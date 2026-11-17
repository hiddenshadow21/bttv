package bttv.api;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.RectF;
import android.util.Log;

import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.List;
import java.util.HashSet;
import java.util.Set;

import bttv.Data;
import bttv.IrcEmotes;
import bttv.Network;
import bttv.RNNetwork;
import bttv.emote.EmoteUrlUtil;
import bttv.emote.InputEmotes;
import bttv.emote.RNEmoteCard;
import bttv.emote.RNEmoteMenu;
import bttv.emote.WideEmotes;

/**
 * Entry points for Twitch builds with the react native chat.
 * These only take plain types, as the names of most classes are obfuscated and change with every release.
 */
public class Hooks {
    public static final String TAG = "LBTTVHooks";

    private static final Set<Integer> bypassedRequests = new HashSet<>();

    /** @noinspection unused */
    public static void onAppCreate(Context context) {
        try {
            Data.ctx = context;
            Log.i(TAG, "onAppCreate: context set");
            // the emote menu is filled before the first chat message arrives
            Network.getBTTVGlobalEmotes();
            Network.getFFZGlobalEmotes();
            Network.get7TVGlobalEmotes();
        } catch (Throwable t) {
            Log.e(TAG, "onAppCreate: ", t);
        }
    }

    /**
     * @param socketId id of the react native websocket
     * @param text incoming text frame
     * @return text to hand to react native
     * @noinspection unused
     */
    public static String onWebSocketText(int socketId, String text) {
        try {
            if (text == null) {
                return null;
            }
            bttv.RNChannelPoints318.onReactNativeSocketFrame(text);
            if (text.contains(IrcEmotes.ROOMSTATE)) {
                IrcEmotes.onRoomState(text);
            }
            // Keep deleted messages before React Native's IRC parser can remove them.
            text = bttv.ChatModeration318.filterFrame(text);
            if (!text.contains(" PRIVMSG #")) {
                return text;
            }
            return bttv.ChatTimestamps.rewriteFrame(IrcEmotes.rewriteFrame(text));
        } catch (Throwable t) {
            Log.e(TAG, "onWebSocketText: ", t);
            return text;
        }
    }

    /**
     * @param uri uri of an image react native is about to load
     * @return uri to load instead
     * @noinspection unused
     */
    public static String imageUri(String uri) {
        try {
            String id = EmoteUrlUtil.idFromTwitchUrl(uri);
            if (id == null) {
                return uri;
            }
            String url = EmoteUrlUtil.getEmoteUrl(id);
            return url == null ? uri : url;
        } catch (Throwable t) {
            Log.e(TAG, "imageUri: ", t);
            return uri;
        }
    }

    /**
     * 31.8.0 ReactImageManager's prop setter receives an array of React Native
     * image source maps. Avoid obsolete obfuscated ImageSource constructor hooks.
     * Copy only if at least one BTTV emote URI needs rewriting.
     *
     * The copy-on-write adaptation comes from the supplied 31.8.0 port, but
     * it calls PR #740's imageUri() and keeps PR #740's provider model.
     */
    @SuppressWarnings("unused")
    public static Object rewriteReactSources(Object sources) {
        if (sources == null) return null;
        try {
            Class<?> readableArray = Class.forName("com.facebook.react.bridge.ReadableArray");
            Class<?> readableMap = Class.forName("com.facebook.react.bridge.ReadableMap");
            Class<?> writableMap = Class.forName("com.facebook.react.bridge.WritableMap");
            Class<?> arguments = Class.forName("com.facebook.react.bridge.Arguments");
            Method sizeMethod = readableArray.getMethod("size");
            Method getMapMethod = readableArray.getMethod("getMap", int.class);
            Method getStringMethod = readableMap.getMethod("getString", String.class);
            int size = (Integer) sizeMethod.invoke(sources);
            List<Object> original = new ArrayList<>(size);
            List<String> rewrites = new ArrayList<>(size);
            boolean changed = false;
            for (int i = 0; i < size; ++i) {
                Object item = getMapMethod.invoke(sources, i);
                original.add(item);
                String uri = item == null ? null : (String) getStringMethod.invoke(item, "uri");
                String rewritten = imageUri(uri);
                rewrites.add(rewritten);
                if (rewritten != null && !rewritten.equals(uri)) changed = true;
            }
            if (!changed) return sources;
            Object result = arguments.getMethod("createArray").invoke(null);
            Method createMap = arguments.getMethod("createMap");
            Method merge = writableMap.getMethod("merge", readableMap);
            Method putString = writableMap.getMethod("putString", String.class, String.class);
            Method pushMap = result.getClass().getMethod("pushMap", readableMap);
            for (int i = 0; i < size; ++i) {
                Object map = createMap.invoke(null);
                merge.invoke(map, original.get(i));
                putString.invoke(map, "uri", rewrites.get(i));
                pushMap.invoke(result, map);
            }
            return result;
        } catch (Throwable error) {
            Log.e(TAG, "rewriteReactSources: leaving original sources untouched", error);
            return sources;
        }
    }

    /**
     * @param uri url the chat input built for an emote
     * @return url to load instead
     * @noinspection unused
     */
    public static String inputEmoteUrl(String uri) {
        try {
            return uri == null ? null : InputEmotes.imageUrl(uri);
        } catch (Throwable t) {
            Log.e(TAG, "inputEmoteUrl: ", t);
            return uri;
        }
    }

