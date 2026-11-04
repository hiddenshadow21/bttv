package bttv.rn;

import android.content.Context;
import android.util.Log;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.lang.reflect.Method;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collection;
import java.util.Collections;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import bttv.Data;
import bttv.Network;
import bttv.emote.Emote;
import bttv.emote.Emotes;

/** React Native chat, image, and picker integrations for the 31.8.0 port.
 * Only stable React Native APIs and plain Java types cross smali hook boundaries.
 * Request bodies, auth headers, raw chat frames, and cookies are NEVER logged.
 */
public final class RNFeatureHooks318 {
    private static final String TAG = "BTTV318RN";
    private static final ExecutorService IO = Executors.newFixedThreadPool(2);
    private static final Set<Integer> BYPASSED = Collections.synchronizedSet(new HashSet<Integer>());
    private static final String TWITCH_EMOTE_PATH = "/emoticons/v2/";
    private static final String PREFIX = "BTTV-";
    private static volatile int rewritten = 0;
    private static volatile int imageRewrites = 0;
    private static volatile int pickerRequests = 0;

    private RNFeatureHooks318() {}

    public static String rewriteFrame(String frame) {
        if (frame == null) return null;
        RNChatExtras318.onRoomState(frame);
        if (frame.indexOf(" PRIVMSG #") == -1) return frame;
        try {
            String[] lines = frame.split("\\r\\n", -1);
            StringBuilder out = new StringBuilder(frame.length() + 32);
            boolean changed = false;
            for (int i = 0; i < lines.length; i++) {
                if (i > 0) out.append("\r\n");
                String replacement = RNChatExtras318.addTimestamp(rewriteLine(lines[i]));
                if (!replacement.equals(lines[i])) changed = true;
                out.append(replacement);
            }
            if (changed && ++rewritten <= 5) Log.i(TAG, "React Native IRC emote tags rewritten");
            return changed ? out.toString() : frame;
        } catch (Throwable t) {
            Log.e(TAG, "IRC rewrite error; forwarding original frame", t);
            return frame;
        }
    }

    private static String rewriteLine(String line) {
        if (!line.startsWith("@")) return line;
        int tagsEnd = line.indexOf(' ');
        int command = tagsEnd < 0 ? -1 : line.indexOf(" PRIVMSG #", tagsEnd);
        if (command < 0) return line;
        int textStart = line.indexOf(" :", command);
        if (textStart < 0) return line;
        textStart += 2;
        String text = line.substring(textStart);
        if (text.startsWith("\u0001")) return line;
        String tags = line.substring(1, tagsEnd);
        String room = tag(tags, "room-id");
        if (room == null) return line;
        int channel = Integer.parseInt(room);
        Context context = Data.ctx;
        if (context == null) return line;
        if (channel > 0 && channel != Data.currentBroadcasterId) Data.setCurrentBroadcasterId(channel);
        String current = tag(tags, "emotes");
        if (current == null) return line; // Do not manufacture an IRC tag when parser omits it.
        Set<Integer> occupied = new HashSet<>();
        if (!current.isEmpty()) {
            for (String emote : current.split("/")) {
                int colon = emote.indexOf(':');
                if (colon < 0) continue;
                for (String range : emote.substring(colon + 1).split(",")) {
                    int dash = range.indexOf('-');
                    if (dash > 0) occupied.add(Integer.parseInt(range.substring(0, dash)));
                }
            }
        }
        Map<String, List<String>> ranges = new LinkedHashMap<>();
        int pos = 0;
        for (String word : text.split(" ", -1)) {
            if (!word.isEmpty() && !occupied.contains(pos)) {
                Emote e = Emotes.getEmote(context, word, channel);
                if (e != null && e.id != null && !e.id.isEmpty()) {
                    String id = PREFIX + e.id;
                    List<String> list = ranges.get(id);
                    if (list == null) { list = new ArrayList<>(); ranges.put(id, list); }
                    int length = word.codePointCount(0, word.length());
                    list.add(pos + "-" + (pos + length - 1));
                }
            }
            pos += word.codePointCount(0, word.length()) + 1;
        }
        if (ranges.isEmpty()) return line;
        StringBuilder updated = new StringBuilder(current);
        for (Map.Entry<String, List<String>> e : ranges.entrySet()) {
            if (updated.length() != 0) updated.append('/');
            updated.append(e.getKey()).append(':');
            for (int i = 0; i < e.getValue().size(); i++) {
                if (i > 0) updated.append(',');
                updated.append(e.getValue().get(i));
            }
        }
        return "@" + replaceTag(tags, "emotes", updated.toString()) + line.substring(tagsEnd);
    }

