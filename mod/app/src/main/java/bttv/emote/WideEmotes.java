package bttv.emote;

import android.util.Log;
import android.view.View;
import android.view.ViewGroup;
import android.view.ViewParent;
import android.view.ViewTreeObserver;

import java.lang.reflect.Method;
import java.util.Collections;
import java.util.Map;
import java.util.WeakHashMap;

/**
 * The react native chat gives every emote a square slot, emotes that are wider than high
 * would be shrunk to fit. Three parts work together to show them at full height:
 * - IrcEmotes puts an invisible marker behind a wide emote, its length tells how wide the emote is,
 *   and gives the emote an id that starts with EmoteUrlUtil.WIDE_PREFIX
 * - the text layout reserves a wider slot, if the inline view is followed by the marker
 * - the image view of the emote is made as wide as the slot
 */
public class WideEmotes {
    private static final String TAG = "LBTTVWideEmotes";
    // word joiner, has no width and is not a place to break a line
    private static final char MARKER = '⁠';
    // U+2063 is invisible to the user, but is different from the wide-emote
    // word joiner. RN inline spans followed by it reserve a minimal 1px slot.
    public static final String OVERLAY_MARKER = "\u2063";
    private static final char OVERLAY_CHAR = '\u2063';
    private static final float MIN_RATIO = 1.2f;
    private static final float MAX_RATIO = 4f;
    private static final int STEPS_PER_HEIGHT = 4;
    private static final String EMOTE_URL_MARKER = "/emoticons/v2/";

    // image views that currently show a wide emote
    private static final Map<View, Float> wideViews = Collections.synchronizedMap(new WeakHashMap<View, Float>());
    // Parent wrapper needs the offset, because React Native owns image layout.
    private static final Map<View, OverlayLayout> overlayWrappers = Collections.synchronizedMap(new WeakHashMap<View, OverlayLayout>());
    private static final class OverlayLayout {
        final float baseRatio;
        final float imageRatio;
        OverlayLayout(float baseRatio, float imageRatio) {
            this.baseRatio = baseRatio;
            this.imageRatio = imageRatio;
        }
    }
    private static final Map<View, Boolean> wrapperListeners = Collections.synchronizedMap(new WeakHashMap<View, Boolean>());
    private static final String WRAPPER_TEST_ID = "chat-emote-wrapper-";
    private static Method getViewExists;
    private static Method getView;
    private static int logged = 0;
    private static int loggedOverlays = 0;
    private static int loggedOverlayPositions = 0;
    private static int loggedOverlayMissingBases = 0;
    private static final String CHAT_EMOTE_TEST_ID = "chat-emote-";
    // the emote card has a square slot for the emote, the text is next to it
    private static final String EMOTE_CARD_TEST_ID = "chat-emote-card";

    /** marker to put behind the emote in the message, empty if it is not wide */
    public static String marker(Emote emote) {
        int steps = steps(emote.aspectRatio);
        if (steps == 0) {
            return "";
        }
        StringBuilder marker = new StringBuilder(steps);
        for (int i = 0; i < steps; i++) {
            marker.append(MARKER);
        }
        return marker.toString();
    }

    public static int steps(float aspectRatio) {
        if (aspectRatio < MIN_RATIO) {
            return 0;
        }
        float ratio = Math.min(aspectRatio, MAX_RATIO);
        return Math.max(1, Math.round((ratio - 1f) * STEPS_PER_HEIGHT));
    }

    public static float ratio(int steps) {
        return 1f + (float) steps / STEPS_PER_HEIGHT;
    }

    /**
     * @param text text an inline view is part of
     * @param end index behind the inline view
     * @param width width of the slot for the inline view
     * @return width to reserve
     */
    public static int inlineViewWidth(CharSequence text, int end, int width) {
        if (text != null && end >= 0 && end < text.length()
                && text.charAt(end) == OVERLAY_CHAR) {
            // A literal zero-sized ReplacementSpan can make Android place the
            // next inline view at the start of a different line. A single
            // physical pixel is effectively zero width without that special
            // placement case. The wrapper is anchored to the base by sibling
            // coordinates, not by blindly subtracting an image width.
            // Log every occurrence in this diagnostic build. The previous
            // six-event cap hid later tests even when the hook kept firing.
            Log.d(TAG, "7TV zero-width RN inline text span: " + width + " -> 1");
            return 1;
        }
        if (text == null || end < 0 || end >= text.length() || text.charAt(end) != MARKER) {
            return width;
        }
        int steps = 0;
        while (end + steps < text.length() && text.charAt(end + steps) == MARKER) {
            steps++;
        }
        int newWidth = Math.round(width * ratio(steps));
        if (logged++ < 5) {
            Log.d(TAG, "inlineViewWidth: " + width + " -> " + newWidth);
        }
        return newWidth;
    }

