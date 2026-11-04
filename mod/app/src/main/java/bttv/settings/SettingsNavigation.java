package bttv.settings;

import android.app.Activity;
import android.content.Context;
import android.content.ContextWrapper;
import android.content.Intent;
import android.view.Menu;

import java.util.Collections;
import java.util.IdentityHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.WeakHashMap;

import bttv.Res;
import bttv.ResUtil;

/** Navigation shared by the two native main Settings row implementations. */
public final class SettingsNavigation {
    // Only final native a120 models are registered; they use Object identity.
    // Boolean values cannot retain an Activity, presenter, or their weak key.
    private static final Map<Object, Boolean> nativeRows = new WeakHashMap<>();

    private SettingsNavigation() {
    }

    public static Activity findActivity(Context context) {
        try {
            Set<Context> seen = Collections.newSetFromMap(new IdentityHashMap<>());
            while (context != null && seen.add(context)) {
                if (context instanceof Activity) {
                    Activity activity = (Activity) context;
                    return activity.isFinishing() || activity.isDestroyed() ? null : activity;
                }
                if (!(context instanceof ContextWrapper)) {
                    return null;
                }
                context = ((ContextWrapper) context).getBaseContext();
            }
        } catch (Throwable ignored) {
            // Invalid/detached contexts must not launch a different task.
        }
        return null;
    }

    public static boolean open(Context context) {
        Activity activity = findActivity(context);
        if (activity == null) {
            return false;
        }
        try {
            activity.startActivity(new Intent(activity, SettingsActivity.class));
            return true;
        } catch (Throwable ignored) {
            return false;
        }
    }

    public static String nativeEntryTitle(Context context) {
        return ResUtil.getLocaleString(context, Res.strings.bttv_settings_entry_title);
    }

    public static synchronized void markNativeRow(Object row) {
        if (row != null) {
            nativeRows.put(row, Boolean.TRUE);
        }
    }

    public static synchronized boolean isNativeRow(Object row) {
        return row != null && nativeRows.containsKey(row);
    }

    public static synchronized boolean hasNativeRow(List<?> rows) {
        if (rows == null) {
            return true;
        }
        for (Object row : rows) {
            if (isNativeRow(row)) {
                return true;
            }
        }
        return false;
    }

    public static void install(final Activity activity, Menu menu) {
        // BTTV 31.8.0 diagnostic fallback for the renamed settings navigation.
        // This only adds an overflow item on a SettingsActivity that calls install().
        if (activity == null || menu == null) {
            return;
        }
        try {
            final int itemId = 0x42747476;
            if (menu.findItem(itemId) != null) {
                return;
            }
            android.view.MenuItem item = menu.add(Menu.NONE, itemId, Menu.NONE, "BTTV Settings");
            item.setShowAsAction(android.view.MenuItem.SHOW_AS_ACTION_NEVER);
            item.setOnMenuItemClickListener(new android.view.MenuItem.OnMenuItemClickListener() {
                @Override
                public boolean onMenuItemClick(android.view.MenuItem clicked) {
                    return open(activity);
                }
            });
            android.util.Log.i("BTTV318Diag", "SettingsActivity overflow fallback installed");
        } catch (Throwable failure) {
            android.util.Log.e("BTTV318Diag", "SettingsActivity overflow fallback failed", failure);
        }
    }
}
