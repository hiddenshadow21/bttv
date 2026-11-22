package bttv.emote;

import android.util.Log;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.ViewParent;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.WeakHashMap;

/**
 * Captures stack context without consuming a React Native emote press.
 * Twitch's EXISTING EmoteCard sheet renders the information. No second dialog.
 */
public final class StackedEmoteDetails {
    private static final String TAG = "LBTTVStackedCards";
    private static final String PRESS_PREFIX = "chat-emote-press-";
    private static final String WRAPPER_PREFIX = "chat-emote-wrapper-";
    private static final String ROW_ID = "chat-message-row";
    private static final String PRESSABLE_ID = "chat-message-pressable";
    private static final int MAX_VIEWS = 512;
    private static final long PENDING_MS = 5000L;
    private static final long CARD_MS = 15000L;

    private static final Map<View, Boolean> INSTALLED =
            Collections.synchronizedMap(new WeakHashMap<View, Boolean>());
    private static final Map<String, String> TWITCH_NAMES =
            Collections.synchronizedMap(new LinkedHashMap<String, String>(512, .75f, true) {
                @Override protected boolean removeEldestEntry(Map.Entry<String, String> entry) {
                    return size() > 512;
                }
            });

    private static volatile Stack pending;
    private static volatile long pendingUntil;
    private static volatile Stack card;
    private static volatile long cardUntil;

    private StackedEmoteDetails() { }

    /** Called on the UI thread by the existing BaseViewManager.setTestId hook. */
    public static void onTestId(View view, String id) {
        if (view == null || id == null) return;
        if (!id.startsWith(PRESS_PREFIX) && !id.startsWith(WRAPPER_PREFIX)) return;
        if (INSTALLED.put(view, Boolean.TRUE) != null) return;
        view.setOnTouchListener((target, event) -> {
            if (event.getActionMasked() == MotionEvent.ACTION_DOWN) {
                Stack stack = stackAt(target);
                pending = stack;
                if (stack != null) {
                    pendingUntil = System.currentTimeMillis() + PENDING_MS;
                    Log.i(TAG, "Stacked emote pressed; native EmoteCard will handle it, count=" + stack.ids.size());
                }
            }
            // Never consume: RN's original onPress must open the native sheet.
            return false;
        });
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

    /** Match the original GraphQL card request to the recent native touch. */
    public static Stack onCardRequest(String requestedId) {
        Stack selected = pending;
        long now = System.currentTimeMillis();
        pending = null;
        if (selected != null && requestedId != null && now <= pendingUntil
                && selected.ids.contains(requestedId)) {
            card = selected;
            cardUntil = now + CARD_MS;
            Log.i(TAG, "Native EmoteCard request matched a stack of " + selected.ids.size());
            return selected;
        }
        card = null;
        return null;
    }

    public static Stack activeCard() {
        if (System.currentTimeMillis() <= cardUntil) return card;
        card = null;
        return null;
    }

    public static String cardTitle(String requestedId, String ordinaryName) {
        Stack selected = activeCard();
        if (selected == null || (requestedId != null && !selected.ids.contains(requestedId))) {
            return ordinaryName;
        }
        StringBuilder out = new StringBuilder();
        for (String id : selected.ids) {
            if (out.length() > 0) out.append(" + ");
            out.append(name(id));
        }
        return out.toString();
    }

    /** Provider/source labels for the EXISTING Twitch sheet's type caption. */
    public static String cardOrigins() {
        Stack selected = activeCard();
        if (selected == null) return null;
        StringBuilder out = new StringBuilder();
        for (String id : selected.ids) {
            if (out.length() > 0) out.append(" + ");
            out.append(origin(id));
        }
        return out.toString();
    }

    public static String cardDescription() {
        Stack selected = activeCard();
        if (selected == null) return null;
        StringBuilder out = new StringBuilder();
        for (int i = 0; i < selected.ids.size(); i++) {
            if (i > 0) out.append('\n');
            String id = selected.ids.get(i);
            out.append(i == 0 ? "Base: " : "Overlay: ");
            out.append(name(id)).append(" · ").append(origin(id));
        }
        return out.toString();
    }

    public static String name(String id) {
        String real = EmoteUrlUtil.extractBTTVId(id);
        if (real != null) {
            Emote e = Emotes.getEmoteById(real);
            if (e != null && e.code != null) return e.code;
        }
        String cached = TWITCH_NAMES.get(id);
        return cached != null ? cached : "Twitch emote";
    }

    public static String origin(String id) {
        String real = EmoteUrlUtil.extractBTTVId(id);
        Emote emote = real == null ? null : Emotes.getEmoteById(real);
        return emote == null ? "Twitch emote" : RNEmoteCard.providerAndScope(emote);
    }

    /** Cache Twitch-native names from IRC tag ranges; do not retain messages. */
    public static void rememberTwitchEmotes(String message, String emotesTag) {
        if (message == null || emotesTag == null || emotesTag.isEmpty()) return;
        for (String entry : emotesTag.split("/")) {
            int colon = entry.indexOf(':');
            if (colon < 1 || colon >= entry.length() - 1) continue;
            String id = entry.substring(0, colon);
            if (id.startsWith("BTTV-")) continue;
            String first = entry.substring(colon + 1).split(",", 2)[0];
            int dash = first.indexOf('-');
            if (dash < 1) continue;
            try {
                int start = Integer.parseInt(first.substring(0, dash));
                int end = Integer.parseInt(first.substring(dash + 1));
                int total = message.codePointCount(0, message.length());
                if (start < 0 || end < start || end >= total || end - start > 80) continue;
                int from = message.offsetByCodePoints(0, start);
                int to = message.offsetByCodePoints(0, end + 1);
                TWITCH_NAMES.put(id, message.substring(from, to));
            } catch (NumberFormatException | IndexOutOfBoundsException ignored) { }
        }
    }
}