    /**
     * @param view react native image view
     * @param sources ReadableArray of maps with an "uri"
     */
    public static void onImageViewSource(Object view, Object sources) throws Exception {
        if (!(view instanceof View)) {
            return;
        }
        Float ratio = null;
        String uri = firstUri(sources);
        if (uri != null) {
            int start = uri.indexOf(EMOTE_URL_MARKER);
            if (start != -1) {
                start += EMOTE_URL_MARKER.length();
                int end = uri.indexOf('/', start);
                String id = end == -1 ? uri.substring(start) : uri.substring(start, end);
                // Normal wide emotes and overlays both need their real image
                // width, even though an overlay has a zero-width text span.
                boolean overlay = EmoteUrlUtil.overlayBaseSteps(id) >= 0;
                String realId = overlay || id.startsWith(EmoteUrlUtil.WIDE_PREFIX)
                        ? EmoteUrlUtil.extractBTTVId(id) : null;
                Emote emote = realId == null ? null : Emotes.getEmoteById(realId);
                if (overlay && emote != null) {
                    ratio = Math.max(0.25f, Math.min(4f, emote.aspectRatio));
                } else if (emote != null && steps(emote.aspectRatio) > 0) {
                    ratio = ratio(steps(emote.aspectRatio));
                }
            }
        }
        if (ratio == null) {
            // views get reused
            if (!wideViews.isEmpty()) {
                wideViews.remove(view);
            }
        } else {
            wideViews.put((View) view, ratio);
        }
    }

    /**
     * The verified RN BaseViewManager.setTestId hook also sees emote wrappers.
     * Inline React views are siblings of chat-message-line within the same
     * chat-message-pressable. Text replacement spans don't guarantee that a
     * width-0 child stays on the same line: RN can lay out an overlay at the
     * *beginning of the next line*. Find the previous real emote wrapper in
     * this same parent and align to its real position in X AND Y.
     * Reset both transforms when Fabric recycles a wrapper for a new ID.
     */
    public static void onWrapperTestId(View view, String testId) {
        if (view == null) return;
        int baseSteps = -1;
        if (testId != null && testId.startsWith(WRAPPER_TEST_ID)) {
            String emoteId = testId.substring(WRAPPER_TEST_ID.length());
            baseSteps = EmoteUrlUtil.overlayBaseSteps(emoteId);
        }
        if (baseSteps < 0) {
            if (overlayWrappers.remove(view) != null) {
                view.setTranslationX(0f);
                view.setTranslationY(0f);
            }
            return;
        }
        String realId = EmoteUrlUtil.extractBTTVId(
                testId.substring(WRAPPER_TEST_ID.length()));
        Emote emote = realId == null ? null : Emotes.getEmoteById(realId);
        float imageRatio = emote == null ? 1f : Math.max(.25f, Math.min(4f, emote.aspectRatio));
        overlayWrappers.put(view, new OverlayLayout(ratio(baseSteps), imageRatio));
        // Do not cap this log: older builds stopped logging after four overlay
        // messages, making later device tests appear as though the hook died.
        Log.d(TAG, "7TV overlay wrapper registered: base steps=" + baseSteps);
        if (!wrapperListeners.containsKey(view)) {
            wrapperListeners.put(view, Boolean.TRUE);
            view.addOnLayoutChangeListener((v, l, t, r, b, oldL, oldT, oldR, oldB) -> {
                updateOverlay(v);
                // Siblings may receive their Fabric layouts after this wrapper.
                v.post(() -> updateOverlay(v));
            });
            // Fabric can mount the actual image wrappers after the overlay's
            // first layout. Re-anchor on global layout, not just the overlay's
            // own layout, so it is retried when its siblings appear later.
            final ViewTreeObserver.OnGlobalLayoutListener globalLayout =
                    () -> updateOverlay(view);
            view.addOnAttachStateChangeListener(new View.OnAttachStateChangeListener() {
                @Override public void onViewAttachedToWindow(View v) {
                    ViewTreeObserver observer = v.getViewTreeObserver();
                    if (observer.isAlive()) {
                        observer.removeOnGlobalLayoutListener(globalLayout);
                        observer.addOnGlobalLayoutListener(globalLayout);
                    }
                    v.post(() -> updateOverlay(v));
                }
                @Override public void onViewDetachedFromWindow(View v) {
                    ViewTreeObserver observer = v.getViewTreeObserver();
                    if (observer.isAlive()) observer.removeOnGlobalLayoutListener(globalLayout);
                }
            });
            view.getViewTreeObserver().addOnGlobalLayoutListener(globalLayout);
        }
        updateOverlay(view);
        view.post(() -> updateOverlay(view));
    }

