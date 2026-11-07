package bttv;

import android.util.Log;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import bttv.settings.Settings;

/**
 * Auto-claim for Twitch 31.8's *React Native* channel-points implementation.
 *
 * In Hermes, useClaimableBonus listens to the channel-points pubsub topic and
 * calls CLAIM_COMMUNITY_POINTS_MUTATION when the user clicks Claim Bonus.
 * The older native ic9 presenter is NOT used for that popup. We observe the
 * same incoming React Native websocket event and send the same GraphQL mutation
 * with the app's existing authenticated RN network headers.
 *
 * No credential is written to disk, included in diagnostics, or logged.
 */
public final class RNChannelPoints318 {
    private static final String TAG = "LBTTVPoints318";
    private static final String GQL_HOST = "gql.twitch.tv";
    private static final long EVENT_MAX_AGE_MS = 120_000L;
    private static final int MAX_PENDING = 32;
    private static final int MAX_RECENT = 128;
    private static final ExecutorService EXECUTOR = Executors.newSingleThreadExecutor();
    private static final Object LOCK = new Object();
    private static RequestSession session;
    private static boolean loggedHermesTransport;
    private static final LinkedHashMap<String, Bonus> pending = new LinkedHashMap<>();
    private static final LinkedHashMap<String, Long> tried = new LinkedHashMap<>();

    // Decompiled from Twitch 31.8.0's actual Hermes CLAIM_COMMUNITY_POINTS_MUTATION.
    private static final String CLAIM_MUTATION =
            "mutation ClaimCommunityPoints($input: ClaimCommunityPointsInput!) {" +
            " claimCommunityPoints(input: $input) {" +
            " claim { id multipliers { factor reasonCode } pointsEarnedBaseline pointsEarnedTotal }" +
            " currentPoints error { code }" +
            " } }";

    private RNChannelPoints318() { }

    private static final class RequestSession {
        final String url;
        final Map<String, String> headers;
        RequestSession(String url, Map<String, String> headers) {
            this.url = url;
            this.headers = headers;
        }
    }

    private static final class Bonus {
        final String channel;
        final String claim;
        final long observedAt;
        Bonus(String channel, String claim) {
            this.channel = channel;
            this.claim = claim;
            this.observedAt = System.currentTimeMillis();
        }
        String key() { return channel + ':' + claim; }
    }

    private static boolean enabled() {
        try {
            return Data.ctx != null && ResUtil.getBooleanFromSettings(Settings.AutoRedeemChannelPointsEnabled);
        } catch (Throwable t) {
            Log.w(TAG, "Cannot read auto-claim preference", t);
            return false;
        }
    }

    /** Called from the already-installed RN NetworkingModule.sendRequest hook. */
    public static void onReactNativeRequest(String method, String url, Object headers) {
        if (!"POST".equalsIgnoreCase(method) || url == null) return;
        try {
            URL target = new URL(url);
            if (!"https".equals(target.getProtocol()) || !GQL_HOST.equalsIgnoreCase(target.getHost())) return;
            List<String[]> incoming = RNNetwork.readHeaders(headers);
            Map<String, String> allowed = new LinkedHashMap<>();
            for (String[] pair : incoming) {
                if (pair == null || pair.length != 2 || pair[0] == null || pair[1] == null) continue;
                String key = pair[0].toLowerCase(Locale.ROOT);
                if (key.equals("authorization") || key.equals("client-id") ||
                        key.equals("client-integrity") || key.equals("device-id") ||
                        key.equals("x-device-id") || key.equals("client-session-id") ||
                        key.equals("client-version") || key.equals("user-agent") ||
                        key.equals("accept-language")) {
                    allowed.put(key, pair[1]);
                }
            }
            // No anonymous requests; never synthesize credentials or use a public token.
            if (!allowed.containsKey("authorization") || !allowed.containsKey("client-id")) return;
            synchronized (LOCK) {
                if (session == null) Log.i(TAG, "Captured authenticated RN GraphQL session (headers not logged)");
                session = new RequestSession(url, allowed);
            }
            drain();
        } catch (Throwable t) {
            Log.w(TAG, "Unable to observe authenticated RN GraphQL session", t);
        }
    }

