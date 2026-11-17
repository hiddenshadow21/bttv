package bttv;

import android.content.Context;
import android.content.res.Configuration;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.PixelFormat;
import android.graphics.RectF;
import android.graphics.ColorFilter;
import android.graphics.drawable.Drawable;
import android.os.Looper;
import android.text.SpannableStringBuilder;
import android.text.Spanned;
import android.text.style.ReplacementSpan;
import android.util.Log;
import android.view.View;
import android.widget.TextView;

import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;
import java.util.WeakHashMap;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import bttv.emote.Emote;
import bttv.emote.Emotes;
import bttv.emote.InputEmotes;
import bttv.settings.Settings;
import bttv.settings.UserPreferences;

/**
 * A narrow bridge for the native (non-React-Native) vertical theatre OneChat
 * TextView. The normal chat uses entirely different Hermes/Fabric hooks.
 *
 * Runs after q5s.x() binds its SpannedString to TitleExtraSmall. The original
 * text and spans are preserved: only exact, uncovered third-party emote tokens
 * receive a ReplacementSpan. Images load off the main thread and are cached.
 * OneChat displays a single message at a time, so split styling alternates as
 * the displayed message changes, not across a multi-row RecyclerView.
 */
public final class VerticalChat318 {
    private static final String TAG = "LBTTVVertical318";
    private static final Map<String, Bitmap> IMAGES = Collections.synchronizedMap(
            new LinkedHashMap<String, Bitmap>(128, .75f, true) {
                @Override protected boolean removeEldestEntry(Map.Entry<String, Bitmap> eldest) {
                    return size() > 128;
                }
            });
    private static final Set<String> LOADING = ConcurrentHashMap.newKeySet();
    private static final Map<String, Set<TextView>> WAITERS = new ConcurrentHashMap<>();
    private static final Map<String, Long> FAILED_UNTIL = new ConcurrentHashMap<>();
    private static final ExecutorService IO = Executors.newFixedThreadPool(2);
    private static final Map<TextView, RowState> ROWS = Collections.synchronizedMap(new WeakHashMap<TextView, RowState>());
    private static int logged;
    private static int classicLogged;


    private static final class RowState {
        CharSequence nativeText;
        boolean alternate;
        Drawable ownedBackground;
        Drawable separator;
    }

    private VerticalChat318() { }

    /** The vertical OneChat fragment carries its own channel on creation. */
    public static void onChannel(Object channelInfo) {
        if (channelInfo == null) return;
        try {
            Object tuid = channelInfo.getClass().getMethod("getTuid").invoke(channelInfo);
            if (tuid == null) return;
            Object value = tuid.getClass().getMethod("toSerializedInt$core_models_release").invoke(tuid);
            int id = ((Number) value).intValue();
            if (id > 0) {
                Data.setCurrentBroadcasterId(id);
                Log.i(TAG, "Native vertical OneChat bound to channel " + id);
            }
        } catch (Throwable error) {
            Log.w(TAG, "Could not resolve native vertical chat channel", error);
        }
    }

    /**
     * The Dual Format Classic theatre uses the *native* RecyclerView, not
     * Hermes/Fabric. k7d.C() assigns the complete spanned message into the
     * chat_message_item TextView. Apply only third-party emote spans here;
     * Split Chat's RN row styling is deliberately NOT used for this view.
     */
    public static void onClassicTextBound(TextView view) {
        if (view == null) return;
        if (Looper.myLooper() != Looper.getMainLooper()) {
            view.post(() -> onClassicTextBound(view));
            return;
        }
        try {
            int channel = Data.currentBroadcasterId;
            if (classicLogged++ < 12) {
                Log.i("LBTTVClassic318", "Native Classic chat message bound, channel="
                        + channel + ", spanned=" + (view.getText() instanceof Spanned));
            }
            applyEmotes(view);
        } catch (Throwable error) {
            Log.w("LBTTVClassic318", "Could not augment native Classic message", error);
        }
    }

    /**
     * Native Classic theatre is a different player from TwitchRNTheatreFragment;
     * no RN ROOMSTATE is guaranteed. Select its stream broadcaster when the
     * native fragment enters the foreground (not from background chat traffic).
     */
    /** Read the foreground Classic fragment's model without risking a crash
     * if Twitch has not initialized it when onViewCreated runs. */
    public static void onClassicTheatre(Object fragment) {
        if (fragment == null) return;
        try {
            Object playable = fragment.getClass().getMethod("getPlayableModel").invoke(fragment);
            onClassicPlayable(playable);
        } catch (Throwable error) {
            Log.w("LBTTVClassic318", "Classic stream model not available yet", error);
        }
    }

