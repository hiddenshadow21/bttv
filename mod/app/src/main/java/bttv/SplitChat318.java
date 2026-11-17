package bttv;

import android.content.Context;
import android.content.res.Configuration;
import android.graphics.Canvas;
import android.graphics.ColorFilter;
import android.graphics.Paint;
import android.graphics.PixelFormat;
import android.graphics.drawable.Drawable;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.view.View;

import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.WeakHashMap;

import bttv.settings.Settings;
import bttv.settings.UserPreferences;

/**
 * React Native split chat for Twitch 31.8.0.
 *
 * Hermes gives each chat message's outer view testID="chat-message-row".
 * BaseViewManager.setTestId notifies us when React creates or reuses one.
 *
 * React Native's backgrounds are CompositeBackgroundDrawable, NOT regular
 * ColorDrawable. Color changes must use its BackgroundStyleApplicator so RN's
 * own styling remains valid. The optional separator is a small ViewOverlay
 * drawable, independent of React's background lifecycle and layout.
 */
public final class SplitChat318 {
    private static final String TAG = "LBTTVSplitChat318";
    private static final String ROW_ID = "chat-message-row";
    public static final String SEPARATOR_PREF = "split_chat_separator_style";

    private static final int DARK_ALTERNATE = 0xFF29292F;
    private static final int LIGHT_ALTERNATE = 0xFFEDEDF0;
    private static final int DARK_SEPARATOR = 0xFF505059;
    private static final int LIGHT_SEPARATOR = 0xFFC3C3C9;
    private static final Handler MAIN = new Handler(Looper.getMainLooper());
    private static final WeakHashMap<View, Row> ROWS = new WeakHashMap<>();

    private static Method readBackground;
    private static Method writeBackground;
    private static boolean backgroundApiLookedUp;
    private static boolean scheduled;
    private static boolean loggedFirstTint;
    private static boolean loggedFirstLine;
    private static boolean loggedNoVisible;

    private SplitChat318() { }

    private static final class Row {
        Integer parity;
        Integer originalColor;
        Integer appliedColor;
        boolean ownsBackground;
        LineDecoration separator;
    }

    /** Called after React has set testID in BaseViewManager. */
    public static void onTestId(View view, String testId) {
        if (view == null) return;
        if (Looper.myLooper() != Looper.getMainLooper()) {
            MAIN.post(() -> onTestId(view, testId));
            return;
        }
        // The same verified RN testID hook also identifies the wrappers for
        // zero-width emotes; Split Chat itself still only styles chat rows.
        bttv.emote.WideEmotes.onWrapperTestId(view, testId);
        bttv.emote.StackedEmoteDetails.onTestId(view, testId);
        if (!ROW_ID.equals(testId)) {
            Row old = ROWS.remove(view);
            if (old != null) removeDecorations(view, old);
            return;
        }
        if (!ROWS.containsKey(view)) {
            Row state = new Row();
            ROWS.put(view, state);
            view.addOnAttachStateChangeListener(new View.OnAttachStateChangeListener() {
                @Override public void onViewAttachedToWindow(View v) { schedule(); }
                @Override public void onViewDetachedFromWindow(View v) {
                    Row s = ROWS.get(v);
                    if (s != null) {
                        removeDecorations(v, s);
                        s.parity = null;  // reused RN rows need a fresh position
                    }
                    schedule();
                }
            });
            view.addOnLayoutChangeListener((v, l, t, r, b, oldL, oldT, oldR, oldB) -> {
                Row s = ROWS.get(v);
                if (s != null && s.separator != null) {
                    s.separator.setBounds(0, 0, v.getWidth(), v.getHeight());
                }
                schedule();
            });
            Log.i(TAG, "Found RN chat-message-row; split chat=" + enabled(view.getContext()));
        }
        schedule();
    }

    /** Called after BTTV settings change; applies to already mounted rows. */
    public static void refresh() {
        if (Looper.myLooper() == Looper.getMainLooper()) schedule();
        else MAIN.post(SplitChat318::schedule);
    }