    /**
     * Hermes pubsub uses a JSON WebSocket envelope of the form
     * notification -> pubsub -> message.  Unlike IRC chat events, claim
     * notifications do not arrive as top-level channel points objects.
     */
    public static void onReactNativeSocketFrame(String text) {
        if (text == null || text.length() > 1_000_000) return;
        // Diagnostic only: do not print any payloads, credentials, user IDs or URLs.
        if (!loggedHermesTransport && text.contains("\"notification\"") && text.contains("pubsub")) {
            synchronized (LOCK) {
                if (!loggedHermesTransport) {
                    Log.i(TAG, "Hermes PubSub notification reached RN WebSocket hook");
                    loggedHermesTransport = true;
                }
            }
        }
        if (!text.contains("claim-available")) return;
        Log.i(TAG, "Claim-available text reached RN WebSocket hook");
        try {
            parseNode(new JSONObject(text), null, 0);
        } catch (Throwable t) {
            // Other WebSocket frames (including IRC) are not necessarily JSON.
            Log.d(TAG, "Claim-available text did not parse as Hermes PubSub JSON");
        }
    }

    private static void parseNode(Object object, String inheritedChannel, int depth) {
        if (object == null || depth > 9) return;
        if (object instanceof String) {
            String str = (String) object;
            if (!str.contains("claim-available") || str.length() > 100_000 || !str.trim().startsWith("{")) return;
            try { parseNode(new JSONObject(str), inheritedChannel, depth + 1); }
            catch (Exception ignored) { }
            return;
        }
        if (object instanceof JSONArray) {
            JSONArray arr = (JSONArray) object;
            for (int i = 0; i < Math.min(arr.length(), 50); i++) {
                parseNode(arr.opt(i), inheritedChannel, depth + 1);
            }
            return;
        }
        if (!(object instanceof JSONObject)) return;
        JSONObject json = (JSONObject) object;
        String channel = first(json, "channelID", "channelId", "channel_id");
        if (channel == null) channel = inheritedChannel;
        // Hermes's community-points-user-v1.<id> topic contains the *user* ID,
        // not a broadcaster ID. Never claim for an ID inferred from that topic.
        if (channel == null) channel = channelFromTopic(first(json, "topic", "subscription"));
        JSONObject channelObj = json.optJSONObject("channel");
        if (channel == null && channelObj != null) channel = first(channelObj, "id", "channelID");
        String type = first(json, "type", "eventType");
        if ("claim-available".equals(type)) {
            String claim = first(json, "claimID", "claimId", "claim_id");
            JSONObject data = json.optJSONObject("data");
            if (data == null && json.opt("data") instanceof String) {
                try { data = new JSONObject((String) json.opt("data")); }
                catch (Exception ignored) { }
            }
            if (data != null) {
                if (channel == null) channel = first(data, "channelID", "channelId", "channel_id");
                if (claim == null) claim = first(data, "claimID", "claimId", "claim_id");
                JSONObject claimObj = data.optJSONObject("claim");
                if (claimObj == null) claimObj = data.optJSONObject("availableClaim");
                JSONObject payload = data.optJSONObject("data");
                if (claim == null && payload != null) {
                    claim = first(payload, "claimID", "claimId", "claim_id");
                    if (channel == null) channel = first(payload, "channelID", "channelId", "channel_id");
                    if (claimObj == null) claimObj = payload.optJSONObject("claim");
                }
                if (claim == null && claimObj != null) claim = first(claimObj, "id");
                if (channel == null) channel = channelFromClaim(claimObj);
            }
            JSONObject claimObj = json.optJSONObject("claim");
            if (claimObj == null) claimObj = json.optJSONObject("availableClaim");
            if (claim == null && claimObj != null) claim = first(claimObj, "id");
            if (channel == null) channel = channelFromClaim(claimObj);
            if (channel == null && Data.currentBroadcasterId > 0) {
                channel = Integer.toString(Data.currentBroadcasterId);
            }
            if (validId(channel) && validId(claim)) enqueue(new Bonus(channel, claim));
            else Log.i(TAG, "Saw RN claim-available event but its claim/channel ID was absent");
            return;
        }
        // Twitch pubsub can nest stringified JSON under data.message or payload.
        for (String key : new String[]{"notification", "pubsub", "message", "data", "payload", "event", "events"}) {
            parseNode(json.opt(key), channel, depth + 1);
        }
    }

    private static String first(JSONObject json, String... keys) {
        if (json == null) return null;
        for (String key : keys) {
            String s = json.optString(key, "").trim();
            if (!s.isEmpty() && !"null".equals(s)) return s;
        }
        return null;
    }

    private static boolean validId(String s) {
        return s != null && !s.isEmpty() && s.length() < 160 && s.matches("[A-Za-z0-9_-]+");
    }

