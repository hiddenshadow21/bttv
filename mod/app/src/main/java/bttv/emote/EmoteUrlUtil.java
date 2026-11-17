package bttv.emote;

import android.util.Log;

import tv.twitch.android.shared.emotes.utils.AnimatedEmotesUrlUtil;

public class EmoteUrlUtil {
    private static final String TAG = "LBTTVEmoteurlUtil";

    public static String getEmoteUrl(String id, AnimatedEmotesUrlUtil.EmoteUrlAnimationSetting setting) {
        String url = getEmoteUrl(id);
        if (url == null) {
            return null;
        }
        if (setting == AnimatedEmotesUrlUtil.EmoteUrlAnimationSetting.STATIC) {
            return url + "?static=true";
        }
        return url;
    }

    public static String getEmoteUrl(String id) {
        String realId = extractBTTVId(id);
        if (realId == null) {
            return null;
        }
        return realIdToUrl(realId);
    }

    private static final String TWITCH_EMOTE_URL_MARKER = "/emoticons/v2/";

    /** @return the emote id in a Twitch emote url (".../emoticons/v2/<id>/..."), null if it is none */
    public static String idFromTwitchUrl(String uri) {
        if (uri == null) {
            return null;
        }
        int start = uri.indexOf(TWITCH_EMOTE_URL_MARKER);
        if (start == -1) {
            return null;
        }
        start += TWITCH_EMOTE_URL_MARKER.length();
        int end = uri.indexOf('/', start);
        return end == -1 ? uri.substring(start) : uri.substring(start, end);
    }

    // id of an emote in a message that got a wider slot, see WideEmotes
    public static final String WIDE_PREFIX = "BTTV-wide-";
    // The per-occurrence suffix stores the preceding emote's width in
    // quarter-height units. The 7TV image still resolves by its real ID.
    public static final String ZERO_WIDTH_PREFIX = "BTTV-zw-";

    public static String overlayId(String realId, int baseWidthSteps) {
        int steps = Math.max(0, Math.min(12, baseWidthSteps));
        return ZERO_WIDTH_PREFIX + steps + "-" + realId;
    }

    /** -1 if not an overlay ID, otherwise the preceding emote width steps. */
    public static int overlayBaseSteps(String id) {
        if (id == null || !id.startsWith(ZERO_WIDTH_PREFIX)) return -1;
        int start = ZERO_WIDTH_PREFIX.length();
        int dash = id.indexOf('-', start);
        if (dash <= start || dash + 1 >= id.length()) return -1;
        try {
            int steps = Integer.parseInt(id.substring(start, dash));
            return steps >= 0 && steps <= 12 ? steps : -1;
        } catch (NumberFormatException ignored) {
            return -1;
        }
    }

    public static String extractBTTVId(String id) {
        if (id == null) return null;
        if (overlayBaseSteps(id) >= 0) {
            return id.substring(id.indexOf('-', ZERO_WIDTH_PREFIX.length()) + 1);
        }
        if (id.startsWith(WIDE_PREFIX)) {
            return id.substring(WIDE_PREFIX.length());
        }
        if (!id.startsWith("BTTV-")) {
            return null;
        }
        return id.split("BTTV-")[1];
    }

    public static String realIdToUrl(String realId) {
        Emote emote = Emotes.getEmoteById(realId);
        if (emote == null) {
            Log.w("LBTTVEmoteUrlUtil", "emote is null, fall back to bttv url, realId was " + realId);
            return "https://cdn.betterttv.net/emote/" + realId + "/2x"; // gamble
        }
        return emote.url;
    }

}
