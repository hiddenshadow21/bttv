package bttv.settings;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Context;
import android.content.ContextWrapper;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.util.Log;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Switch;
import android.widget.TextView;
import android.widget.Toast;

import java.lang.ref.WeakReference;

import java.util.ArrayList;

import bttv.Data;
import bttv.Res;
import bttv.ResUtil;

/** Open BTTV preferences from the clickable Compose settings row injected
 * into Twitch 31.8.0's MainSettingsFragmentV2 scrolling content.
 */
public final class SettingsOverlay318 {
    private static final String TAG = "LBTTVSettings318";
    private static final int BACKGROUND = 0xFF18181B;
    private static final int FOREGROUND = Color.WHITE;
    private static final int SECONDARY = 0xFFADADB8;
    private static final int ACCENT = 0xFFBF94FF;
    // Do not keep Activities alive after the settings screen is dismissed.
    private static volatile WeakReference<Activity> activeSettingsHost =
            new WeakReference<>(null);

    private SettingsOverlay318() { }

    public static String versionLabel() {
        String version = "";
        Context context = Data.ctx;
        if (context != null) {
            try {
                version = context.getPackageManager()
                        .getPackageInfo(context.getPackageName(), 0).versionName;
            } catch (PackageManager.NameNotFoundException ignored) { }
        }
        return "BTTV" + (version == null || version.isEmpty() ? "" : " " + version)
                + " (Twitch v31.8.0)";
    }

    /** Called from MainSettingsFragmentV2.onCreateView with its requireContext().
     * This mirrors the working slop branch's ComposeView.getContext() source,
     * but keeps the row inside the Compose scrolling list.
     */
    public static void rememberContext(Context context) {
        Activity activity = findActivity(context);
        if (activity != null) {
            activeSettingsHost = new WeakReference<>(activity);
            Log.i(TAG, "Captured settings host Activity");
        } else {
            Log.w(TAG, "Settings Fragment context did not resolve to an Activity");
        }
    }

    private static Activity findActivity(Context context) {
        for (int i = 0; i < 30 && context != null; i++) {
            if (context instanceof Activity) {
                Activity activity = (Activity) context;
                return activity.isFinishing() || activity.isDestroyed() ? null : activity;
            }
            if (!(context instanceof ContextWrapper)) break;
            Context base = ((ContextWrapper) context).getBaseContext();
            if (base == context) break;
            context = base;
        }
        return null;
    }

    /** Called by the normal clickable Compose settings-list row. */
    public static void open(Context context) {
        Log.i(TAG, "BTTV settings row clicked");
        Activity activity = findActivity(context);
        if (activity == null) {
            WeakReference<Activity> ref = activeSettingsHost;
            activity = ref == null ? null : ref.get();
            if (activity != null && (activity.isFinishing() || activity.isDestroyed())) {
                activity = null;
            }
        }
        if (activity == null) {
            Log.e(TAG, "No active Activity for BTTV settings; cannot show dialog");
            if (context != null) {
                Toast.makeText(context, "BTTV settings: no active screen", Toast.LENGTH_SHORT).show();
            }
            return;
        }
        final Activity host = activity;
        host.runOnUiThread(() -> showSettings(host));
    }

