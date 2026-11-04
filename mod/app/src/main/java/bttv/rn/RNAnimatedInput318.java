package bttv.rn;

import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.ImageDecoder;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.drawable.AnimatedImageDrawable;
import android.graphics.drawable.Drawable;
import android.os.Handler;
import android.os.Looper;
import android.text.Editable;
import android.text.Spanned;
import android.text.style.ReplacementSpan;
import android.util.Log;
import android.view.View;
import android.widget.TextView;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.lang.reflect.Method;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.ByteBuffer;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Map;
import java.util.Set;
import java.util.WeakHashMap;
import java.util.concurrent.ConcurrentHashMap;

import bttv.emote.Emote;

/** Animated external emotes inside the RN chat input's bitmap-only spans.
 * Normal Twitch emotes use the stock loader/drawing path, unchanged.
 * Gif bytes are decoded to AnimatedImageDrawable on API 29+.
 * Based on PR #740's InputEmotes animation approach, with bounded downloads.
 */
public final class RNAnimatedInput318 {
    private static final String TAG = "BTTV318GIF";
    private static final int MAX_GIF_BYTES = 3_000_000;
    private static final Map<String, Emote> urls = new ConcurrentHashMap<>();
    private static final Map<Bitmap, Drawable> animations = Collections.synchronizedMap(new WeakHashMap<Bitmap, Drawable>());
    private static final Set<View> inputViews = Collections.newSetFromMap(new WeakHashMap<View, Boolean>());
    private static final Handler mainHandler = new Handler(Looper.getMainLooper());
    private static int animatedCount;
    private RNAnimatedInput318() {}

    public static void register(Emote emote) {
        if (emote != null && emote.url != null && "gif".equalsIgnoreCase(emote.imageType)
                && (emote.url.startsWith("https://") || emote.url.startsWith("http://"))) {
            urls.put(emote.url, emote);
        }
    }

    public static void onInputViewAttached(View view) {
        if (view instanceof TextView) inputViews.add(view);
    }

    /** Runs on TwitchEmoteInputView's background loader thread. Null means stock loading. */
    public static Bitmap fetch(String originalUrl) {
        try {
            if (originalUrl == null) return null;
            String url = RNFeatureHooks318.redirectImageUri(originalUrl);
            Emote emote = urls.get(url);
            if (emote == null || !"gif".equalsIgnoreCase(emote.imageType)) return null;
            URL parsed = new URL(url);
            if (!"https".equalsIgnoreCase(parsed.getProtocol())) return null;
            String host = parsed.getHost();
            if (!("cdn.betterttv.net".equals(host) || "cdn.7tv.app".equals(host)
                    || "static-cdn.jtvnw.net".equals(host) || host.endsWith(".frankerfacez.com")
                    || "cdn.frankerfacez.com".equals(host))) return null;
            HttpURLConnection connection = (HttpURLConnection) parsed.openConnection();
            connection.setConnectTimeout(7000);
            connection.setReadTimeout(10000);
            connection.setInstanceFollowRedirects(false);
            try {
                if (connection.getResponseCode() != 200) return null;
                ByteArrayOutputStream output = new ByteArrayOutputStream();
                try (InputStream input = connection.getInputStream()) {
                    byte[] buffer = new byte[8192];
                    int n;
                    while ((n = input.read(buffer)) != -1) {
                        if (output.size() + n > MAX_GIF_BYTES) return null;
                        output.write(buffer, 0, n);
                    }
                }
                byte[] bytes = output.toByteArray();
                Bitmap bitmap = BitmapFactory.decodeByteArray(bytes, 0, bytes.length);
                if (bitmap == null) return null;
                Drawable drawable = ImageDecoder.decodeDrawable(ImageDecoder.createSource(ByteBuffer.wrap(bytes)));
                if (drawable instanceof AnimatedImageDrawable) {
                    drawable.setCallback(CALLBACK);
                    animations.put(bitmap, drawable);
                    if (++animatedCount <= 5) Log.i(TAG, "Animated input emote decoded");
                }
                return bitmap;
            } finally { connection.disconnect(); }
        } catch (Throwable problem) {
            Log.w(TAG, "Animated input decode unavailable; falling back to Twitch", problem);
            return null;
        }
    }

    /** True when an animation was drawn instead of Twitch's first-frame Bitmap. */
    public static boolean draw(Bitmap bitmap, Canvas canvas, RectF destination, Paint paint) {
        if (bitmap == null || canvas == null || destination == null || paint == null) return false;
        Drawable animation = animations.get(bitmap);
        if (!(animation instanceof AnimatedImageDrawable)) return false;
        try {
            animation.setBounds(Math.round(destination.left), Math.round(destination.top),
                    Math.round(destination.right), Math.round(destination.bottom));
            animation.setAlpha(paint.getAlpha());
            animation.draw(canvas);
            AnimatedImageDrawable gif = (AnimatedImageDrawable) animation;
            if (!gif.isRunning()) gif.start();
            return true;
        } catch (Throwable t) {
            Log.w(TAG, "Animated span draw failed; using still image", t);
            return false;
        }
    }

    private static final Drawable.Callback CALLBACK = new Drawable.Callback() {
        @Override public void invalidateDrawable(Drawable drawable) {
            for (View view : new ArrayList<View>(inputViews)) {
                if (!(view instanceof TextView) || !view.isAttachedToWindow()) continue;
                CharSequence text = ((TextView) view).getText();
                if (!(text instanceof Editable)) continue;
                Editable editable = (Editable) text;
                for (ReplacementSpan span : editable.getSpans(0, editable.length(), ReplacementSpan.class)) {
                    try {
                        Method method = span.getClass().getMethod("getBitmap");
                        Object bitmap = method.invoke(span);
                        if (animations.get(bitmap) != drawable) continue;
                        int start = editable.getSpanStart(span);
                        int end = editable.getSpanEnd(span);
                        if (start >= 0 && end > start)
                            editable.setSpan(span, start, end, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
                    } catch (Throwable ignored) { /* not our span */ }
                }
            }
        }
        @Override public void scheduleDrawable(Drawable who, Runnable action, long when) {
            mainHandler.postAtTime(action, who, when);
        }
        @Override public void unscheduleDrawable(Drawable who, Runnable action) {
            mainHandler.removeCallbacks(action, who);
        }
    };
}
