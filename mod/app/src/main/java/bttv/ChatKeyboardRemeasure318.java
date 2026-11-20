package bttv;

import android.graphics.Rect;
import android.os.Build;
import android.util.Log;
import android.view.View;
import android.view.WindowInsets;

import java.lang.ref.WeakReference;
import java.lang.reflect.Method;
import java.util.WeakHashMap;

/**
 * Experimental, theatre-only Android 31.8.0 IME resize workaround.
 *
 * This does NOT modify keyboard/window soft-input flags or recreate the stream.
 * If the full-screen RN theatre view changes height when the IME opens/closes,
 * ask Twitch's existing RN surface controller to remeasure once after layout.
 * In particular, only request a remeasure when at least one endpoint had the
 * IME visible, so normal player/overlay changes are not affected.
 *
 * The public controller/mini-player method names are pinned to the unmodified
 * Twitch 31.8.0 smali. Reflection avoids linking Twitch classes in mod Java.
 */
public final class ChatKeyboardRemeasure318 {
    private static final String TAG = "BTTVChatResize318";
    private static final WeakHashMap<View, Watcher> WATCHERS = new WeakHashMap<>();

    private ChatKeyboardRemeasure318() {}

    public static void install(View theatreRoot, Object surfaceController, Object miniPlayer) {
        Log.i(TAG, "install invoked; root=" + (theatreRoot != null)
                + " surface=" + (surfaceController != null)
                + " mini=" + (miniPlayer != null));
        if (theatreRoot == null || surfaceController == null || miniPlayer == null) {
            Log.w(TAG, "theatre resize listener not installed: missing dependency");
            return;
        }
        synchronized (WATCHERS) {
            Watcher old = WATCHERS.remove(theatreRoot);
            if (old != null) theatreRoot.removeOnLayoutChangeListener(old);
            Watcher watcher = new Watcher(theatreRoot, surfaceController, miniPlayer);
            WATCHERS.put(theatreRoot, watcher);
            theatreRoot.addOnLayoutChangeListener(watcher);
            Log.i(TAG, "installed theatre layout watcher; height=" + theatreRoot.getHeight()
                    + " ime=" + imeVisible(theatreRoot)
                    + " mini=" + isMinimized(miniPlayer));
        }
    }

    public static void uninstall(View theatreRoot) {
        if (theatreRoot == null) return;
        synchronized (WATCHERS) {
            Watcher old = WATCHERS.remove(theatreRoot);
            if (old != null) {
                theatreRoot.removeOnLayoutChangeListener(old);
                Log.i(TAG, "removed theatre layout watcher");
            }
        }
    }

    private static boolean isMinimized(Object miniPlayer) {
        if (miniPlayer == null) return true;
        try {
            Object value = miniPlayer.getClass().getMethod("isMinimized").invoke(miniPlayer);
            return Boolean.TRUE.equals(value);
        } catch (Throwable t) {
            // Fail closed, but NEVER silently swallow an unexpected method.
            Log.w(TAG, "MiniPlayerController.isMinimized unavailable: "
                    + t.getClass().getSimpleName());
            return true;
        }
    }

    private static Boolean imeVisible(View root) {
        if (Build.VERSION.SDK_INT < 30) return null;
        try {
            WindowInsets insets = root.getRootWindowInsets();
            if (insets == null) return null;
            return insets.isVisible(WindowInsets.Type.ime());
        } catch (Throwable ignored) {
            return null;
        }
    }

    private static final class Watcher implements View.OnLayoutChangeListener {
        private final WeakReference<View> root;
        private final WeakReference<Object> controller;
        private final WeakReference<Object> miniPlayer;
        private Boolean lastIme;
        private boolean pending;

        Watcher(View root, Object controller, Object miniPlayer) {
            this.root = new WeakReference<>(root);
            this.controller = new WeakReference<>(controller);
            this.miniPlayer = new WeakReference<>(miniPlayer);
            this.lastIme = imeVisible(root);
        }

        @Override
        public void onLayoutChange(View view, int left, int top, int right, int bottom,
                                   int oldLeft, int oldTop, int oldRight, int oldBottom) {
            final int height = bottom - top;
            final int oldHeight = oldBottom - oldTop;
            final Boolean previousIme = lastIme;
            final Boolean nowIme = imeVisible(view);
            lastIme = nowIme;
            if (oldHeight <= 0 || height <= 0 || height == oldHeight) return;
            Log.i(TAG, "theatre layout changed: height=" + oldHeight + "->" + height
                    + " ime=" + previousIme + "->" + nowIme);

            // Ignore small video/decoration adjustments. A keyboard typically
            // changes height by hundreds of dp; this threshold is 120 dp.
            float density = view.getResources().getDisplayMetrics().density;
            if (Math.abs(height - oldHeight) < Math.max(1, (int) (120f * density))) return;

            // On Android, IME insets can be dispatched AFTER the layout resize.
            // A large theatre-height change is the reliable signal here;
            // previousIme/nowIme are diagnostic only, never a suppressing gate.
            if (isMinimized(miniPlayer.get())) {
                Log.i(TAG, "skipped RN remeasure: player still minimized");
                return;
            }
            if (pending) return;

            Log.i(TAG, "requesting RN remeasure after keyboard-related theatre height change");
            pending = true;
            final View theatre = root.get();
            if (theatre == null) {
                pending = false;
                return;
            }
            theatre.post(new Runnable() {
                @Override
                public void run() {
                    pending = false;
                    if (!theatre.isAttachedToWindow() || isMinimized(miniPlayer.get())) {
                        return;
                    }
                    Object target = controller.get();
                    if (target == null) return;
                    try {
                        Method method = target.getClass().getMethod("kickRemeasure");
                        method.invoke(target);
                        Log.i(TAG, "IME-height transition: requested RN theatre remeasure");
                    } catch (Throwable t) {
                        Log.w(TAG, "RN surface remeasure unavailable: " + t.getClass().getSimpleName());
                    }
                }
            });
        }
    }
}