    private static void showSettings(Activity activity) {
        if (activity.isFinishing() || activity.isDestroyed()) return;
        try {
            ScrollView scroll = new ScrollView(activity);
            scroll.setFillViewport(false);
            scroll.setBackgroundColor(BACKGROUND);
            LinearLayout rows = new LinearLayout(activity);
            rows.setOrientation(LinearLayout.VERTICAL);
            rows.setPadding(dp(activity, 20), dp(activity, 14), dp(activity, 20), dp(activity, 18));
            scroll.addView(rows);
            addHeading(activity, rows, "Emotes");
            addSwitch(activity, rows, "BetterTTV emotes", Settings.BTTVEmotesEnabled);
            addSwitch(activity, rows, "FrankerFaceZ emotes", Settings.FFZEmotesEnabled);
            addSwitch(activity, rows, "7TV emotes", Settings.SevenTVEmotesEnabled);
            addGifMode(activity, rows);
            addHeading(activity, rows, "Chat");
            addSwitch(activity, rows, "Always show chat timestamps", Settings.AlwaysShowChatTimestamps);
            TextView hint = new TextView(activity);
            hint.setText("Applies to new live messages. Reopen the stream after changing settings.");
            hint.setTextSize(12);
            hint.setTextColor(SECONDARY);
            hint.setPadding(0, dp(activity, 8), 0, dp(activity, 12));
            rows.addView(hint);
            AlertDialog dialog = new AlertDialog.Builder(activity)
                    .setTitle("BTTV settings")
                    .setView(scroll)
                    .setPositiveButton("Done", (ignored, which) -> { })
                    .create();
            dialog.setOnShowListener(ignored -> {
                dialog.getButton(AlertDialog.BUTTON_POSITIVE).setTextColor(ACCENT);
            });
            dialog.show();
            Log.i(TAG, "BTTV settings dialog shown");
        } catch (Throwable error) {
            Log.e(TAG, "Cannot display BTTV settings", error);
        }
    }

    private static void addHeading(Context ctx, LinearLayout root, String title) {
        TextView heading = new TextView(ctx);
        heading.setText(title);
        heading.setTextSize(13);
        heading.setTextColor(ACCENT);
        heading.setPadding(0, dp(ctx, 15), 0, dp(ctx, 8));
        root.addView(heading);
    }

    private static void addSwitch(Context ctx, LinearLayout root, String title, Settings setting) {
        final UserPreferences.Entry.BoolEntry preference =
                (UserPreferences.Entry.BoolEntry) setting.entry;
        Switch toggle = new Switch(ctx);
        toggle.setText(title);
        toggle.setTextSize(16);
        toggle.setTextColor(FOREGROUND);
        toggle.setMinHeight(dp(ctx, 54));
        toggle.setPadding(0, dp(ctx, 8), 0, dp(ctx, 8));
        toggle.setChecked(preference.get(ctx).get());
        toggle.setOnCheckedChangeListener((button, checked) -> {
            preference.set(ctx, new UserPreferences.Entry.BoolValue(checked));
            Log.i(TAG, "Changed " + preference.key + " to " + checked);
        });
        root.addView(toggle, new LinearLayout.LayoutParams(-1, -2));
    }

    private static void addGifMode(Activity activity, LinearLayout root) {
        TextView choice = new TextView(activity);
        choice.setText("Animated emotes");
        choice.setTextSize(16);
        choice.setTextColor(FOREGROUND);
        choice.setGravity(android.view.Gravity.CENTER_VERTICAL);
        choice.setMinHeight(dp(activity, 54));
        choice.setOnClickListener(view -> {
            try {
                UserPreferences.Entry.DropDownEntry pref =
                        (UserPreferences.Entry.DropDownEntry) Settings.GifRenderMode.entry;
                UserPreferences.Entry.DropDownValue value = pref.get(activity);
                ArrayList<Res.strings> options = value.get();
                String[] labels = new String[options.size()];
                int selected = options.indexOf(value.getSelected());
                for (int i = 0; i < options.size(); i++) {
                    try { labels[i] = ResUtil.getLocaleString(activity, options.get(i)); }
                    catch (Throwable t) { labels[i] = options.get(i).name(); }
                }
                new AlertDialog.Builder(activity)
                        .setTitle("Animated emotes")
                        .setSingleChoiceItems(labels, selected, (dialog, index) -> {
                            pref.set(activity, value.newWithSelected(options.get(index)));
                            dialog.dismiss();
                        })
                        .setNegativeButton("Cancel", null)
                        .show();
            } catch (Throwable error) {
                Log.e(TAG, "Cannot open animated-emote preferences", error);
            }
        });
        root.addView(choice);
    }

    private static int dp(Context ctx, int value) {
        return Math.round(value * ctx.getResources().getDisplayMetrics().density);
    }
}