    private static String channelFromTopic(String topic) {
        if (topic == null || !topic.startsWith("community-points-channel-v1.")) return null;
        String id = topic.substring("community-points-channel-v1.".length());
        return id.matches("[0-9]+") ? id : null;
    }

    /** Hermes communityPointsClaim decoder reads claim.point_gain.channel_id. */
    private static String channelFromClaim(JSONObject claim) {
        if (claim == null) return null;
        String channel = first(claim, "channel_id", "channelID", "channelId");
        if (channel != null) return channel;
        JSONObject pointGain = claim.optJSONObject("point_gain");
        if (pointGain == null) pointGain = claim.optJSONObject("pointGain");
        return first(pointGain, "channel_id", "channelID", "channelId");
    }

    private static void enqueue(Bonus bonus) {
        if (!enabled()) return;
        synchronized (LOCK) {
            if (tried.containsKey(bonus.key()) || pending.containsKey(bonus.key())) return;
            if (pending.size() >= MAX_PENDING) pending.remove(pending.keySet().iterator().next());
            pending.put(bonus.key(), bonus);
        }
        Log.i(TAG, "RN claim-available event received; awaiting authenticated request if necessary");
        drain();
    }

    private static void drain() {
        final List<Bonus> work = new ArrayList<>();
        final RequestSession current;
        synchronized (LOCK) {
            current = session;
            if (pending.isEmpty()) return;
            if (current == null) {
                Log.i(TAG, "Bonus detected, waiting for authenticated RN GraphQL session");
                return;
            }
            long now = System.currentTimeMillis();
            for (Bonus b : pending.values()) {
                if (now - b.observedAt < EVENT_MAX_AGE_MS && !tried.containsKey(b.key())) {
                    tried.put(b.key(), now);
                    work.add(b);
                }
            }
            pending.clear();
            while (tried.size() > MAX_RECENT) tried.remove(tried.keySet().iterator().next());
        }
        for (final Bonus bonus : work) {
            EXECUTOR.execute(() -> submit(current, bonus));
        }
    }

    private static void submit(RequestSession current, Bonus bonus) {
        if (!enabled()) return;
        HttpURLConnection conn = null;
        try {
            JSONObject vars = new JSONObject()
                    .put("input", new JSONObject().put("channelID", bonus.channel).put("claimID", bonus.claim));
            JSONObject request = new JSONObject().put("operationName", "ClaimCommunityPoints")
                    .put("query", CLAIM_MUTATION).put("variables", vars);
            byte[] bytes = request.toString().getBytes(StandardCharsets.UTF_8);
            conn = (HttpURLConnection) new URL(current.url).openConnection();
            conn.setConnectTimeout(12_000);
            conn.setReadTimeout(12_000);
            conn.setRequestMethod("POST");
            conn.setDoOutput(true);
            conn.setRequestProperty("Content-Type", "application/json");
            for (Map.Entry<String, String> header : current.headers.entrySet()) {
                conn.setRequestProperty(header.getKey(), header.getValue());
            }
            try (OutputStream out = conn.getOutputStream()) { out.write(bytes); }
            int status = conn.getResponseCode();
            InputStream in = status >= 400 ? conn.getErrorStream() : conn.getInputStream();
            String response = readStream(in);
            JSONObject root = new JSONObject(response);
            JSONObject data = root.optJSONObject("data");
            JSONObject result = data == null ? null : data.optJSONObject("claimCommunityPoints");
            boolean ok = status >= 200 && status < 300 && result != null &&
                    !result.isNull("claim") && result.optJSONObject("error") == null &&
                    (root.optJSONArray("errors") == null || root.optJSONArray("errors").length() == 0);
            if (ok) Log.i(TAG, "RN channel-point bonus claimed successfully");
            else Log.w(TAG, "RN channel-point claim rejected (HTTP " + status + ")");
        } catch (Exception e) {
            Log.w(TAG, "RN channel-point claim request failed", e);
        } finally {
            if (conn != null) conn.disconnect();
        }
    }

    private static String readStream(InputStream in) throws Exception {
        if (in == null) return "{}";
        try (InputStream stream = in; ByteArrayOutputStream buffer = new ByteArrayOutputStream()) {
            byte[] tmp = new byte[4096];
            int n;
            while ((n = stream.read(tmp)) != -1 && buffer.size() < 64_000) buffer.write(tmp, 0, n);
            return buffer.toString("UTF-8");
        }
    }
}