    private static String tag(String tags, String name) {
        String prefix = name + "=";
        int start = tags.startsWith(prefix) ? 0 : tags.indexOf(";" + prefix);
        if (start < 0) return null;
        start += (start == 0 ? 0 : 1) + prefix.length();
        int end = tags.indexOf(';', start);
        return tags.substring(start, end < 0 ? tags.length() : end);
    }
    private static String replaceTag(String tags, String name, String replacement) {
        String prefix = name + "=";
        int start = tags.startsWith(prefix) ? 0 : tags.indexOf(";" + prefix);
        if (start < 0) return tags;
        start += (start == 0 ? 0 : 1) + prefix.length();
        int end = tags.indexOf(';', start);
        return tags.substring(0, start) + replacement + (end < 0 ? "" : tags.substring(end));
    }

    public static String redirectImageUri(String uri) {
        if (uri == null) return null;
        try {
            int begin = uri.indexOf(TWITCH_EMOTE_PATH);
            if (begin < 0) return uri;
            begin += TWITCH_EMOTE_PATH.length();
            int end = uri.indexOf('/', begin);
            if (end < 0) end = uri.length();
            int query = uri.indexOf('?', begin);
            if (query >= 0 && query < end) end = query;
            String id = uri.substring(begin, end);
            if (!id.startsWith(PREFIX)) return uri;
            Emote e = Emotes.getEmoteById(id.substring(PREFIX.length()));
            String target = e == null ? null : e.url;
            if (e != null) RNAnimatedInput318.register(e);
            if (target == null || (!target.startsWith("https://") && !target.startsWith("http://"))) {
                // Do not guess a BTTV URL for an FFZ/7TV ID.
                return uri;
            }
            if (++imageRewrites <= 5) Log.i(TAG, "React Native emote image URL redirected");
            return target;
        } catch (Throwable t) {
            Log.e(TAG, "Image URI redirect failed", t);
            return uri;
        }
    }

    /** Copy-on-write conversion of React Native's image source array. Does not alter stock sources. */
    public static Object rewriteReactSources(Object input) {
        if (input == null) return null;
        try {
            Class<?> readableArray = Class.forName("com.facebook.react.bridge.ReadableArray");
            Class<?> readableMap = Class.forName("com.facebook.react.bridge.ReadableMap");
            Class<?> writableMap = Class.forName("com.facebook.react.bridge.WritableMap");
            Class<?> arguments = Class.forName("com.facebook.react.bridge.Arguments");
            int size = (Integer) readableArray.getMethod("size").invoke(input);
            List<String> changes = new ArrayList<>(size);
            Object[] maps = new Object[size];
            boolean any = false;
            for (int i = 0; i < size; i++) {
                Object item = readableArray.getMethod("getMap", int.class).invoke(input, i);
                maps[i] = item;
                String uri = item == null ? null : (String) readableMap.getMethod("getString", String.class).invoke(item, "uri");
                String updated = redirectImageUri(uri);
                changes.add(updated);
                if (updated != null && !updated.equals(uri)) any = true;
            }
            if (!any) return input;
            Object output = arguments.getMethod("createArray").invoke(null);
            Method createMap = arguments.getMethod("createMap");
            for (int i = 0; i < size; i++) {
                Object map = createMap.invoke(null);
                writableMap.getMethod("merge", readableMap).invoke(map, maps[i]);
                writableMap.getMethod("putString", String.class, String.class).invoke(map, "uri", changes.get(i));
                output.getClass().getMethod("pushMap", readableMap).invoke(output, map);
            }
            return output;
        } catch (Throwable t) {
            Log.e(TAG, "React image source adaptation failed; keeping original", t);
            return input;
        }
    }

