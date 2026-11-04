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
     * Display the timestamp alongside the sender name, never inside the message body.
     * The React Native chat renderer uses IRC display-name for the username label.
     * We escape the separator with IRCv3 \s and leave the login and user-id intact.
     * This is an RN data-level workaround, not a separate timestamp component.
     */
    public static String addTimestamp(String line) {
        if (line == null || !line.startsWith("@")) return line;
        try {
            int tagsEnd = line.indexOf(' ');
            if (tagsEnd < 0 || line.indexOf(" PRIVMSG #", tagsEnd) < 0) return line;
            String tags = line.substring(1, tagsEnd);
            String displayName = tag(tags, "display-name");
            if (displayName == null || displayName.isEmpty()) return line;
            if (displayName.startsWith("[")) return line;
            String sentMs = tag(tags, "tmi-sent-ts");
            if (sentMs == null) return line;
            long timestamp = Long.parseLong(sentMs);
            long now = System.currentTimeMillis();
            if (timestamp < 1_000_000_000_000L || timestamp > now + 86_400_000L) return line;
            String prefix = "[" + new SimpleDateFormat("HH:mm", Locale.getDefault()).format(new Date(timestamp)) + "]";
            // The IRCv3 space escape is two ASCII characters, backslash and s.
            String result = "@" + replaceTag(tags, "display-name", prefix + "\\s" + displayName)
                    + line.substring(tagsEnd);
            if (++timestampLogs <= 3) Log.i(TAG, "Timestamp moved to sender display label");
            return result;
        } catch (Throwable t) {
            Log.e(TAG, "Sender timestamp injection failed; forwarding original IRC", t);
            return line;
        }
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
