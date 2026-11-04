package bttv.rn;

import android.util.Log;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import bttv.Data;

/**
 * React Native IRC chat support for Twitch 31.8.0.
 *
 * All modifications are best-effort. If tags are malformed, the original IRC
 * line passes through unchanged. No chat text, account ID or authorization data
 * is logged. Timestamps are displayed as a text prefix rather than as a new
 * React component, pending a dedicated native RN timestamp renderer.
 */
public final class RNChatExtras318 {
    private static final String TAG = "BTTV318Chat";
    private static int timestampLogs;
    private static int channelLogs;

    private RNChatExtras318() {}

    /** Receive join metadata early, as in PR #740's IrcEmotes.onRoomState. */
    public static void onRoomState(String frame) {
        if (frame == null || frame.indexOf(" ROOMSTATE #") < 0) return;
        try {
            String[] lines = frame.split("\\r\\n", -1);
            for (String line : lines) {
                if (!line.startsWith("@")) continue;
                int tagsEnd = line.indexOf(' ');
                if (tagsEnd < 0 || line.indexOf(" ROOMSTATE #", tagsEnd) < 0) continue;
                String roomId = tag(line.substring(1, tagsEnd), "room-id");
                if (roomId == null || roomId.isEmpty()) continue;
                int id = Integer.parseInt(roomId);
                if (id <= 0 || Data.ctx == null || id == Data.currentBroadcasterId) continue;
                Data.setCurrentBroadcasterId(id);
                if (++channelLogs <= 3) Log.i(TAG, "ROOMSTATE selected chat channel; channel catalog requested");
            }
        } catch (Throwable t) {
            Log.e(TAG, "ROOMSTATE handling failed; keeping Twitch behavior", t);
        }
    }

    /**
     * Prefix a PRIVMSG with [HH:mm] in device local time, using tmi-sent-ts.
     * Adjust the Twitch + BTTV emote ranges (IRC code-point offsets) so the
     * timestamp cannot make previously located emotes point at the wrong text.
     *
     * This deliberately skips /me CTCP ACTION messages because those have
     * different offset semantics. It also never changes non-PRIVMSG frames.
     */
    public static String addTimestamp(String line) {
        if (line == null || !line.startsWith("@")) return line;
        try {
            int tagsEnd = line.indexOf(' ');
            if (tagsEnd < 0) return line;
            int cmd = line.indexOf(" PRIVMSG #", tagsEnd);
            if (cmd < 0) return line;
            int start = line.indexOf(" :", cmd);
            if (start < 0) return line;
            start += 2;
            String body = line.substring(start);
            if (body.isEmpty() || body.charAt(0) == '\u0001') return line;
            if (body.matches("^\\[\\d{2}:\\d{2}\\] .*")) return line;
            String tags = line.substring(1, tagsEnd);
            String sentMs = tag(tags, "tmi-sent-ts");
            long timestamp = sentMs == null ? System.currentTimeMillis() : Long.parseLong(sentMs);
            if (timestamp < 1_000_000_000_000L || timestamp > System.currentTimeMillis() + 86_400_000L)
                return line;
            String prefix = "[" + new SimpleDateFormat("HH:mm", Locale.getDefault()).format(new Date(timestamp)) + "] ";
            int offset = prefix.codePointCount(0, prefix.length());
            String emotes = tag(tags, "emotes");
            if (emotes != null && !emotes.isEmpty()) {
                String shifted = shiftEmoteRanges(emotes, offset);
                if (shifted == null) return line; // Never corrupt a Twitch emote range.
                tags = replaceTag(tags, "emotes", shifted);
            }
            String result = "@" + tags + line.substring(tagsEnd, start) + prefix + body;
            if (++timestampLogs <= 3) Log.i(TAG, "React Native chat message timestamp inserted");
            return result;
        } catch (Throwable t) {
            Log.e(TAG, "Timestamp injection failed; forwarding original IRC", t);
            return line;
        }
    }

    private static String shiftEmoteRanges(String source, int amount) {
        StringBuilder out = new StringBuilder(source.length() + 32);
        for (String group : source.split("/", -1)) {
            int colon = group.indexOf(':');
            if (colon <= 0 || colon == group.length() - 1) return null;
            if (out.length() > 0) out.append('/');
            out.append(group, 0, colon + 1);
            String[] ranges = group.substring(colon + 1).split(",", -1);
            for (int i = 0; i < ranges.length; i++) {
                if (i > 0) out.append(',');
                String range = ranges[i];
                int dash = range.indexOf('-');
                if (dash <= 0 || dash == range.length() - 1) return null;
                int first = Integer.parseInt(range.substring(0, dash));
                int last = Integer.parseInt(range.substring(dash + 1));
                if (first < 0 || last < first || last > 1_000_000) return null;
                out.append(first + amount).append('-').append(last + amount);
            }
        }
        return out.toString();
    }

    private static String tag(String tags, String name) {
        String key = name + "=";
        int p = tags.startsWith(key) ? 0 : tags.indexOf(";" + key);
        if (p < 0) return null;
        int start = p + (p == 0 ? 0 : 1) + key.length();
        int end = tags.indexOf(';', start);
        return tags.substring(start, end < 0 ? tags.length() : end);
    }

    private static String replaceTag(String tags, String name, String value) {
        String key = name + "=";
        int p = tags.startsWith(key) ? 0 : tags.indexOf(";" + key);
        if (p < 0) return tags;
        int start = p + (p == 0 ? 0 : 1) + key.length();
        int end = tags.indexOf(';', start);
        return tags.substring(0, start) + value + (end < 0 ? "" : tags.substring(end));
    }
}