    private static Context context(Context fallback) {
        return Data.ctx == null ? fallback : Data.ctx;
    }

    private static boolean enabled(Context fallback) {
        Context ctx = context(fallback);
        if (ctx == null) return false;
        try {
            return ((UserPreferences.Entry.BoolEntry) Settings.SplitChatEnabled.entry)
                    .get(ctx).get();
        } catch (Throwable ex) {
            Log.w(TAG, "Cannot read split-chat preference", ex);
            return false;
        }
    }

    private static int separatorWidth(Context fallback) {
        Context ctx = context(fallback);
        if (ctx == null) return 0;
        try {
            String value = UserPreferences.getString(ctx, SEPARATOR_PREF, "none");
            if ("subtle".equals(value)) return 1;
            if ("strong".equals(value)) return 2;
        } catch (Throwable ex) {
            Log.w(TAG, "Cannot read separator preference", ex);
        }
        return 0;
    }

    private static void schedule() {
        if (scheduled) return;
        scheduled = true;
        MAIN.postDelayed(() -> {
            scheduled = false;
            update();
        }, 16);
    }

    /** Parity is anchored to an existing visible row, not the first index. */
    static int parityAt(int index, int knownIndex, int knownParity) {
        return (knownParity ^ ((index - knownIndex) & 1)) & 1;
    }

    private static void update() {
        if (ROWS.isEmpty()) return;
        View any = ROWS.keySet().iterator().next();
        if (any == null) return;
        boolean active = enabled(any.getContext());
        int separatorDp = active ? separatorWidth(any.getContext()) : 0;

        if (!active) {
            for (Map.Entry<View, Row> entry : new ArrayList<>(ROWS.entrySet())) {
                removeDecorations(entry.getKey(), entry.getValue());
                entry.getValue().parity = null;
            }
            return;
        }

        Map<View, List<View>> windows = new HashMap<>();
        for (View row : new ArrayList<>(ROWS.keySet())) {
            if (row != null && row.isAttachedToWindow() && row.isShown()
                    && row.getWidth() > 0 && row.getHeight() > 0) {
                windows.computeIfAbsent(row.getRootView(), k -> new ArrayList<>()).add(row);
            }
        }
        if (windows.isEmpty() && !loggedNoVisible) {
            loggedNoVisible = true;
            Log.i(TAG, "Chat rows registered, waiting for visible RN layout");
        }
        int[] xy = new int[2];
        for (List<View> visible : windows.values()) {
            Map<View, Integer> tops = new HashMap<>();
            for (View view : visible) {
                view.getLocationOnScreen(xy);
                tops.put(view, xy[1]);
            }
            visible.sort(Comparator.comparingInt(tops::get));
            int knownIndex = 0;
            int knownParity = 0;
            for (int i = 0; i < visible.size(); i++) {
                Row state = ROWS.get(visible.get(i));
                if (state != null && state.parity != null) {
                    knownIndex = i;
                    knownParity = state.parity;
                    break;
                }
            }
            for (int i = 0; i < visible.size(); i++) {
                View view = visible.get(i);
                Row state = ROWS.get(view);
                if (state == null) continue;
                int parity = parityAt(i, knownIndex, knownParity);
                state.parity = parity;
                updateBackground(view, state, parity != 0);
                updateSeparator(view, state, separatorDp);
            }
        }
    }

    private static void ensureBackgroundApi() {
        if (backgroundApiLookedUp) return;
        backgroundApiLookedUp = true;
        try {
            Class<?> cls = Class.forName("com.facebook.react.uimanager.BackgroundStyleApplicator");
            readBackground = cls.getMethod("getBackgroundColor", View.class);
            writeBackground = cls.getMethod("setBackgroundColor", View.class, Integer.class);
        } catch (Throwable error) {
            Log.w(TAG, "React Native BackgroundStyleApplicator unavailable", error);
        }
    }

    private static Integer background(View view) throws Exception {
        return (Integer) readBackground.invoke(null, view);
    }

    private static void setBackground(View view, Integer color) throws Exception {
        writeBackground.invoke(null, view, color);
    }

