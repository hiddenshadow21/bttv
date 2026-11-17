package bttv.emote;

import android.content.Context;
import android.util.Log;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.EnumMap;
import java.util.Collections;
import java.util.concurrent.ConcurrentHashMap;

import bttv.Network;

public class Emotes {

    public enum Source {
        BTTV,
        FFZ,
        STV;
        public int getPriority() {
            if (this.equals(Source.BTTV)) {
                return 3;
            } else if (this.equals(Source.FFZ)) {
                return 2;
            } else if (this.equals(Source.STV)){
                return 1;
            } else {
                Log.w("LBTTVEmotesSource", "getPriority: unknown priority!");
                return 0;
            }
        }
    }

    public static volatile Map<String, Emote> globalEmotesBTTV = Collections.emptyMap();
    public static volatile Map<String, Emote> globalEmotesFFZ = Collections.emptyMap();
    public static volatile Map<String, Emote> globalEmotes7TV = Collections.emptyMap();

    // map channel ids to their emote codes
    public static Map<Integer, Set<String>> channelEmotesBTTV = new ConcurrentHashMap<>();
    public static Map<Integer, Set<String>> channelEmotesFFZ = new ConcurrentHashMap<>();
    public static Map<Integer, Set<String>> channelEmotes7TV = new ConcurrentHashMap<>();

    // map emote to their id
    private static final Map<String, Emote> idEmoteMap = new ConcurrentHashMap<>();

    // The chat uses provider priority for conflicting codes, but each picker
    // section must show its own emote even if another provider has that code.
    private static final Map<Source, Map<Integer, Map<String, Emote>>> providerChannels = new EnumMap<>(Source.class);
    static {
        for (Source source : Source.values()) {
            providerChannels.put(source, new ConcurrentHashMap<Integer, Map<String, Emote>>());
        }
    }

    public static boolean channelHasEmotes(Context context, int channelId) {

        // BTTV
        boolean bttvEnabled = EmoteSettings.bttvEnabled();
        boolean hasBTTVEmotes = bttvEnabled && channelEmotesBTTV.containsKey(channelId);
        boolean globalBTTVLoaded = bttvEnabled && !globalEmotesBTTV.isEmpty();

        // FFZ
        boolean ffzEnabled = EmoteSettings.ffzEnabled();
        boolean hasFFZEmotes = ffzEnabled && channelEmotesFFZ.containsKey(channelId);
        boolean globalFFZLoaded = ffzEnabled && !globalEmotesFFZ.isEmpty();

        // 7TV
        boolean stvEnabled = EmoteSettings.stvEnabled();
        boolean has7TVEmotes = stvEnabled && channelEmotes7TV.containsKey(channelId);
        boolean global7TVLoaded = stvEnabled && !globalEmotes7TV.isEmpty();

        return hasBTTVEmotes
                || hasFFZEmotes
                || has7TVEmotes
                || globalBTTVLoaded
                || globalFFZLoaded
                || global7TVLoaded;
    }

    public static Emote getEmote(Context ctx, String code, int channelId) {
        // Channel-specific provider maps prevent a disabled provider's emote
        // leaking through the priority cache when two providers share a code.
        for (Source source : new Source[]{Source.FFZ, Source.BTTV, Source.STV}) {
            if (!sourceEnabled(source)) continue;
            Emote global = globalFor(source).get(code);
            if (global != null && usable(global)) return global;
            Emote channel = getChannelEmote(source, channelId, code);
            if (channel != null && usable(channel)) return channel;
        }
        return null;
    }

    /**
     * Overlays are a special case of provider precedence. A zero-width 7TV
     * emote must retain its overlay semantics even if FFZ or BTTV uses the
     * same code. This lookup is only called immediately after a base emote:
     * ordinary chat and the provider-specific picker keep their priorities.
     */
    public static Emote getZeroWidth7TVEmote(String code, int channelId) {
        if (!EmoteSettings.stvEnabled()) return null;
        Emote channel = getChannelEmote(Source.STV, channelId, code);
        Emote candidate = channel != null ? channel : globalEmotes7TV.get(code);
        return candidate != null && candidate.zeroWidth && usable(candidate) ? candidate : null;
    }

    private static boolean sourceEnabled(Source source) {
        switch (source) {
            case BTTV: return EmoteSettings.bttvEnabled();
            case FFZ: return EmoteSettings.ffzEnabled();
            case STV: return EmoteSettings.stvEnabled();
            default: return false;
        }
    }

    private static boolean usable(Emote emote) {
        return EmoteSettings.gifEnabled() || !emote.isAnimated();
    }

    public static Map<String, Emote> globalFor(Source source) {
        switch (source) {
            case BTTV: return globalEmotesBTTV;
            case FFZ: return globalEmotesFFZ;
            case STV: return globalEmotes7TV;
            default: return Collections.emptyMap();
        }
    }

    public static Emote getEmote(int channelId, String code) {
        return getEmote(null, code, channelId);
    }

    public static Emote getChannelEmote(Source source, int channelId, String code) {
        Map<String, Emote> channel = providerChannels.get(source).get(channelId);
        return channel == null ? null : channel.get(code);
    }

    public static Emote getEmoteById(String id) {
        return idEmoteMap.get(id);
    }