    public static void onClassicPlayable(Object playable) {
        if (playable == null) return;
        try {
            Object channelTuid = playable.getClass().getMethod("getChannelId").invoke(playable);
            if (channelTuid == null) return;
            Object serialized = channelTuid.getClass()
                    .getMethod("toSerializedInt$core_models_release").invoke(channelTuid);
            if (!(serialized instanceof Number)) return;
            int channel = ((Number) serialized).intValue();
            if (channel <= 0) return;
            Data.setCurrentBroadcasterId(channel);
            Log.i("LBTTVClassic318", "Native Classic theatre channel=" + channel);
        } catch (NoSuchMethodException ignored) {
            // VOD or non-stream playable, outside this live Classic chat hook.
        } catch (Throwable error) {
            Log.w("LBTTVClassic318", "Could not resolve Classic theatre channel", error);
        }
    }

    /** Called only from VerticalTheatreOneChatFragment's q5s text binding. */
    public static void onTextBound(TextView view) {
        if (view == null) return;
        if (Looper.myLooper() != Looper.getMainLooper()) {
            view.post(() -> onTextBound(view));
            return;
        }
        CharSequence original = view.getText();
        if (original == null || original.length() == 0) return;
        RowState state = ROWS.get(view);
        if (state == null) {
            state = new RowState();
            ROWS.put(view, state);
        }
        if (state.nativeText != original) {
            state.nativeText = original;
            state.alternate = !state.alternate;
        }
        applySplit(view, state);
        applyEmotes(view);
        if (logged++ < 8) {
            Log.i(TAG, "Native vertical OneChat text bound, channel=" + Data.currentBroadcasterId
                    + ", split=" + splitEnabled(view.getContext()));
        }
    }

    private static boolean splitEnabled(Context context) {
        try {
            return ((UserPreferences.Entry.BoolEntry) Settings.SplitChatEnabled.entry)
                    .get(context).get();
        } catch (Throwable t) {
            Log.w(TAG, "Cannot access split-chat setting", t);
            return false;
        }
    }

    private static void applySplit(TextView view, RowState state) {
        if (!splitEnabled(view.getContext())) {
            restore(view, state);
            return;
        }
        if (state.ownedBackground != null && view.getBackground() != state.ownedBackground) {
            // Twitch changed its own background (highlight/effect). Do not cover it.
            state.ownedBackground = null;
        }
        if (state.alternate) {
            if (view.getBackground() == null || view.getBackground() == state.ownedBackground) {
                int night = view.getResources().getConfiguration().uiMode & Configuration.UI_MODE_NIGHT_MASK;
                int tint = night == Configuration.UI_MODE_NIGHT_YES ? 0xFF29292F : 0xFFEDEDF0;
                view.setBackgroundColor(tint);
                state.ownedBackground = view.getBackground();
            }
        } else if (state.ownedBackground != null) {
            view.setBackground(null);
            state.ownedBackground = null;
        }
        String style = UserPreferences.getString(view.getContext(), SplitChat318.SEPARATOR_PREF, "none");
        int dp = "strong".equals(style) ? 2 : ("subtle".equals(style) ? 1 : 0);
        if (dp == 0) {
            clearLine(view, state);
        } else {
            if (state.separator == null) {
                state.separator = new BottomLine(view, dp);
                view.getOverlay().add(state.separator);
                view.addOnLayoutChangeListener((v, l, t, r, b, ol, ot, orr, ob) -> {
                    RowState s = ROWS.get(view);
                    if (s != null && s.separator != null)
                        s.separator.setBounds(0, 0, view.getWidth(), view.getHeight());
                });
            }
            state.separator.setBounds(0, 0, view.getWidth(), view.getHeight());
        }
    }

    private static void restore(TextView view, RowState state) {
        if (state.ownedBackground != null && view.getBackground() == state.ownedBackground) {
            view.setBackground(null);
        }
        state.ownedBackground = null;
        clearLine(view, state);
    }

    private static void clearLine(TextView view, RowState state) {
        if (state.separator != null) {
            view.getOverlay().remove(state.separator);
            state.separator = null;
        }
    }