    /**
     * The 31.8 Hermes ChatMessageRowComponent exposes chat-message-row and
     * EmotePart exposes chat-emote-wrapper-<id>. The inline attachments are
     * not guaranteed to be direct siblings: Fabric can insert ViewGroups
     * between them. Locate the preceding non-overlay emote within the *same*
     * chat row in mount order. Never search the RecyclerView / other rows.
     */
    private static View precedingBase(View view) {
        ViewGroup row = null;
        ViewGroup pressable = null;
        View cursor = view;
        for (int depth = 0; cursor != null && depth < 32; depth++) {
            String id = viewTestId(cursor);
            if ("chat-message-row".equals(id) && cursor instanceof ViewGroup) {
                row = (ViewGroup) cursor;
                break;
            }
            if ("chat-message-pressable".equals(id) && cursor instanceof ViewGroup) {
                pressable = (ViewGroup) cursor;
            }
            ViewParent parent = cursor.getParent();
            cursor = parent instanceof View ? (View) parent : null;
        }
        if (row != null || pressable != null) {
            View[] preceding = new View[1];
            if (findPrecedingBase(row != null ? row : pressable, view, preceding)) {
                return preceding[0];
            }
        }
        // Fallback for another RN chat hierarchy: direct-sibling scanning
        // is safe, whereas walking an arbitrary parent could cross rows.
        ViewParent parent = view.getParent();
        if (parent instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) parent;
            for (int i = group.indexOfChild(view) - 1; i >= 0; --i) {
                View candidate = group.getChildAt(i);
                if (isBaseEmote(candidate)) return candidate;
            }
        }
        return null;
    }

    /** Returns true once the target was found; keeps last base before it. */
    private static boolean findPrecedingBase(View node, View target, View[] preceding) {
        if (node == target) return true;
        if (isBaseEmote(node)) preceding[0] = node;
        if (node instanceof ViewGroup) {
            ViewGroup group = (ViewGroup) node;
            for (int i = 0, n = group.getChildCount(); i < n; i++) {
                if (findPrecedingBase(group.getChildAt(i), target, preceding)) return true;
            }
        }
        return false;
    }

    private static boolean isBaseEmote(View view) {
        String id = viewTestId(view);
        return id != null && id.startsWith(WRAPPER_TEST_ID)
                && EmoteUrlUtil.overlayBaseSteps(id.substring(WRAPPER_TEST_ID.length())) < 0;
    }

    private static String viewTestId(View view) {
        if (view == null) return null;
        // Verified against 31.8.0 BaseViewManager.setTestId: Twitch calls
        // setTag(Object) as well as setTag(0x7f0b10ab, Object). The generic
        // tag is reliable even if dynamic resource-name lookup fails.
        Object value = view.getTag();
        // This is the exact keyed resource in Twitch 31.8.0 smali; it also
        // helps if another RN component overwrites the unkeyed View tag.
        if (!(value instanceof String)) value = view.getTag(0x7f0b10ab);
        return value instanceof String ? (String) value : null;
    }

    private static void updateOverlay(View view) {
        OverlayLayout spec = overlayWrappers.get(view);
        if (spec == null || view.getHeight() <= 0 || view.getParent() == null) return;

        View base = precedingBase(view);
        if (base != null && base.getHeight() > 0) {
            // getLeft/getTop cannot be compared across nested ReactViewGroups.
            // Global coordinates include the existing translation, so remove
            // it to avoid drifting on repeated global-layout callbacks.
            int[] baseXY = new int[2];
            int[] overlayXY = new int[2];
            base.getLocationOnScreen(baseXY);
            view.getLocationOnScreen(overlayXY);
            float rawX = overlayXY[0] - view.getTranslationX();
            float rawY = overlayXY[1] - view.getTranslationY();
            float baseWidth = Math.max(base.getWidth(), base.getHeight() * spec.baseRatio);
            float overlayWidth = view.getWidth() > 0 ? view.getWidth()
                    : view.getHeight() * spec.imageRatio;
            float dx = baseXY[0] - rawX + (baseWidth - overlayWidth) / 2f;
            float dy = baseXY[1] - rawY
                    + (base.getHeight() - view.getHeight()) / 2f;
            if (view.getTranslationX() != dx) view.setTranslationX(dx);
            if (view.getTranslationY() != dy) view.setTranslationY(dy);
            // A translated inline image may cross a nested ViewGroup boundary.
            // Limit overflow enabling to the current chat row.
            allowOverlayOutsideNestedParents(view);
            if (loggedOverlayPositions++ < 24 || loggedOverlayPositions % 30 == 0) {
                Log.d(TAG, "7TV overlay anchored in chat row: dx=" + dx
                        + " dy=" + dy + " baseWidth=" + baseWidth);
            }
        } else {
            // The original blind -64px fallback displaced images into other
            // text and made failures hard to diagnose. Do not translate until
            // a real base is mounted; the global-layout listener will retry.
            view.setTranslationX(0f);
            view.setTranslationY(0f);
            if (loggedOverlayMissingBases++ < 24 || loggedOverlayMissingBases % 30 == 0) {
                Log.d(TAG, "7TV overlay waiting for preceding emote in chat row: parent="
                        + view.getParent().getClass().getSimpleName());
            }
        }
    }

    private static void allowOverlayOutsideNestedParents(View view) {
        ViewParent parent = view.getParent();
        for (int depth = 0; parent instanceof ViewGroup && depth < 16; depth++) {
            ViewGroup group = (ViewGroup) parent;
            group.setClipChildren(false);
            group.setClipToPadding(false);
            if ("chat-message-row".equals(viewTestId(group))) break;
            parent = group.getParent();
        }
    }

    // react native stores the testID of a view as a tag
    private static boolean isChatEmote(View view) {
        String id = viewTestId(view);
        if (id == null) return false;
        return id.startsWith(CHAT_EMOTE_TEST_ID) && !id.startsWith(EMOTE_CARD_TEST_ID);
    }

    private static String firstUri(Object sources) throws Exception {
        if (sources == null) {
            return null;
        }
        Class<?> array = Class.forName("com.facebook.react.bridge.ReadableArray");
        if ((Integer) array.getMethod("size").invoke(sources) != 1) {
            return null;
        }
        Object map = array.getMethod("getMap", int.class).invoke(sources, 0);
        if (map == null) {
            return null;
        }
        Class<?> readableMap = Class.forName("com.facebook.react.bridge.ReadableMap");
        if (!(Boolean) readableMap.getMethod("hasKey", String.class).invoke(map, "uri")) {
            return null;
        }
        return (String) readableMap.getMethod("getString", String.class).invoke(map, "uri");
    }

    /**
     * @param manager react native SurfaceMountingManager
     * @param tag tag of the view that gets its layout
     * @return width the view should get
     */
    public static int layoutWidth(Object manager, int tag, int width, int height) throws Exception {
        if (wideViews.isEmpty() && overlayWrappers.isEmpty()) {
            return width;
        }
        if (getView == null) {
            getViewExists = manager.getClass().getMethod("getViewExists", int.class);
            getView = manager.getClass().getMethod("getView", int.class);
        }
        if (!(Boolean) getViewExists.invoke(manager, tag)) {
            return width;
        }
        View view = (View) getView.invoke(manager, tag);
        OverlayLayout overlay = overlayWrappers.get(view);
        if (overlay != null) {
            // Keep the actual view at image size, even though the preceding
            // TextInlineViewPlaceholderSpan measured zero width. Otherwise
            // ReactViewGroup clips the overlay's contents.
            return Math.max(1, Math.round(height * overlay.imageRatio));
        }
        Float ratio = wideViews.get(view);
        if (ratio == null || !isChatEmote(view)) {
            // the emote menu and the autocomplete show emotes in square slots
            return width;
        }
        return Math.round(height * ratio);
    }
}