    public static boolean interceptNetwork(final Object module, final String method, final String url,
            final double requestId, final Object headers, final Object data, final String responseType,
            final boolean incremental, final double timeout, final boolean credentials) {
        if (module == null || !"POST".equals(method) || url == null || !url.contains("gql.twitch.tv")) return false;
        final int id = (int) requestId;
        if (BYPASSED.remove(id)) return false;
        try {
            String body = requestBody(data);
            if (body == null) return false;
            // Synthetic BTTV IDs cannot be resolved by Twitch's EmoteCard endpoint.
            // Handle only recognized one-operation requests. All others go untouched.
            if (body.contains("EmoteCard") && interceptEmoteCard(module, url, id, body)) return true;
            if (!body.contains("ChatEmoteSets") || !hasOperation(body, "ChatEmoteSets")) return false;
            final String request = body;
            final List<String[]> requestHeaders = requestHeaders(headers);
            IO.execute(new Runnable() {
                @Override public void run() {
                    try {
                        proxyPicker(module, id, url, requestHeaders, request);
                    } catch (Throwable t) {
                        Log.e(TAG, "RN emote picker interception failed; falling back to Twitch", t);
                        try {
                            BYPASSED.add(id);
                            Class<?> ra = Class.forName("com.facebook.react.bridge.ReadableArray");
                            Class<?> rm = Class.forName("com.facebook.react.bridge.ReadableMap");
                            module.getClass().getMethod("sendRequest", String.class, String.class, double.class,
                                    ra, rm, String.class, boolean.class, double.class, boolean.class)
                                    .invoke(module, method, url, requestId, headers, data, responseType, incremental, timeout, credentials);
                        } catch (Throwable nested) {
                            BYPASSED.remove(id);
                            Log.e(TAG, "RN emote picker fallback failed", nested);
                        }
                    }
                }
            });
            if (++pickerRequests <= 3) Log.i(TAG, "ChatEmoteSets request intercepted");
            return true;
        } catch (Throwable t) {
            Log.e(TAG, "Unable to inspect GraphQL request; keeping stock handling", t);
            return false;
        }
    }
    /** PR #740: EmoteCard for BTTV/FFZ/7TV must not be sent to Twitch's API. */
    private static boolean interceptEmoteCard(final Object module, final String url, final int id, String request) throws Exception {
        boolean batch = request.trim().startsWith("[");
        JSONArray operations = batch ? new JSONArray(request) : new JSONArray().put(new JSONObject(request));
        // Never synthesize part of a GraphQL batch and drop the remaining operations.
        if (operations.length() != 1) return false;
        JSONObject operation = operations.getJSONObject(0);
        if (!"EmoteCard".equals(operation.optString("operationName"))) return false;
        JSONObject variables = operation.optJSONObject("variables");
        String requested = variables == null ? null : variables.optString("emoteID", null);
        if (requested == null) return false;
        String realId = requested.startsWith("BTTV-wide-") ? requested.substring("BTTV-wide-".length())
                : requested.startsWith(PREFIX) ? requested.substring(PREFIX.length()) : null;
        if (realId == null || realId.isEmpty()) return false;
        Emote emote = Emotes.getEmoteById(realId);
        if (emote == null) return false; // Unknown ID; preserve Twitch's normal fallback.
        JSONObject item = new JSONObject();
        item.put("id", requested);
        item.put("token", emote.code);
        item.put("type", "GLOBALS");
        item.put("subscriptionTier", JSONObject.NULL);
        item.put("setID", "0");
        item.put("owner", JSONObject.NULL);
        item.put("subscriptionSummaries", new JSONArray());
        item.put("bitsBadgeTierSummary", JSONObject.NULL);
        item.put("__typename", "Emote");
        JSONObject result = new JSONObject();
        result.put("data", new JSONObject().put("emote", item));
        result.put("extensions", new JSONObject().put("operationName", "EmoteCard")
                .put("durationMilliseconds", 1).put("requestID", "bttv-android"));
        final String answer = batch ? new JSONArray().put(result).toString() : result.toString();
        // RN expects the events after sendRequest has returned to JS.
        android.os.Handler main = new android.os.Handler(android.os.Looper.getMainLooper());
        main.post(new Runnable() {
            @Override public void run() {
                try {
                    Map<String, String> h = Collections.singletonMap("content-type", "application/json");
                    emitResponse(module, id, 200, h, url, answer);
                } catch (Throwable failure) { Log.e(TAG, "External EmoteCard response failed", failure); }
            }
        });
        Log.i(TAG, "External emote metadata card answered (provider=" + emote.source.name() + ")");
        return true;
    }