    private static void applyEmotes(TextView view) {
        CharSequence text = view.getText();
        if (!(text instanceof Spanned)) return;
        int channel = Data.currentBroadcasterId;
        SpannableStringBuilder builder = new SpannableStringBuilder(text);
        boolean changed = false;
        for (int start = 0; start < text.length();) {
            while (start < text.length() && Character.isWhitespace(text.charAt(start))) start++;
            if (start == text.length()) break;
            int end = start;
            while (end < text.length() && !Character.isWhitespace(text.charAt(end))) end++;
            String code = text.subSequence(start, end).toString();
            if (!code.contains("://") && ((Spanned) text).getSpans(start, end, ReplacementSpan.class).length == 0) {
                Emote emote = Emotes.getEmote(view.getContext(), code, channel);
                if (emote != null) {
                    Bitmap image = IMAGES.get(emote.url);
                    if (image != null) {
                        builder.setSpan(new InlineEmote(image, emote.aspectRatio), start, end,
                                Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
                        changed = true;
                    } else {
                        loadImage(emote, view);
                    }
                }
            }
            start = end;
        }
        if (changed) view.setText(builder, TextView.BufferType.SPANNABLE);
    }

    private static void loadImage(Emote emote, TextView view) {
        Long retryAfter = FAILED_UNTIL.get(emote.url);
        if (retryAfter != null && System.currentTimeMillis() < retryAfter) return;
        Set<TextView> interested = WAITERS.computeIfAbsent(emote.url,
                ignored -> Collections.synchronizedSet(
                        Collections.newSetFromMap(new WeakHashMap<TextView, Boolean>())));
        interested.add(view);
        if (!LOADING.add(emote.url)) return;
        // InputEmotes already handles the verified Fresco/disk/network cache,
        // GIF/WebP decoding, and BTTV's animation mode preference.
        IO.execute(() -> {
            try {
                // Resolve using the real provider URL (BTTV, FFZ or 7TV),
                // not a fabricated Twitch/BTTV emote identifier.
                Bitmap image = InputEmotes.bitmapForEmote(emote);
                if (image != null) {
                    IMAGES.put(emote.url, image);
                    FAILED_UNTIL.remove(emote.url);
                } else {
                    FAILED_UNTIL.put(emote.url, System.currentTimeMillis() + 300_000L);
                }
            } catch (Throwable error) {
                FAILED_UNTIL.put(emote.url, System.currentTimeMillis() + 300_000L);
                Log.w(TAG, "Could not load native vertical emote " + emote.code, error);
            } finally {
                LOADING.remove(emote.url);
                Set<TextView> interestedViews = WAITERS.remove(emote.url);
                if (interestedViews != null) {
                    TextView[] snapshot;
                    synchronized (interestedViews) {
                        snapshot = interestedViews.toArray(new TextView[0]);
                    }
                    for (TextView waiting : snapshot) {
                        waiting.post(() -> {
                            if (waiting.isAttachedToWindow()) applyEmotes(waiting);
                        });
                    }
                }
            }
        });
    }

    private static final class InlineEmote extends ReplacementSpan {
        private final Bitmap image;
        private final float ratio;
        InlineEmote(Bitmap image, float ratio) {
            this.image = image;
            this.ratio = Math.min(4f, Math.max(.25f, ratio));
        }
        private int height(Paint p) { return Math.max(12, (int) Math.ceil(p.getTextSize() * 1.2f)); }
        @Override public int getSize(Paint paint, CharSequence text, int start, int end, Paint.FontMetricsInt fm) {
            int h = height(paint);
            if (fm != null) { fm.top = fm.ascent = -h; fm.bottom = fm.descent = 0; }
            return Math.max(1, Math.round(h * ratio));
        }
        @Override public void draw(Canvas canvas, CharSequence text, int start, int end,
                                    float x, int top, int y, int bottom, Paint paint) {
            int h = height(paint);
            RectF dst = new RectF(x, y - h, x + Math.max(1, Math.round(h * ratio)), y);
            if (!InputEmotes.draw(image, canvas, dst, paint)) canvas.drawBitmap(image, null, dst, paint);
        }
    }

    private static final class BottomLine extends Drawable {
        final Paint paint = new Paint();
        final int thickness;
        BottomLine(View view, int dp) {
            thickness = Math.max(1, Math.round(dp * view.getResources().getDisplayMetrics().density));
            boolean dark = (view.getResources().getConfiguration().uiMode
                    & Configuration.UI_MODE_NIGHT_MASK) == Configuration.UI_MODE_NIGHT_YES;
            paint.setColor(dark ? 0xFF505059 : 0xFFC3C3C9);
        }
        @Override public void draw(Canvas c) {
            c.drawRect(0, Math.max(0, getBounds().bottom - thickness),
                    getBounds().right, getBounds().bottom, paint);
        }
        @Override public void setAlpha(int alpha) { paint.setAlpha(alpha); invalidateSelf(); }
        @Override public void setColorFilter(ColorFilter cf) { paint.setColorFilter(cf); invalidateSelf(); }
        @Override public int getOpacity() { return PixelFormat.TRANSLUCENT; }
    }
}
