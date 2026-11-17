package bttv.emote;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.content.ContextWrapper;
import android.graphics.Color;
import android.util.Log;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.ViewParent;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import com.bumptech.glide.Glide;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.WeakHashMap;

/**
 * A zero-width emote is another real emote over the preceding image. Hermes's
 * EmotePart.onPress, however, only knows one emoteId and opens one EmoteCard.
 * The verified BaseViewManager.setTestId hook exposes the press Text and image
 * wrapper views. For a stacked emote only, intercept the tap and show both
 * emotes together. All ordinary Twitch/BTTV/FFZ/7TV emotes retain the native
 * React Native card handler.
 */
public final class StackedEmoteDetails {
    private static final String TAG = "LBTTVStackedCards";
    private static final String PRESS_PREFIX = "chat-emote-press-";
    private static final String WRAPPER_PREFIX = "chat-emote-wrapper-";
    private static final String ROW_ID = "chat-message-row";
    private static final String PRESSABLE_ID = "chat-message-pressable";
    private static final int MAX_VIEWS = 512;
    private static final int BG = 0xFF18181B;
    private static final int FG = Color.WHITE;
    private static final int SECONDARY = 0xFFADADB8;

    private static final Map<View, Boolean> INSTALLED =
            Collections.synchronizedMap(new WeakHashMap<View, Boolean>());
    private static final Map<View, Stack> ARMED =
            Collections.synchronizedMap(new WeakHashMap<View, Stack>());
    private static boolean firstLogged;

    private StackedEmoteDetails() { }

    /** Called on the UI thread by the already-installed RN testID hook. */
    public static void onTestId(View view, String id) {
        if (view == null || id == null) return;
        if (!id.startsWith(PRESS_PREFIX) && !id.startsWith(WRAPPER_PREFIX)) {
            ARMED.remove(view); // recycled Fabric node
            return;
        }
        if (INSTALLED.put(view, Boolean.TRUE) != null) return;
        view.setOnTouchListener((target, event) -> handleTouch(target, event));
        if (!firstLogged) {
            firstLogged = true;
            Log.i(TAG, "Stacked emote details touch hook installed");
        }
    }

    private static boolean handleTouch(View target, MotionEvent event) {
        switch (event.getActionMasked()) {
            case MotionEvent.ACTION_DOWN: {
                // Do not consume or change the native emote card for normal
                // emotes; we only claim a touch when two or more are stacked.
                Stack stack = stackAt(target);
                if (stack == null) return false;
                ARMED.put(target, stack);
                Log.i(TAG, "Intercepted stacked emote tap; entries=" + stack.ids.size());
                return true;
            }
            case MotionEvent.ACTION_UP: {
                Stack stack = ARMED.remove(target);
                if (stack == null) return false;
                if (event.getX() >= -16 && event.getY() >= -16
                        && event.getX() <= target.getWidth() + 16
                        && event.getY() <= target.getHeight() + 16) {
                    show(target, stack);
                }
                return true;
            }
            case MotionEvent.ACTION_CANCEL:
                return ARMED.remove(target) != null;
            case MotionEvent.ACTION_MOVE:
                return ARMED.containsKey(target);
            default:
                return ARMED.containsKey(target);
        }
    }

    /** Resolve the stack from this exact chat row, not from all visible rows. */
    private static Stack stackAt(View pressed) {
        String pressedId = viewId(pressed);
        if (pressedId == null) return null;
        String id;
        if (pressedId.startsWith(PRESS_PREFIX)) id = pressedId.substring(PRESS_PREFIX.length());
        else if (pressedId.startsWith(WRAPPER_PREFIX)) id = pressedId.substring(WRAPPER_PREFIX.length());
        else return null;

        ViewGroup row = null;
        ViewGroup pressable = null;
        View cursor = pressed;
        for (int depth = 0; cursor != null && depth < 32; depth++) {
            String testId = viewId(cursor);
            if (ROW_ID.equals(testId) && cursor instanceof ViewGroup) {
                row = (ViewGroup) cursor;
                break;
            }
            if (PRESSABLE_ID.equals(testId) && cursor instanceof ViewGroup) {
                pressable = (ViewGroup) cursor;
            }
            ViewParent parent = cursor.getParent();
            cursor = parent instanceof View ? (View) parent : null;
        }
        ViewGroup root = row != null ? row : pressable;
        if (root == null) return null;

        List<Wrapper> found = new ArrayList<>();
        collect(root, found, new int[]{0});
        if (found.size() < 2) return null;
        int pressedIndex = findPressedIndex(pressed, id, found);
        if (pressedIndex < 0) return null;
        return findStack(ids(found), pressedIndex);
    }

