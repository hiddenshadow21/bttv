package bttv;

import android.util.Log;

import org.json.JSONException;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Set;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.ThreadFactory;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;

import bttv.emote.ChannelEmoteData;
import bttv.emote.Emote;
import bttv.emote.Emotes;

/**
 * Twitch 31.8.0 catalog loader. Does not depend on unshaded okhttp3.* classes:
 * those types are absent in Twitch's current runtime DEX files.
 *
 * The public get*Emotes() methods retain the original bttv.Network API.
 */
public final class Network {
    private static final String TAG = "BTTV318Net";
    private static final int GLOBAL_CHANNEL_ID = -2;
    private static final int MAX_BODY_BYTES = 3_000_000;
    public static final String BTTV_API_HOST = "https://api.betterttv.net";
    public static final String STV_API_HOST = "https://7tv.io/v3";
    public static final String FFZ_API_HOST = "https://api.frankerfacez.com/v1";
    public static final String CHATTERINO_API_HOST = "https://api.chatterino.com";
    private static final Set<String> IN_FLIGHT = ConcurrentHashMap.newKeySet();
    private static final ExecutorService IO = new ThreadPoolExecutor(
            2, 3, 30L, TimeUnit.SECONDS, new ArrayBlockingQueue<Runnable>(32),
            new ThreadFactory() {
                private int serial;
                @Override public synchronized Thread newThread(Runnable work) {
                    Thread thread = new Thread(work, "bttv-catalog-" + (++serial));
                    thread.setDaemon(true);
                    return thread;
                }
            }, new ThreadPoolExecutor.AbortPolicy());

    public Network() {}

    /** Lightweight asynchronous response contract for badge and other JSON callers. */
    public interface TextCallback {
        void onSuccess(String json) throws IOException;
        void onFailure(IOException error);
    }

    /** Kept for Badges.getBadges() and any other generic provider calls. */
    public static void get(final String url, final TextCallback callback) {
        if (callback == null) throw new IllegalArgumentException("callback must not be null");
        try {
            IO.execute(new Runnable() {
                @Override public void run() {
                    try {
                        callback.onSuccess(download(url));
                    } catch (Exception failure) {
                        IOException error = failure instanceof IOException
                                ? (IOException) failure : new IOException("Provider callback failed", failure);
                        try {
                            callback.onFailure(error);
                        } catch (Throwable callbackFailure) {
                            Log.e(TAG, "Provider failure callback crashed", callbackFailure);
                        }
                    }
                }
            });
        } catch (RuntimeException rejected) {
            Log.e(TAG, "Provider request could not be scheduled", rejected);
            callback.onFailure(new IOException("Provider request could not be scheduled", rejected));
        }
    }

    private static void schedule(final String url, final Emotes.Source source, final int channel) {
        final String key = source.name() + ":" + channel;
        if (!IN_FLIGHT.add(key)) return;
        Log.i(TAG, "Catalog request scheduled: provider=" + source.name()
                + ", scope=" + (channel == GLOBAL_CHANNEL_ID ? "global" : "channel"));
        try {
            IO.execute(new Runnable() {
                @Override public void run() {
                    try {
                        String json = download(url);
                        if (channel == GLOBAL_CHANNEL_ID) {
                            List<Emote> emotes = Emote.fromJSONArray(json, source);
                            Emotes.setGlobal(emotes, source);
                            Log.i(TAG, "Catalog loaded: provider=" + source.name()
                                    + ", scope=global, count=" + emotes.size());
                        } else {
                            int count;
                            switch (source) {
                                case BTTV: {
                                    ChannelEmoteData data = ChannelEmoteData.fromJson(json);
                                    Emotes.addChannelBTTV(channel, data);
                                    count = data.channelEmotes.size() + data.sharedEmotes.size();
                                    break;
                                }
                                case FFZ: {
                                    List<Emote> emotes = Emote.fromJSONArray(json, source);
                                    Emotes.addChannelFFZ(channel, emotes);
                                    count = emotes.size();
                                    break;
                                }
                                case STV: {
                                    List<Emote> emotes = Emote.fromJSONArray(json, source);
                                    Emotes.addChannel7TV(channel, emotes);
                                    count = emotes.size();
                                    break;
                                }
                                default: throw new IllegalArgumentException("Unknown catalog source");
                            }
                            Log.i(TAG, "Catalog loaded: provider=" + source.name()
                                    + ", scope=channel, count=" + count);
                        }
                    } catch (Throwable e) {
                        // Network and provider schema changes are visible, not silently ignored.
                        Log.e(TAG, "Catalog fetch failed: provider=" + source.name()
                                + ", scope=" + (channel == GLOBAL_CHANNEL_ID ? "global" : "channel"), e);
                    } finally {
                        IN_FLIGHT.remove(key);
                    }
                }
            });
        } catch (RuntimeException e) {
            IN_FLIGHT.remove(key);
            Log.e(TAG, "Catalog task scheduling rejected", e);
        }
    }