    private static String requestBody(Object map) throws Exception {
        if (map == null) return null;
        Class<?> rm = Class.forName("com.facebook.react.bridge.ReadableMap");
        if (!(Boolean) rm.getMethod("hasKey", String.class).invoke(map, "string")) return null;
        return (String) rm.getMethod("getString", String.class).invoke(map, "string");
    }
    private static boolean hasOperation(String body, String name) throws Exception {
        if (body.trim().startsWith("[")) {
            JSONArray batch = new JSONArray(body);
            for (int i = 0; i < batch.length(); i++) if (name.equals(batch.getJSONObject(i).optString("operationName"))) return true;
            return false;
        }
        return name.equals(new JSONObject(body).optString("operationName"));
    }
    private static List<String[]> requestHeaders(Object input) throws Exception {
        List<String[]> result = new ArrayList<>();
        if (input == null) return result;
        Class<?> array = Class.forName("com.facebook.react.bridge.ReadableArray");
        int size = (Integer) array.getMethod("size").invoke(input);
        for (int i = 0; i < size; i++) {
            Object pair = array.getMethod("getArray", int.class).invoke(input, i);
            if (pair == null || (Integer) array.getMethod("size").invoke(pair) != 2) continue;
            String key = (String) array.getMethod("getString", int.class).invoke(pair, 0);
            String value = (String) array.getMethod("getString", int.class).invoke(pair, 1);
            if (key != null && value != null) result.add(new String[]{key, value});
        }
        return result;
    }
    private static void proxyPicker(Object module, int id, String url, List<String[]> headers, String body) throws Exception {
        int channel = channelForPickerRequest(body, Data.currentBroadcasterId);
        if (channel > 0 && channel != Data.currentBroadcasterId) Data.setCurrentBroadcasterId(channel);
        if (channel > 0) Emotes.ensureChannelEmotes(Data.ctx, channel);
        HttpURLConnection connection = (HttpURLConnection) new URL(url).openConnection();
        int status;
        String responseText;
        Map<String, String> responseHeaders = new LinkedHashMap<>();
        try {
            connection.setRequestMethod("POST");
            connection.setDoOutput(true);
            connection.setConnectTimeout(10000);
            connection.setReadTimeout(10000);
            for (String[] header : headers) {
                String key = header[0];
                if (key.equalsIgnoreCase("content-length") || key.equalsIgnoreCase("host") || key.equalsIgnoreCase("accept-encoding")) continue;
                connection.setRequestProperty(key, header[1]);
            }
            try (OutputStream out = connection.getOutputStream()) { out.write(body.getBytes("UTF-8")); }
            status = connection.getResponseCode();
            if (status != 200) throw new IllegalStateException("GraphQL status " + status);
            for (Map.Entry<String, List<String>> e : connection.getHeaderFields().entrySet()) {
                if (e.getKey() != null && e.getValue() != null && !e.getValue().isEmpty()) {
                    String key = e.getKey().toLowerCase(java.util.Locale.ROOT);
                    if (!key.equals("content-encoding") && !key.equals("content-length") && !key.equals("transfer-encoding"))
                        responseHeaders.put(e.getKey(), e.getValue().get(e.getValue().size() - 1));
                }
            }
            try (InputStream stream = connection.getInputStream(); ByteArrayOutputStream output = new ByteArrayOutputStream()) {
                byte[] buffer = new byte[8192];
                int n;
                while ((n = stream.read(buffer)) >= 0) {
                    if (n > 0) output.write(buffer, 0, n);
                    if (output.size() > 5_000_000) throw new IllegalStateException("GraphQL response too large");
                }
                responseText = output.toString("UTF-8");
            }
        } finally { connection.disconnect(); }
        waitForPickerCatalogs(channel);
        String response = responseText;
        try { response = injectEmoteSets(body, responseText, channel); }
        catch (Throwable t) { Log.e(TAG, "Picker payload conversion failed; returning stock response", t); }
        emitResponse(module, id, status, responseHeaders, url, response);
    }
    /** The picker request carries the channel before the first IRC ROOMSTATE frame on some streams. */
    private static int channelForPickerRequest(String request, int fallback) {
        try {
            JSONArray operations = request.trim().startsWith("[") ? new JSONArray(request)
                    : new JSONArray().put(new JSONObject(request));
            for (int i = 0; i < operations.length(); i++) {
                JSONObject op = operations.getJSONObject(i);
                if (!"ChatChannelLockedEmotes".equals(op.optString("operationName"))) continue;
                JSONObject vars = op.optJSONObject("variables");
                String id = vars == null ? "" : vars.optString("channelOwnerID", "");
                if (id.isEmpty()) continue;
                int parsed = Integer.parseInt(id);
                if (parsed > 0) return parsed;
            }
        } catch (Throwable error) {
            Log.w(TAG, "Picker channel ID not available; retaining current channel", error);
        }
        return fallback;
    }

