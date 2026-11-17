package bttv.emote;

import android.util.Log;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

import tv.twitch.android.models.emotes.EmoteModelAssetType;

public class Emote {
    public String id;
    public Emotes.Source source;
    public String code;
    public String url;
    public String imageType;
    // Animation is independent of container format: some 7TV sets provide
    // animated WebP when a GIF rendition is absent.
    public boolean animated;
    // 7TV: active emote flag 1, or the emote's default flag 256.
    // Only zero-width when an emote actually follows another emote in chat.
    public boolean zeroWidth;
    public String owner;
    // width / height, 1 if unknown
    public float aspectRatio = 1f;

    public Emote(String id, Emotes.Source source, String code, String url, String imageType, String owner) {
        this.id = id;
        this.source = source;
        this.code = code;
        this.url = url;
        this.imageType = imageType;
        this.animated = "gif".equalsIgnoreCase(imageType);
        this.owner = owner;
    }

    public static Emote fromJson(JSONObject jsonObject, Emotes.Source source) throws JSONException {
        String id = jsonObject.getString("id");
        String code;
        String url;
        String imageType = "";
        String owner = null;
        float aspectRatio = 1f;

        switch (source) {
            case BTTV:
                code = jsonObject.getString("code");
                url = "https://cdn.betterttv.net/emote/" + id + "/2x";
                imageType = jsonObject.getString("imageType");
                owner = null; // we don't get the owner :/
                // only set for emotes that are not square
                if (jsonObject.optInt("width") > 0 && jsonObject.optInt("height") > 0) {
                    aspectRatio = (float) jsonObject.getInt("width") / jsonObject.getInt("height");
                }
                break;
            case FFZ:
                code = jsonObject.getString("code");
                JSONObject images = jsonObject.getJSONObject("images");
                if (images.has("2x") && !images.isNull("2x")) {
                    url = images.getString("2x");
                } else {
                    url = images.getString("1x");
                }
                imageType = jsonObject.getString("imageType");
                if (jsonObject.has("user"))
                    owner = jsonObject.getJSONObject("user").getString("displayName");
                break;
            case STV:
                // note: this is the emote set item's name, which may differ from the emote name
                // (from what I understand an emote can be added to a channel using a different name)
                code = jsonObject.getString("name");

                JSONObject data = jsonObject.getJSONObject("data");

                JSONObject hostObj = data.getJSONObject("host");
                StringBuilder urlBuilder = new StringBuilder("https:"); // for some godforsaken reason this part is missing
                urlBuilder.append(hostObj.getString("url"));
                urlBuilder.append('/');

                JSONArray files = hostObj.getJSONArray("files");

                // the react native chat can not show animated webp files, but gif files
                String format = "WEBP";
                if (data.optBoolean("animated")) {
                    for (int i = 0; i < files.length(); i++) {
                        if (files.getJSONObject(i).getString("format").equals("GIF")) {
                            format = "GIF";
                            break;
                        }
                    }
                }

                // the following is semantically equivalent to this:
                // - filter out files of other formats
                // - if length > 1 choose the second option (the 2x size, which has a height of 64)
                //   else choose the first item (low quality)

                String smallerThan64 = null;
                String geThan64 = null;

                for (int i = 0; i < files.length(); i++) {
                    JSONObject emote = files.getJSONObject(i);
                    if (!emote.getString("format").equals(format)) {
                        continue;
                    }
                    String name = emote.getString("name");
                    if (emote.optInt("width") > 0 && emote.optInt("height") > 0) {
                        aspectRatio = (float) emote.getInt("width") / emote.getInt("height");
                    }
                    if (emote.getInt("height") >= 64 && geThan64 == null) {
                        geThan64 = name;
                    } else if (smallerThan64 == null) {
                        smallerThan64 = name;
                    }
                }
                String selected = geThan64 != null ? geThan64 : smallerThan64;
                if (selected == null) {
                    throw new JSONException("No usable 7TV image format for emote " + id);
                }
                urlBuilder.append(selected);
                url = urlBuilder.toString();
                // Record the selected container format separately from whether
                // its pixels animate (7TV can publish animated WebP files).
                imageType = "GIF".equals(format) ? "gif" : "webp";
                if (data.has("owner")) {
                    owner = data.getJSONObject("owner").getString("display_name");
                } else {
                    owner = null; // we don't get the owner
                }
                break;
            default:
                Log.w("LBTTVEmoteFromJson", "source unknown: " + source);
                url = "";
                code = "";
                imageType = "";
                owner = null;
        }

        Emote emote = new Emote(id, source, code, url, imageType, owner);
        emote.aspectRatio = aspectRatio;
        if (source == Emotes.Source.STV) {
            emote.animated = jsonObject.getJSONObject("data").optBoolean("animated");
            // 7TV v3: active emote flags and underlying emote metadata use
            // DIFFERENT zero-width bits. Preserve either indication.
            emote.zeroWidth = (jsonObject.optInt("flags") & 1) != 0
                    || (jsonObject.getJSONObject("data").optInt("flags") & 256) != 0
                    // A verified legacy zero-width emote can appear in some
                    // emote sets without either per-set flag. Match the 7TV
                    // ID, never the name (which can be aliased or duplicated).
                    || "01FE5VRARG000FV5W0DYEQ6JKP".equals(id); // SnowTime
        }
        return emote;
    }

    public static List<Emote> fromJSONArray(String json, Emotes.Source source) throws JSONException {
        JSONArray arr;
        if (source == Emotes.Source.STV) {
            JSONObject response = new JSONObject(json);
            JSONObject emoteSet;
            // global emotes already is only the emote set,
            // for user-related requests get it
            if (response.has("emote_set")) {
                emoteSet = response.getJSONObject("emote_set");
            } else {
                emoteSet = response;
            }
            arr = emoteSet.getJSONArray("emotes");
        } else {
            arr = new JSONArray(json);
        }
        return fromJSONArray(arr, source);
    }

    public static List<Emote> fromJSONArray(JSONArray arr, Emotes.Source source) throws JSONException {
        ArrayList<Emote> ret = new ArrayList<>(arr.length());
        for (int i = 0; i < arr.length(); i++) {
            JSONObject obj = arr.getJSONObject(i);
            ret.add(Emote.fromJson(obj, source));
        }
        return ret;
    }

    @Override
    public String toString() {
        return "Emote(" + id + ", " + code + ", " + url + " imageType: " + imageType + ")";
    }

    public boolean isAnimated() {
        return animated;
    }

    public EmoteModelAssetType getAssetType() {
        return this.isAnimated() ? EmoteModelAssetType.ANIMATED : EmoteModelAssetType.STATIC;
    }
}
