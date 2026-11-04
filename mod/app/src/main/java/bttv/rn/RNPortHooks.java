package bttv.rn;

import android.app.Activity;
import android.content.Context;
import android.util.Log;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;

import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;

import bttv.Data;
import bttv.Network;
import bttv.emote.Emotes;

/**
 * Twitch 31.8.0 React Native stage-1 hooks. The WebSocket and HTTP callbacks are
 * deliberately non-mutating until image and GraphQL response hooks are ready.
 * Never log raw chat contents, GQL request bodies, URIs, or credentials.
 */
public final class RNPortHooks {
    private static final String TAG = "BTTV318RN";
    private static final String LABEL = "BTTV 0.44.0-beta (Twitch 31.8.0)";
    private static final AtomicBoolean GLOBALS_REQUESTED = new AtomicBoolean();
    private static final AtomicInteger CHAT_FRAMES = new AtomicInteger();
    private static final AtomicInteger GQL_REQUESTS = new AtomicInteger();
    private static volatile int lastChannel = -1;

    private RNPortHooks() {}

    public static String onWebSocketText(int socketId, String frame) {
        try {
            int count = CHAT_FRAMES.incrementAndGet();
            if (count == 1) {
                Log.i(TAG, "React Native WebSocket hook active (first frame)");
            }
            if (count == 30 || count == 150) {
                Log.i(TAG, "Global catalog counts: BTTV=" + Emotes.globalEmotesBTTV.size()
                        + " FFZ=" + Emotes.globalEmotesFFZ.size()
                        + " 7TV=" + Emotes.globalEmotes7TV.size());
            }
            Context context = Data.ctx;
            if (context != null && GLOBALS_REQUESTED.compareAndSet(false, true)) {
                Log.i(TAG, "Starting BTTV/FFZ/7TV global catalog requests");
                try { Network.getBTTVGlobalEmotes(); }
                catch (Throwable t) { Log.e(TAG, "BTTV global request", t); }
                try { Network.getFFZGlobalEmotes(); }
                catch (Throwable t) { Log.e(TAG, "FFZ global request", t); }
                try { Network.get7TVGlobalEmotes(); }
                catch (Throwable t) { Log.e(TAG, "7TV global request", t); }
            }
            if (frame != null && frame.contains(" ROOMSTATE #")) {
                for (String line : frame.split("\\r?\\n")) {
                    int command = line.indexOf(" ROOMSTATE #");
                    int tagsEnd = line.indexOf(' ');
                    if (!line.startsWith("@") || command < 0 || tagsEnd <= 1) continue;
                    String tags = line.substring(1, tagsEnd);
                    String idText = getTag(tags, "room-id");
                    if (idText == null) continue;
                    int roomId = Integer.parseInt(idText);
                    if (roomId > 0 && roomId != lastChannel && context != null) {
                        lastChannel = roomId;
                        Data.setCurrentBroadcasterId(roomId);
                        Log.i(TAG, "Channel catalogs requested from ROOMSTATE");
                    }
                }
            }
        } catch (Throwable t) {
            // This hook must never break the host's React Native WebSocket delivery.
            Log.e(TAG, "WebSocket initialization failed", t);
        }
        return frame;
    }

    private static String getTag(String tags, String key) {
        String prefix = key + "=";
        int start = tags.startsWith(prefix) ? 0 : tags.indexOf(";" + prefix);
        if (start < 0) return null;
        if (start > 0) start++;
        start += prefix.length();
        int end = tags.indexOf(';', start);
        return tags.substring(start, end < 0 ? tags.length() : end);
    }

    public static void onHttpRequest(String method, String url) {
        try {
            if (url != null && url.contains("gql.twitch.tv")) {
                int count = GQL_REQUESTS.incrementAndGet();
                if (count == 1 || count == 10) {
                    Log.i(TAG, "React Native GraphQL request path active (count=" + count + ")");
                }
            }
        } catch (Throwable ignored) {
            // Observation is never allowed to change request behavior.
        }
    }

    public static void brandSettings(Activity activity) {
        if (activity == null) return;
        try {
            final View root = activity.getWindow().getDecorView();
            // Native footer may be added asynchronously after onResume.
            root.postDelayed(new Runnable() {
                @Override public void run() { updateVersion(root); }
            }, 200);
            root.postDelayed(new Runnable() {
                @Override public void run() { updateVersion(root); }
            }, 1200);
        } catch (Throwable t) {
            Log.w(TAG, "Version footer update failed", t);
        }
    }

    private static void updateVersion(View view) {
        try {
            if (view instanceof TextView) {
                TextView textView = (TextView) view;
                CharSequence value = textView.getText();
                if (value != null && value.toString().matches("Twitch v31\\.8\\.0.*")) {
                    textView.setText(LABEL);
                    Log.i(TAG, "Version TextView updated to BTTV branding");
                }
            }
            if (view instanceof ViewGroup) {
                ViewGroup group = (ViewGroup) view;
                for (int i = 0; i < group.getChildCount(); i++) {
                    updateVersion(group.getChildAt(i));
                }
            }
        } catch (Throwable t) {
            Log.w(TAG, "Version view scan failed", t);
        }
    }
}
