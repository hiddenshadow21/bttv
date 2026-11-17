package bttv.emote;

import android.os.Handler;
import android.view.View;
import android.widget.TextView;
import android.os.Looper;
import android.util.Log;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.Collections;
import java.util.Map;

import bttv.RNNetwork;

/**
 * Answers the "EmoteCard" GraphQL request of the react native chat for our emotes,
 * Twitch does not know them and would show an error.
 */
public class RNEmoteCard {
    private static final String TAG = "LBTTVRNEmoteCard";
    private static final String OPERATION = "EmoteCard";
    private static final long ACTIVE_MS = 15000;
    private static volatile Emote activeEmote = null;
    private static volatile long activeUntil = 0;
    private static volatile String activeId = null;
    private static final Map<String, String> HEADERS = Collections.singletonMap("content-type", "application/json");

    /**
     * @param module react native NetworkingModule
     * @param body request body
     * @return true if we answer this request, it must not be sent then
     */
    public static boolean intercept(final Object module, final String url, final int requestId, String body) throws Exception {
        if (body == null || !body.contains("\"" + OPERATION + "\"")) {
            return false;
        }
        final boolean isBatch = body.trim().startsWith("[");
        JSONObject operation;
        if (isBatch) {
            JSONArray batch = new JSONArray(body);
            if (batch.length() != 1) {
                // other operations need a real answer
                return false;
            }
            operation = batch.getJSONObject(0);
        } else {
            operation = new JSONObject(body);
        }

        if (!OPERATION.equals(operation.optString("operationName"))) {
            return false;
        }
        JSONObject variables = operation.optJSONObject("variables");
        String emoteId = variables == null ? null : variables.optString("emoteID", null);
        // Even native Twitch emotes can be the BASE of a 7TV overlay.
        // Let Twitch handle its own GraphQL response, but retain the stack
        // information for its existing bottom-sheet caption.
        StackedEmoteDetails.onCardRequest(emoteId);
        String realId = emoteId == null ? null : EmoteUrlUtil.extractBTTVId(emoteId);
        if (realId == null) {
            // An official Twitch emote may be the base of a 7TV stack.
            // Do not replace its real GraphQL result.
            activeEmote = null;
            activeId = null;
            activeUntil = System.currentTimeMillis() + ACTIVE_MS;
            return false;
        }
        Emote emote = Emotes.getEmoteById(realId);
        if (emote == null) { // triggers error dialog
            Log.w(TAG, "intercept: unknown emote " + emoteId);
            return false;
        }

        JSONObject response = buildResponse(emoteId, emote);
        final String responseBody = isBatch ? new JSONArray().put(response).toString() : response.toString();

        // answer after sendRequest returned
        new Handler(Looper.getMainLooper()).post(new Runnable() {
            @Override
            public void run() {
                try {
                    RNNetwork.emitResponse(module, requestId, 200, HEADERS, url, responseBody);
                } catch (Throwable t) {
                    Log.e(TAG, "respond: ", t);
                }
            }
        });
        Log.d(TAG, "intercept: answering request " + requestId + " for " + emoteId);
        activeUntil = System.currentTimeMillis() + ACTIVE_MS;
        activeEmote = emote;
        activeId = emoteId;
        return true;
    }

    /**
     * Rewrite only the two named native React Native EmoteCard text views.
     * This runs after Twitch updates their text. It must NOT rewrite ordinary
     * chat, and it must not change Twitch's original GraphQL response for a
     * native base emote.
     */
    public static void onNativeCardText(View view) {
        if (!(view instanceof TextView)) return;
        Object tag = view.getTag();
        if (!(tag instanceof String)) return;
        String id = (String) tag;
        if (!id.equals("chat-emote-card-type")
                && !id.equals("chat-emote-card-copy")
                && !id.equals("chat-emote-card-code")) return;
        String text = replacementFor(id);
        if (text == null) return;
        TextView label = (TextView) view;
        CharSequence previous = label.getText();
        if (!text.contentEquals(previous == null ? "" : previous)) {
            label.setText(text);
            Log.d(TAG, "Updated native sheet emote metadata: " + id);
        }
    }