    private static List<String> ids(List<Wrapper> wrappers) {
        List<String> ids = new ArrayList<>(wrappers.size());
        for (Wrapper w : wrappers) ids.add(w.emoteId);
        return ids;
    }

    /** Pure function: enables deterministic tests for chains and repeated emote IDs. */
    static Stack findStack(List<String> ids, int index) {
        if (index < 0 || index >= ids.size()) return null;
        int base = index;
        while (base > 0 && isOverlay(ids.get(base))) base--;
        if (isOverlay(ids.get(base))) return null; // orphan overlay
        int end = base + 1;
        while (end < ids.size() && isOverlay(ids.get(end))) end++;
        if (end - base < 2 || index >= end) return null;
        return new Stack(new ArrayList<>(ids.subList(base, end)));
    }

    private static boolean isOverlay(String id) {
        return EmoteUrlUtil.overlayBaseSteps(id) >= 0;
    }

    static final class Stack {
        final List<String> ids;
        Stack(List<String> ids) { this.ids = ids; }
    }

    private static final class Wrapper {
        final View view;
        final String emoteId;
        Wrapper(View view, String emoteId) {
            this.view = view;
            this.emoteId = emoteId;
        }
    }

    private static void collect(View node, List<Wrapper> list, int[] visited) {
        if (++visited[0] > MAX_VIEWS) return;
        String tag = viewId(node);
        if (tag != null && tag.startsWith(WRAPPER_PREFIX)) {
            list.add(new Wrapper(node, tag.substring(WRAPPER_PREFIX.length())));
        }
        if (node instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) node;
            for (int i = 0; i < group.getChildCount() && visited[0] < MAX_VIEWS; i++) {
                collect(group.getChildAt(i), list, visited);
            }
        }
    }

    private static int findPressedIndex(View pressed, String id, List<Wrapper> wrappers) {
        // The React Text onPress normally wraps this inline image. Prefer
        // its own descendant when the same ID appears more than once.
        int best = -1;
        long closest = Long.MAX_VALUE;
        int[] pressedXY = new int[2];
        int[] wrapperXY = new int[2];
        pressed.getLocationOnScreen(pressedXY);
        for (int i = 0; i < wrappers.size(); i++) {
            Wrapper wrapper = wrappers.get(i);
            if (!id.equals(wrapper.emoteId)) continue;
            if (wrapper.view == pressed || isDescendant(wrapper.view, pressed)) return i;
            wrapper.view.getLocationOnScreen(wrapperXY);
            long dx = (long) wrapperXY[0] - pressedXY[0];
            long dy = (long) wrapperXY[1] - pressedXY[1];
            long squared = dx * dx + dy * dy;
            if (squared < closest) {
                closest = squared;
                best = i;
            }
        }
        return best;
    }

    private static boolean isDescendant(View child, View ancestor) {
        ViewParent parent = child.getParent();
        for (int depth = 0; parent != null && depth < 24; depth++) {
            if (parent == ancestor) return true;
            parent = parent.getParent();
        }
        return false;
    }

    private static String viewId(View view) {
        Object tag = view.getTag();
        if (!(tag instanceof String)) tag = view.getTag(0x7f0b10ab);
        return tag instanceof String ? (String) tag : null;
    }

    private static Activity activity(Context ctx) {
        for (int n = 0; ctx != null && n < 24; n++) {
            if (ctx instanceof Activity) {
                Activity a = (Activity) ctx;
                return a.isFinishing() || a.isDestroyed() ? null : a;
            }
            // RN ThemedReactContext commonly wraps the application context,
            // NOT the Activity, so unwrapping it alone is insufficient.
            try {
                Object current = ctx.getClass().getMethod("getCurrentActivity").invoke(ctx);
                if (current instanceof Activity) {
                    Activity a = (Activity) current;
                    if (!a.isFinishing() && !a.isDestroyed()) return a;
                }
            } catch (ReflectiveOperationException ignored) { }
            if (!(ctx instanceof ContextWrapper)) return null;
            Context next = ((ContextWrapper) ctx).getBaseContext();
            if (next == ctx) return null;
            ctx = next;
        }
        return null;
    }

    private static int dp(Context context, float size) {
        return Math.round(context.getResources().getDisplayMetrics().density * size);
    }

    private static void show(View view, Stack stack) {
        Activity host = activity(view.getContext());
        if (host == null) {
            Log.w(TAG, "Cannot open stacked emote card: no live Activity");
            return;
        }
        try {
            LinearLayout content = new LinearLayout(host);
            content.setOrientation(LinearLayout.VERTICAL);
            content.setPadding(dp(host, 20), dp(host, 8), dp(host, 20), dp(host, 12));
            content.setBackgroundColor(BG);
            for (int i = 0; i < stack.ids.size(); i++) {
                addEmoteRow(host, content, stack.ids.get(i), i == 0 ? "Base emote" : "Zero-width overlay");
            }
            ScrollView scroll = new ScrollView(host);
            scroll.setFillViewport(false);
            scroll.addView(content);
            new AlertDialog.Builder(host)
                    .setTitle("Stacked emotes")
                    .setView(scroll)
                    .setPositiveButton("Close", null)
                    .show();
            Log.i(TAG, "Opened combined details for " + stack.ids.size() + " stacked emotes");
        } catch (Throwable t) {
            Log.e(TAG, "Unable to open stacked emote details", t);
        }
    }

    private static void addEmoteRow(Context context, LinearLayout root, String emoteId, String role) {
        String realId = EmoteUrlUtil.extractBTTVId(emoteId);
        Emote emote = realId == null ? null : Emotes.getEmoteById(realId);
        String name = emote == null ? "Twitch emote #" + emoteId : emote.code;
        String source = emote == null ? "Twitch" : provider(emote);
        String uri = emote == null
                ? "https://static-cdn.jtvnw.net/emoticons/v2/" + emoteId + "/default/dark/2.0"
                : emote.url;

        TextView heading = new TextView(context);
        heading.setText(role);
        heading.setTextColor(SECONDARY);
        heading.setTextSize(12);
        heading.setPadding(0, dp(context, 13), 0, dp(context, 5));
        root.addView(heading);

        LinearLayout line = new LinearLayout(context);
        line.setOrientation(LinearLayout.HORIZONTAL);
        line.setGravity(android.view.Gravity.CENTER_VERTICAL);
        ImageView image = new ImageView(context);
        image.setScaleType(ImageView.ScaleType.FIT_CENTER);
        line.addView(image, new LinearLayout.LayoutParams(dp(context, 72), dp(context, 72)));
        try {
            Glide.with(context).load(uri).into(image);
        } catch (Throwable t) {
            Log.w(TAG, "Could not load stacked emote preview", t);
        }
        LinearLayout labels = new LinearLayout(context);
        labels.setOrientation(LinearLayout.VERTICAL);
        labels.setPadding(dp(context, 12), 0, 0, 0);
        TextView title = new TextView(context);
        title.setText(name);
        title.setTextColor(FG);
        title.setTextSize(17);
        labels.addView(title);
        TextView provider = new TextView(context);
        provider.setText(source + (emote != null && emote.owner != null && !emote.owner.isEmpty()
                ? " · by " + emote.owner : ""));
        provider.setTextColor(SECONDARY);
        provider.setTextSize(13);
        labels.addView(provider);
        line.addView(labels, new LinearLayout.LayoutParams(0, -2, 1f));
        root.addView(line);
    }

    private static String provider(Emote emote) {
        switch (emote.source) {
            case STV: return "7TV";
            case FFZ: return "FrankerFaceZ";
            default: return "BetterTTV";
        }
    }
}