    private static void updateBackground(View view, Row state, boolean stripe) {
        ensureBackgroundApi();
        if (readBackground == null || writeBackground == null) return;
        try {
            Integer current = background(view);
            // RN has changed the background since our previous update: honor
            // a nontransparent native highlight instead of covering it.
            if (state.ownsBackground && !sameColor(current, state.appliedColor)) {
                state.ownsBackground = false;
                state.originalColor = null;
                state.appliedColor = null;
            }
            if (!stripe) {
                restoreBackground(view, state);
                return;
            }
            if (!state.ownsBackground) {
                // The JSX row uses no backgroundColor. If Twitch supplies an
                // explicit color (e.g. a highlighted message), leave it alone.
                if (current != null && current != 0) return;
                state.originalColor = current;
            }
            int night = view.getResources().getConfiguration().uiMode
                    & Configuration.UI_MODE_NIGHT_MASK;
            int wanted = night == Configuration.UI_MODE_NIGHT_YES
                    ? DARK_ALTERNATE : LIGHT_ALTERNATE;
            if (state.ownsBackground && sameColor(current, wanted)) return;
            setBackground(view, wanted);
            state.ownsBackground = true;
            state.appliedColor = wanted;
            if (!loggedFirstTint) {
                loggedFirstTint = true;
                Log.i(TAG, "Applied first alternating RN background through BackgroundStyleApplicator");
            }
        } catch (Throwable error) {
            Log.w(TAG, "Cannot update RN chat background", error);
        }
    }

    private static boolean sameColor(Integer a, Integer b) {
        return a == null ? b == null : a.equals(b);
    }

    private static void restoreBackground(View view, Row state) {
        if (!state.ownsBackground) return;
        try {
            if (readBackground != null && writeBackground != null
                    && sameColor(background(view), state.appliedColor)) {
                setBackground(view, state.originalColor);
            }
        } catch (Throwable error) {
            Log.w(TAG, "Cannot restore RN chat background", error);
        }
        state.ownsBackground = false;
        state.originalColor = null;
        state.appliedColor = null;
    }

    private static void updateSeparator(View view, Row state, int widthDp) {
        if (widthDp == 0) {
            removeSeparator(view, state);
            return;
        }
        boolean dark = (view.getResources().getConfiguration().uiMode
                & Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_YES;
        int px = Math.max(1, Math.round(widthDp * view.getResources().getDisplayMetrics().density));
        int color = dark ? DARK_SEPARATOR : LIGHT_SEPARATOR;
        if (state.separator == null) {
            state.separator = new LineDecoration(px, color);
            view.getOverlay().add(state.separator);
            if (!loggedFirstLine) {
                loggedFirstLine = true;
                Log.i(TAG, "Applied first RN chat separator");
            }
        } else {
            state.separator.update(px, color);
        }
        state.separator.setBounds(0, 0, view.getWidth(), view.getHeight());
    }

    private static void removeSeparator(View view, Row state) {
        if (state.separator == null) return;
        view.getOverlay().remove(state.separator);
        state.separator = null;
    }

    private static void removeDecorations(View view, Row state) {
        restoreBackground(view, state);
        removeSeparator(view, state);
    }

    /** Draw just the bottom separator above the RN row without changing layout. */
    private static final class LineDecoration extends Drawable {
        private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
        private int thickness;

        LineDecoration(int thickness, int color) {
            update(thickness, color);
        }

        void update(int thickness, int color) {
            this.thickness = thickness;
            paint.setColor(color);
            invalidateSelf();
        }

        @Override public void draw(Canvas canvas) {
            int bottom = getBounds().bottom;
            if (bottom <= 0 || getBounds().right <= 0) return;
            canvas.drawRect(0, Math.max(0, bottom - thickness), getBounds().right, bottom, paint);
        }

        @Override public void setAlpha(int alpha) { paint.setAlpha(alpha); invalidateSelf(); }
        @Override public void setColorFilter(ColorFilter filter) {
            paint.setColorFilter(filter); invalidateSelf();
        }
        @Override public int getOpacity() { return PixelFormat.TRANSLUCENT; }
    }
}