    /** Give asynchronous provider responses time to populate all three channel catalogs. */
    private static void waitForPickerCatalogs(int channel) throws InterruptedException {
        long until = System.currentTimeMillis() + 4000;
        while (System.currentTimeMillis() < until) {
            boolean globals = !Emotes.globalEmotesBTTV.isEmpty();
            boolean channels = channel <= 0 || (Emotes.channelEmotesBTTV.containsKey(channel)
                    && Emotes.channelEmotesFFZ.containsKey(channel)
                    && Emotes.channelEmotes7TV.containsKey(channel));
            if (globals && channels) break;
            Thread.sleep(60);
        }
    }

    private static String injectEmoteSets(String request, String response, int channel) throws Exception {
        boolean batch = request.trim().startsWith("[");
        JSONArray req = batch ? new JSONArray(request) : new JSONArray().put(new JSONObject(request));
        JSONArray res = batch ? new JSONArray(response) : new JSONArray().put(new JSONObject(response));
        int index = -1;
        for (int i = 0; i < req.length(); i++) if ("ChatEmoteSets".equals(req.getJSONObject(i).optString("operationName"))) { index = i; break; }
        if (index < 0) return response;
        JSONObject data = res.getJSONObject(index).getJSONObject("data");
        JSONArray sets = data.getJSONObject("currentUser").getJSONArray("emoteSets");
        JSONObject setTemplate = null, emoteTemplate = null, ownerTemplate = null;
        for (int i = 0; i < sets.length(); i++) {
            JSONObject set = sets.getJSONObject(i);
            if (setTemplate == null) setTemplate = set;
            if (ownerTemplate == null && set.optJSONObject("owner") != null) {
                ownerTemplate = set.getJSONObject("owner");
                setTemplate = set;
            }
            JSONArray es = set.optJSONArray("emotes");
            if (es != null && es.length() > 0 && emoteTemplate == null) emoteTemplate = es.getJSONObject(0);
        }
        if (setTemplate == null || emoteTemplate == null) return response;
        if (ownerTemplate == null) {
            // Without an owner, React Native categorizes synthetic sets as Twitch Global.
            ownerTemplate = new JSONObject().put("id", "").put("login", "")
                    .put("displayName", "").put("profileImageURL", "")
                    .put("__typename", "User");
        }
        JSONArray custom = new JSONArray();
        int added = 0;
        int channels = 0;
        if (channel > 0) {
            channels += addSet(custom, setTemplate, emoteTemplate, ownerTemplate, "BetterTTV Channel", "bttv-channel-" + channel, channelSet(Emotes.channelEmotesBTTV.get(channel), channel, Emotes.Source.BTTV));
            channels += addSet(custom, setTemplate, emoteTemplate, ownerTemplate, "FrankerFaceZ Channel", "ffz-channel-" + channel, channelSet(Emotes.channelEmotesFFZ.get(channel), channel, Emotes.Source.FFZ));
            channels += addSet(custom, setTemplate, emoteTemplate, ownerTemplate, "7TV Channel", "7tv-channel-" + channel, channelSet(Emotes.channelEmotes7TV.get(channel), channel, Emotes.Source.STV));
        }
        added += channels;
        added += addSet(custom, setTemplate, emoteTemplate, ownerTemplate, "BetterTTV Global", "bttv-global", Emotes.globalEmotesBTTV.values());
        added += addSet(custom, setTemplate, emoteTemplate, ownerTemplate, "FrankerFaceZ Global", "ffz-global", Emotes.globalEmotesFFZ.values());
        added += addSet(custom, setTemplate, emoteTemplate, ownerTemplate, "7TV Global", "7tv-global", Emotes.globalEmotes7TV.values());
        Log.i(TAG, "Picker channel catalogs: channel-known=" + (channel > 0)
                + ", channel-emotes=" + channels + ", total-external=" + added);
        for (int i = 0; i < sets.length(); i++) custom.put(sets.get(i));
        if (added > 0) data.getJSONObject("currentUser").put("emoteSets", custom);
        Log.i(TAG, "RN picker external emotes added=" + added);
        return added > 0 ? (batch ? res.toString() : res.getJSONObject(0).toString()) : response;
    }
    private static Collection<Emote> channelSet(Set<String> codes, int channel, Emotes.Source source) {
        List<Emote> found = new ArrayList<>();
        if (codes != null) for (String code : new ArrayList<>(codes)) {
            Emote e = Emotes.getEmote(channel, code);
            if (e != null && e.source == source) found.add(e);
        }
        return found;
    }
    private static int addSet(JSONArray result, JSONObject template, JSONObject emoteTemplate, JSONObject ownerTemplate,
            String name, String id, Collection<Emote> emotes) throws Exception {
        if (emotes == null || emotes.isEmpty()) return 0;
        String setId = "BTTV-set-" + id;
        JSONArray items = new JSONArray();
        for (Emote e : new ArrayList<>(emotes)) {
            JSONObject item = new JSONObject(emoteTemplate.toString());
            item.put("id", "BTTV-" + e.id);
            item.put("setID", setId);
            item.put("token", e.code);
            item.put("assetType", "gif".equals(e.imageType) ? "ANIMATED" : "STATIC");
            if (item.has("type")) item.put("type", "MEGA_COMMERCE");
            if (item.has("modifiers")) item.put("modifiers", JSONObject.NULL);
            items.put(item);
        }
        JSONObject set = new JSONObject(template.toString());
        set.put("id", setId);
        set.put("emotes", items);
        JSONObject owner = ownerTemplate == null ? new JSONObject() : new JSONObject(ownerTemplate.toString());
        owner.put("id", "BTTV-owner-" + id);
        owner.put("login", id);
        owner.put("displayName", name);
        owner.put("profileImageURL", "https://cdn.betterttv.net/assets/logos/mascot.png");
        owner.put("__typename", "User");
        set.put("owner", owner);
        result.put(set);
        return items.length();
    }
    /** Mirrors the RN NetworkingModule event shape, including the blob response used by Twitch. */
    private static void emitResponse(Object module, int id, int status, Map<String, String> headers, String url, String body) throws Exception {
        Object context = module.getClass().getMethod("getReactApplicationContext").invoke(module);
        Method emit = context.getClass().getMethod("emitDeviceEvent", String.class, Object.class);
        Class<?> args = Class.forName("com.facebook.react.bridge.Arguments");
        Class<?> mapType = Class.forName("com.facebook.react.bridge.ReadableMap");
        Object headerMap = args.getMethod("createMap").invoke(null);
        for (Map.Entry<String, String> entry : headers.entrySet()) {
            headerMap.getClass().getMethod("putString", String.class, String.class).invoke(headerMap, entry.getKey(), entry.getValue());
        }
        Object result = args.getMethod("createArray").invoke(null);
        result.getClass().getMethod("pushInt", int.class).invoke(result, id);
        result.getClass().getMethod("pushInt", int.class).invoke(result, status);
        result.getClass().getMethod("pushMap", mapType).invoke(result, headerMap);
        result.getClass().getMethod("pushString", String.class).invoke(result, url);
        emit.invoke(context, "didReceiveNetworkResponse", result);
        Class<?> blobType = Class.forName("com.facebook.react.modules.blob.BlobModule");
        Object blob = context.getClass().getMethod("getNativeModule", Class.class).invoke(context, blobType);
        byte[] bytes = body.getBytes("UTF-8");
        String blobId = (String) blobType.getMethod("store", byte[].class).invoke(blob, (Object) bytes);
        Object data = args.getMethod("createMap").invoke(null);
        data.getClass().getMethod("putString", String.class, String.class).invoke(data, "blobId", blobId);
        data.getClass().getMethod("putInt", String.class, int.class).invoke(data, "offset", 0);
        data.getClass().getMethod("putInt", String.class, int.class).invoke(data, "size", bytes.length);
        Object payload = args.getMethod("createArray").invoke(null);
        payload.getClass().getMethod("pushInt", int.class).invoke(payload, id);
        payload.getClass().getMethod("pushMap", mapType).invoke(payload, data);
        emit.invoke(context, "didReceiveNetworkData", payload);
        Object complete = args.getMethod("createArray").invoke(null);
        complete.getClass().getMethod("pushInt", int.class).invoke(complete, id);
        complete.getClass().getMethod("pushNull").invoke(complete);
        emit.invoke(context, "didCompleteNetworkResponse", complete);
    }
}
