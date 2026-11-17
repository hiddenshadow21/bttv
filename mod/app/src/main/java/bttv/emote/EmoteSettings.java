package bttv.emote;

import android.util.Log;

import bttv.Res;
import bttv.ResUtil;
import bttv.settings.Settings;

/**
 * Emote related settings, falls back to defaults when the settings can not be loaded.
 */
public class EmoteSettings {
    private static final String TAG = "LBTTVEmoteSettings";
    private static boolean settingsBroken = false;

    public static boolean bttvEnabled() {
        if (settingsBroken) {
            return true;
        }
        try {
            return ResUtil.getBooleanFromSettings(Settings.BTTVEmotesEnabled);
        } catch (Throwable t) {
            return onBroken(t);
        }
    }

    public static boolean ffzEnabled() {
        if (settingsBroken) {
            return true;
        }
        try {
            return ResUtil.getBooleanFromSettings(Settings.FFZEmotesEnabled);
        } catch (Throwable t) {
            return onBroken(t);
        }
    }

    public static boolean stvEnabled() {
        if (settingsBroken) {
            return true;
        }
        try {
            return ResUtil.getBooleanFromSettings(Settings.SevenTVEmotesEnabled);
        } catch (Throwable t) {
            return onBroken(t);
        }
    }

    public enum AnimationMode { FOREVER, ONCE, STATIC, DISABLED }

    public static AnimationMode animationMode() {
        if (settingsBroken) return AnimationMode.ONCE;
        try {
            if (ResUtil.selectedDropdownFromSettingsIs(Settings.GifRenderMode,
                    Res.strings.bttv_settings_gif_render_mode_disabled)) return AnimationMode.DISABLED;
            if (ResUtil.selectedDropdownFromSettingsIs(Settings.GifRenderMode,
                    Res.strings.bttv_settings_gif_render_mode_static)) return AnimationMode.STATIC;
            if (ResUtil.selectedDropdownFromSettingsIs(Settings.GifRenderMode,
                    Res.strings.bttv_settings_gif_render_mode_animate_forever)) return AnimationMode.FOREVER;
            return AnimationMode.ONCE;
        } catch (Throwable t) {
            onBroken(t);
            return AnimationMode.ONCE;
        }
    }

    public static boolean gifEnabled() {
        return animationMode() != AnimationMode.DISABLED;
    }

    private static boolean onBroken(Throwable t) {
        settingsBroken = true;
        Log.w(TAG, "settings unavailable, using defaults", t);
        return true;
    }
}