    /** Also called when RN assigns the testID after the text update. */
    public static void onNativeCardTestId(View view, String testId) {
        if (testId != null && testId.startsWith("chat-emote-card-")) {
            onNativeCardText(view);
        }
    }

    static String replacementFor(String testId) {
        if (System.currentTimeMillis() > activeUntil) {
            activeEmote = null;
            activeId = null;
            return null;
        }
        StackedEmoteDetails.Stack stack = StackedEmoteDetails.activeCard();
        if (stack != null) {
            if ("chat-emote-card-code".equals(testId)) {
                return StackedEmoteDetails.cardTitle(activeId, "");
            }
            if ("chat-emote-card-type".equals(testId)) {
                return StackedEmoteDetails.cardOrigins();
            }
            if ("chat-emote-card-copy".equals(testId)) {
                return StackedEmoteDetails.cardDescription();
            }
        }
        Emote emote = activeEmote;
        if (emote == null) return null;
        if ("chat-emote-card-type".equals(testId)) return providerAndScope(emote);
        if ("chat-emote-card-copy".equals(testId)) {
            return "Third-party emote from " + providerAndScope(emote) + ".";
        }
        return null;
    }

    /** Backward-compatible entry point; use view-specific interception above. */
    public static String swapText(String text) {
        return text;
    }

    /** Use the real catalog, not Twitch's synthetic GLOBALS GraphQL type. */
    static String providerAndScope(Emote emote) {
        if (emote == null) return "Twitch Emote";
        String source;
        switch (emote.source) {
            case FFZ: source = "FrankerFaceZ"; break;
            case STV: source = "7TV"; break;
            default: source = "BetterTTV";
        }
        Emote global = Emotes.globalFor(emote.source).get(emote.code);
        boolean isGlobal = global != null && emote.id.equals(global.id);
        return source + (isGlobal ? " Global Emote" : " Channel Emote");
    }

    private static JSONObject buildResponse(String emoteId, Emote emote) throws Exception {
        JSONObject emoteJson = new JSONObject();
        emoteJson.put("id", emoteId);
        emoteJson.put("token", StackedEmoteDetails.cardTitle(emoteId, emote.code));
        emoteJson.put("type", "GLOBALS");
        // Twitch's existing EmoteCard supports an auxiliary emote image strip
        // using subscriptionSummaries, even for a global-type emote. Expose
        // the other members of a stacked pair there, no custom Android dialog.
        JSONArray otherEmotes = new JSONArray();
        StackedEmoteDetails.Stack stack = StackedEmoteDetails.activeCard();
        if (stack != null && stack.ids.contains(emoteId)) {
            for (String id : stack.ids) {
                if (id.equals(emoteId)) continue;
                otherEmotes.put(new JSONObject()
                        .put("id", id)
                        .put("token", StackedEmoteDetails.name(id)));
            }
        }
        boolean hasStack = otherEmotes.length() > 0;
        emoteJson.put("subscriptionTier", hasStack ? "TIER_1" : JSONObject.NULL);
        emoteJson.put("setID", "0");
        emoteJson.put("owner", JSONObject.NULL);
        JSONArray summaries = new JSONArray();
        if (hasStack) {
            summaries.put(new JSONObject()
                    .put("tier", "TIER_1")
                    .put("emotes", otherEmotes));
        }
        emoteJson.put("subscriptionSummaries", summaries);
        emoteJson.put("bitsBadgeTierSummary", JSONObject.NULL);
        emoteJson.put("__typename", "Emote");

        JSONObject extensions = new JSONObject();
        extensions.put("durationMilliseconds", 1);
        extensions.put("operationName", OPERATION);
        extensions.put("requestID", "bttv-android");

        JSONObject response = new JSONObject();
        response.put("data", new JSONObject().put("emote", emoteJson));
        response.put("extensions", extensions);
        return response;
    }
}