    private static String download(String url) throws IOException {
        URL request = new URL(url);
        String host = request.getHost();
        if (!"https".equalsIgnoreCase(request.getProtocol()) ||
                !("api.betterttv.net".equals(host) || "7tv.io".equals(host)
                        || "api.frankerfacez.com".equals(host)
                        || "api.chatterino.com".equals(host)
                        // Update-check JSON only. Binary downloads are handled separately.
                        || ("api.github.com".equals(host) &&
                            "/repos/bttv-android/bttv/releases/latest".equals(request.getPath())))) {
            throw new IOException("Unexpected emote API host");
        }
        HttpURLConnection connection = (HttpURLConnection) request.openConnection();
        connection.setConnectTimeout(10000);
        connection.setReadTimeout(15000);
        connection.setRequestMethod("GET");
        connection.setRequestProperty("User-Agent", "bttv-android/0.44.0-beta");
        connection.setRequestProperty("Accept", "application/json");
        connection.setInstanceFollowRedirects(false);
        try {
            int status = connection.getResponseCode();
            if (status != 200) throw new IOException("Catalog HTTP " + status);
            try (InputStream stream = connection.getInputStream();
                 ByteArrayOutputStream bytes = new ByteArrayOutputStream()) {
                byte[] buf = new byte[8192];
                int length;
                while ((length = stream.read(buf)) != -1) {
                    if (bytes.size() + length > MAX_BODY_BYTES) {
                        throw new IOException("Catalog response exceeds size limit");
                    }
                    bytes.write(buf, 0, length);
                }
                return new String(bytes.toByteArray(), StandardCharsets.UTF_8);
            }
        } finally {
            connection.disconnect();
        }
    }

    public static void getBTTVGlobalEmotes() {
        schedule(BTTV_API_HOST + "/3/cached/emotes/global", Emotes.Source.BTTV, GLOBAL_CHANNEL_ID);
    }
    public static void getFFZGlobalEmotes() {
        schedule(BTTV_API_HOST + "/3/cached/frankerfacez/emotes/global", Emotes.Source.FFZ, GLOBAL_CHANNEL_ID);
    }
    public static void get7TVGlobalEmotes() {
        schedule(STV_API_HOST + "/emote-sets/global", Emotes.Source.STV, GLOBAL_CHANNEL_ID);
    }
    public static void getBTTVChannelEmotes(int channelId) {
        schedule(BTTV_API_HOST + "/3/cached/users/twitch/" + channelId, Emotes.Source.BTTV, channelId);
    }
    public static void getFFZChannelEmotes(int channelId) {
        schedule(BTTV_API_HOST + "/3/cached/frankerfacez/users/twitch/" + channelId, Emotes.Source.FFZ, channelId);
    }
    public static void get7TVChannelEmotes(int channelId) {
        schedule(STV_API_HOST + "/users/twitch/" + channelId, Emotes.Source.STV, channelId);
    }
}