    /**
     * @param url image url of an emote in the chat input
     * @param size height of the emote
     * @return width of the emote
     * @noinspection unused
     */
    public static int inputEmoteWidth(String url, int size) {
        try {
            return InputEmotes.width(url, size);
        } catch (Throwable t) {
            Log.e(TAG, "inputEmoteWidth: ", t);
            return size;
        }
    }

    /**
     * @param url image url of an emote in the chat input
     * @param left left edge of the emote
     * @param size height of the emote
     * @return right edge of the emote
     * @noinspection unused
     */
    public static float inputEmoteRight(String url, float left, float size) {
        try {
            return InputEmotes.right(url, left, size);
        } catch (Throwable t) {
            Log.e(TAG, "inputEmoteRight: ", t);
            return left + size;
        }
    }

    /**
     * @param url image url of an emote in the chat input, called on a background thread
     * @return the image, null to let the input download it
     * @noinspection unused
     */
    public static Bitmap inputEmoteBitmap(String url) {
        try {
            return InputEmotes.bitmap(url);
        } catch (Throwable t) {
            Log.e(TAG, "inputEmoteBitmap: ", t);
            return null;
        }
    }

    /**
     * @param view TwitchEmoteInputView
     * @noinspection unused
     */
    public static void onInputViewAttached(Object view) {
        try {
            InputEmotes.onInputViewAttached(view);
        } catch (Throwable t) {
            Log.e(TAG, "onInputViewAttached: ", t);
        }
    }

    /**
     * Same arguments as the drawBitmap call of an emote span in the chat input.
     * @return true if the emote was drawn, the still image must not be drawn then
     * @noinspection unused
     */
    public static boolean drawInputEmote(Bitmap bitmap, Canvas canvas, RectF destination, Paint paint) {
        try {
            return InputEmotes.draw(bitmap, canvas, destination, paint);
        } catch (Throwable t) {
            Log.e(TAG, "drawInputEmote: ", t);
            return false;
        }
    }

    /**
     * Same arguments as NetworkingModule.sendRequest
     * @param module react native NetworkingModule
     * @param data react native ReadableMap, the body is stored under "string"
     * @return true if the request was answered by us and must not be sent
     * @noinspection unused
     */
    public static boolean interceptHttpRequest(final Object module, final String method, final String url, final double requestId,
                                               final Object headers, final Object data, final String responseType,
                                               final boolean incrementalUpdates, final double timeout, final boolean withCredentials) {
        try {
            if (url == null || data == null || !url.contains("gql.twitch.tv")) {
                return false;
            }
            bttv.RNChannelPoints318.onReactNativeRequest(method, url, headers);
            final int id = (int) requestId;
            synchronized (bypassedRequests) {
                if (bypassedRequests.remove(id)) {
                    return false;
                }
            }
            String body = RNNetwork.readBody(data);
            RNEmoteMenu.observeChannelQuery(body);
            if (RNEmoteCard.intercept(module, url, id, body)) {
                return true;
            }
            Runnable fallback = new Runnable() {
                @Override
                public void run() {
                    try {
                        synchronized (bypassedRequests) {
                            bypassedRequests.add(id);
                        }
                        Class<?> readableArray = Class.forName("com.facebook.react.bridge.ReadableArray");
                        Class<?> readableMap = Class.forName("com.facebook.react.bridge.ReadableMap");
                        module.getClass().getMethod("sendRequest", String.class, String.class, double.class, readableArray,
                                        readableMap, String.class, boolean.class, double.class, boolean.class)
                                .invoke(module, method, url, requestId, headers, data, responseType, incrementalUpdates, timeout, withCredentials);
                    } catch (Throwable t) {
                        Log.e(TAG, "interceptHttpRequest: fallback failed: ", t);
                    }
                }
            };
            return RNEmoteMenu.intercept(module, method, url, id, headers, body, fallback);
        } catch (Throwable t) {
            Log.e(TAG, "interceptHttpRequest: ", t);
            return false;
        }
    }

    /**
     * @param text a piece of text react native is about to lay out
     * @return text to show
     * @noinspection unused
     */
    public static String text(String text) {
        try {
            return RNEmoteCard.swapText(text);
        } catch (Throwable t) {
            Log.e(TAG, "text: ", t);
            return text;
        }
    }

    /**
     * @param text text an inline view is part of
     * @param end index behind the inline view
     * @param width width of the slot for the inline view
     * @return width to reserve
     * @noinspection unused
     */
    public static int inlineViewWidth(CharSequence text, int end, int width) {
        try {
            return WideEmotes.inlineViewWidth(text, end, width);
        } catch (Throwable t) {
            Log.e(TAG, "inlineViewWidth: ", t);
            return width;
        }
    }

    /**
     * @param view react native image view
     * @param sources ReadableArray, the sources the view is about to show
     * @noinspection unused
     */
    public static void onImageViewSource(Object view, Object sources) {
        try {
            WideEmotes.onImageViewSource(view, sources);
        } catch (Throwable t) {
            Log.e(TAG, "onImageViewSource: ", t);
        }
    }

    /**
     * @param manager react native SurfaceMountingManager
     * @param tag tag of the view that gets its layout
     * @return width the view should get
     * @noinspection unused
     */
    public static int layoutWidth(Object manager, int tag, int width, int height) {
        try {
            return WideEmotes.layoutWidth(manager, tag, width, height);
        } catch (Throwable t) {
            Log.e(TAG, "layoutWidth: ", t);
            return width;
        }
    }
}
