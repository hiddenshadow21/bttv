package bttv.settings.abstractions;

import android.content.Context;

import bttv.ResUtil;
import bttv.settings.UserPreferences;
import tv.twitch.android.shared.ui.menus.subscription.SubMenuModel;
import tv.twitch.android.models.settings.SettingsDestination;

public class Link {
    public static SubMenuModel fromEntry(Context context, UserPreferences.Entry.LinkEntry entry) {
        // Legacy settings navigation only. The active 31.8.0 Compose overlay
        // never calls this method. Resolve the old destination lazily so the
        // Settings enum and live chat remain loadable without this Twitch type.
        SettingsDestination destination = null;
        if (entry.destination != null) {
            try {
                destination = SettingsDestination.valueOf(entry.destination);
            } catch (IllegalArgumentException ignored) {
                // A destination may no longer exist on another Twitch release.
            }
        }
        return new SubMenuModel(
                ResUtil.getLocaleString(context, entry.primaryTextResource),
                ResUtil.getLocaleString(context, entry.secondaryTextResource),
                ResUtil.getLocaleString(context, entry.auxiliaryTextResource),
                destination,
                true
        );
    }
}
