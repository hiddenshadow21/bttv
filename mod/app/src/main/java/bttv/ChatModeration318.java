package bttv;

import android.content.Context;
import android.util.Log;

import bttv.settings.Settings;
import bttv.settings.UserPreferences;

/**
 * Retain chat messages that Twitch's IRC moderation notifications would remove.
 * Filter only the specific inbound moderation commands, without changing any
 * PRIVMSG body, badges, emote offsets, or the user's ability to send messages.
 *
 * CLEARMSG removes a single message; an untargeted CLEARCHAT clears all chat.
 * Targeted CLEARCHAT (ban/timeout) is left alone because it also carries
 * important viewer moderation state that should not be hidden from the client.
 */
public final class ChatModeration318 {
    private static final String TAG = "LBTTVDeleted318";
    private ChatModeration318() { }

    static boolean enabled() {
        Context context = Data.ctx;
        if (context == null) return false;
        try {
            return ((UserPreferences.Entry.BoolEntry) Settings.ShowDeletedMessagesEnabled.entry)
                    .get(context).get();
        } catch (Throwable error) {
            Log.w(TAG, "Could not read show-deleted-messages preference", error);
            return false;
        }
    }

    /** Called before processing IRC PRIVMSG emotes and timestamps. */
    public static String filterFrame(String frame) {
        if (frame == null || !enabled()) return frame;
        return filterFrame(frame, true);
    }

    /** Package-private pure transformation for regression tests. */
    static String filterFrame(String frame, boolean showDeleted) {
        if (!showDeleted || frame == null ||
                (!frame.contains(" CLEARMSG #") && !frame.contains(" CLEARCHAT #"))) {
            return frame;
        }
        String[] lines = frame.split("\\r\\n", -1);
        StringBuilder kept = new StringBuilder(frame.length());
        boolean removed = false;
        for (String line : lines) {
            if (line.isEmpty()) continue;
            if (isDeletionCommand(line)) {
                removed = true;
                continue;
            }
            if (kept.length() > 0) kept.append("\r\n");
            kept.append(line);
        }
        if (!removed) return frame;
        if (frame.endsWith("\r\n") && kept.length() > 0) kept.append("\r\n");
        Log.i(TAG, "Preserved live chat by ignoring an IRC deletion event");
        return kept.toString();
    }

    private static boolean isDeletionCommand(String line) {
        // Parse the actual IRC command instead of matching arbitrary substrings
        // in a user's message body (which could contain the word CLEARMSG).
        int index = 0;
        int length = line.length();
        if (length == 0) return false;
        if (line.charAt(index) == '@') {
            int endTags = line.indexOf(' ', index);
            if (endTags < 0) return false;
            index = endTags + 1;
        }
        if (index < length && line.charAt(index) == ':') {
            int endPrefix = line.indexOf(' ', index);
            if (endPrefix < 0) return false;
            index = endPrefix + 1;
        }
        int endCommand = line.indexOf(' ', index);
        if (endCommand < 0) return false;
        String command = line.substring(index, endCommand);
        if (!command.equals("CLEARMSG") && !command.equals("CLEARCHAT")) return false;
        int channelStart = endCommand + 1;
        if (channelStart >= length || line.charAt(channelStart) != '#') return false;
        if (command.equals("CLEARMSG")) return true;
        int endChannel = line.indexOf(' ', channelStart);
        // Targeted CLEARCHAT indicates a ban or timeout as well as a deletion.
        return endChannel < 0 || line.substring(endChannel).trim().isEmpty();
    }
}