    public static void ensureChannelEmotes(Context context, int id) {
        // Never request provider catalogs for an unresolved channel ID.
        if (context == null || id <= 0) return;
        boolean bttvEnabled = EmoteSettings.bttvEnabled();
        boolean ffzEnabled = EmoteSettings.ffzEnabled();
        boolean stvEnabled = EmoteSettings.stvEnabled();

        Log.i("LBTTV", "ensureChannelEmotes: bttvEnabled: " + bttvEnabled + " ffzEnabled: " + ffzEnabled + " stvEnabled: " + stvEnabled);

        if (bttvEnabled && globalEmotesBTTV.isEmpty()) {
            Network.getBTTVGlobalEmotes();
        }
        if (ffzEnabled && globalEmotesFFZ.isEmpty()) {
            Network.getFFZGlobalEmotes();
        }
        if (stvEnabled && globalEmotes7TV.isEmpty()) {
            Network.get7TVGlobalEmotes();
        }
        if (bttvEnabled && !channelEmotesBTTV.containsKey(id)) {
            Network.getBTTVChannelEmotes(id);
        }
        if (ffzEnabled && !channelEmotesFFZ.containsKey(id)) {
            Network.getFFZChannelEmotes(id);
        }
        if (stvEnabled && !channelEmotes7TV.containsKey(id)) {
            Network.get7TVChannelEmotes(id);
        }
    }

    public static void setGlobal(List<Emote> emotes, Emotes.Source source) {
        HashMap<String, Emote> map = new HashMap<>();
        for (Emote emote : emotes) {
            map.put(emote.code, emote);
            idEmoteMap.put(emote.id, emote);
        }
        Map<String, Emote> snapshot = Collections.unmodifiableMap(map);
        switch (source) {
            case BTTV:
                globalEmotesBTTV = snapshot;
                break;
            case FFZ:
                globalEmotesFFZ = snapshot;
                break;
            case STV:
                globalEmotes7TV = snapshot;
                break;
            default:
                Log.e("LBTTVEmotes", "setGlobal: source unknown!", new Exception());
        }
        Log.i("LBTTVEmotes", "setGlobal: " + map.size() + " emotes for " + source);
    }

    // FFZ
    public static void addChannelFFZ(int id, List<Emote> emotes) {
        Set<String> set = new HashSet<>();
        for (Emote emote : emotes) {
            set.add(emote.code);
            idEmoteMap.put(emote.id, emote);
        }

        putProviderChannel(Source.FFZ, id, emotes);
        channelEmotesFFZ.put(id, Collections.unmodifiableSet(set));
        Log.i("LBTTVEmotes", "addChannelFFZ: " + set.size() + " emotes for channel " + id);
    }

    // BTTV
    public static void addChannelBTTV(int id, ChannelEmoteData chEmData) {
        Set<String> set = new HashSet<>();
        for (Emote emote : chEmData.channelEmotes) {
            set.add(emote.code);
            idEmoteMap.put(emote.id, emote);
        }
        for (Emote emote : chEmData.sharedEmotes) {
            set.add(emote.code);
            idEmoteMap.put(emote.id, emote);
        }

        ArrayList<Emote> all = new ArrayList<>(chEmData.channelEmotes);
        all.addAll(chEmData.sharedEmotes);
        putProviderChannel(Source.BTTV, id, all);
        channelEmotesBTTV.put(id, Collections.unmodifiableSet(set));
        Log.i("LBTTVEmotes", "addChannelBTTV: " + set.size() + " emotes for channel " + id);
    }

    // 7TV
    public static void addChannel7TV(int id, List<Emote> emotes) {
        Set<String> set = new HashSet<>();
        for (Emote emote : emotes) {
            set.add(emote.code);
            idEmoteMap.put(emote.id, emote);
        }

        putProviderChannel(Source.STV, id, emotes);
        channelEmotes7TV.put(id, Collections.unmodifiableSet(set));
        Log.i("LBTTVEmotes", "addChannel7TV: " + set.size() + " emotes for channel " + id);
    }


    private static void putProviderChannel(Source source, int channel, List<Emote> emotes) {
        Map<String, Emote> byCode = new HashMap<>();
        for (Emote emote : emotes) byCode.put(emote.code, emote);
        providerChannels.get(source).put(channel, Collections.unmodifiableMap(byCode));
    }

    public static ArrayList<String> getAllEmotes(int channelId) {
        // Autocomplete must not include disabled providers or stale channels.
        java.util.TreeSet<String> codes = new java.util.TreeSet<>();
        if (EmoteSettings.ffzEnabled()) {
            codes.addAll(globalEmotesFFZ.keySet());
            Set<String> channel = channelEmotesFFZ.get(channelId);
            if (channel != null) codes.addAll(channel);
        }
        if (EmoteSettings.bttvEnabled()) {
            codes.addAll(globalEmotesBTTV.keySet());
            Set<String> channel = channelEmotesBTTV.get(channelId);
            if (channel != null) codes.addAll(channel);
        }
        if (EmoteSettings.stvEnabled()) {
            codes.addAll(globalEmotes7TV.keySet());
            Set<String> channel = channelEmotes7TV.get(channelId);
            if (channel != null) codes.addAll(channel);
        }
        if (!EmoteSettings.gifEnabled()) {
            java.util.Iterator<String> cursor = codes.iterator();
            while (cursor.hasNext()) {
                if (getEmote(null, cursor.next(), channelId) == null) cursor.remove();
            }
        }
        return new ArrayList<>(codes);
    }
}
