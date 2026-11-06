package bttv;

import android.content.Context;
import android.util.Log;

import java.util.concurrent.atomic.AtomicInteger;

import bttv.settings.Settings;
import bttv.settings.UserPreferences;

/**
 * Live-chat visibility gate for Twitch 31.8.0's existing React Native
 * TimestampPart component. The Hermes patch enables the separate timestamp
 * component before the badges; do not modify IRC display-name or chat body.
 *
 * Twitch's 31.8.0 JS renderer uses tmiSentTs as the timestamp source.
 * When the BTTV preference is off, remove that tag only from NEW PRIVMSGs.
 * This preserves chat/emote text offsets and leaves historical messages
 * untouched. Caveat: other JS uses of tmiSentTs on these new messages will
 * also receive an absent value while timestamps are switched off.
 */
public final class ChatTimestamps {
    private static final String TAG = "LBTTVTimestamps";
    private static final AtomicInteger frameDiagnostics = new AtomicInteger();

    private ChatTimestamps() { }

    private static boolean enabled() {
        Context context = Data.ctx;
        if (context == null) return true; // Do not strip server metadata during startup.
        try {
            return ((UserPreferences.Entry.BoolEntry)
                    Settings.AlwaysShowChatTimestamps.entry).get(context).get();
        } catch (Throwable t) {
            Log.w(TAG, "Cannot read BTTV timestamp preference; keeping IRC metadata", t);
            return true; // Fail open; never silently corrupt incoming chat metadata.
        }
    }

    /** Legacy native-chat compatibility. */
    public static boolean shouldShow(boolean nativeVisible) {
        return nativeVisible || enabled();
    }

    /** Called for IRC WebSocket frames after the emote handler. */
    public static String rewriteFrame(String frame) {
        if (frame == null || !frame.contains(" PRIVMSG #")) return frame;
        boolean show = enabled();
        if (frameDiagnostics.getAndIncrement() < 5) {
            Log.i(TAG, "Live PRIVMSG: enabled=" + show
                    + ", has-server-time=" + frame.contains("tmi-sent-ts="));
        }
        if (show) return frame;
        try {
            String[] lines = frame.split("\\r\\n", -1);
            StringBuilder out = new StringBuilder(frame.length());
            for (int i = 0; i < lines.length; i++) {
                if (i != 0) out.append("\r\n");
                out.append(withoutTimestampTag(lines[i]));
            }
            return out.toString();
        } catch (Throwable t) {
            Log.w(TAG, "Could not filter live timestamp; preserving IRC frame", t);
            return frame;
        }
    }

    /** IRCv3 tag-filter for incoming PRIVMSG only; never changes message text. */
    static String withoutTimestampTag(String line) {
        if (!line.startsWith("@")) return line;
        int sep = line.indexOf(' ');
        if (sep < 0 || line.indexOf(" PRIVMSG #", sep) < 0) return line;
        String tags = line.substring(1, sep);
        final String key = "tmi-sent-ts=";
        int idx = tags.startsWith(key) ? 0 : tags.indexOf(";" + key);
        if (idx < 0) return line;
        int valueStart = idx + (idx == 0 ? 0 : 1) + key.length();
        int end = tags.indexOf(';', valueStart);
        if (idx == 0) {
            // First tag, remove its following separator too.
            String rest = end == -1 ? "" : tags.substring(end + 1);
            return rest.isEmpty() ? line.substring(sep + 1) : "@" + rest + line.substring(sep);
        }
        // Middle or final tag: keep the preceding tags intact.
        return "@" + tags.substring(0, idx) +
                (end < 0 ? "" : tags.substring(end)) + line.substring(sep);
    }

    /**
     * Kept solely for the pre-existing RN smali hook from earlier rebase
     * patches. TimestampPart already supplies Twitch's own gray style and
     * native placement, so styling arbitrary RN chat spans is now disabled.
     */
    public static void styleText(CharSequence unused) { }
}
