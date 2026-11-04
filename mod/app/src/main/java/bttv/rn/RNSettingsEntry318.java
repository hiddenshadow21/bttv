package bttv.rn;

import android.content.Context;
import android.content.res.TypedArray;
import android.graphics.Color;
import android.util.Log;
import android.view.View;
import android.view.ViewGroup;
import android.widget.LinearLayout;
import android.widget.TextView;

import bttv.settings.SettingsNavigation;

/** A visible entry in the actual Compose-backed Twitch 31.8 settings screen. */
public final class RNSettingsEntry318 {
    private static final String TAG = "BTTV318RN";
    private RNSettingsEntry318() {}

    public static View wrap(final View composeView) {
        if (composeView == null) return null;
        try {
            final Context context = composeView.getContext();
            LinearLayout root = new LinearLayout(context);
            root.setOrientation(LinearLayout.VERTICAL);
            root.setLayoutParams(new ViewGroup.LayoutParams(-1, -1));

            TextView item = new TextView(context);
            item.setText("BTTV Settings");
            item.setTextSize(16f);
            item.setContentDescription("Open BTTV Settings");
            item.setClickable(true);
            item.setFocusable(true);
            int pad = (int) (context.getResources().getDisplayMetrics().density * 20 + .5f);
            item.setPadding(pad, pad, pad, pad);
            TypedArray colors = context.obtainStyledAttributes(new int[]{android.R.attr.textColorPrimary});
            try { item.setTextColor(colors.getColor(0, Color.WHITE)); }
            finally { colors.recycle(); }
            item.setOnClickListener(new View.OnClickListener() {
                @Override public void onClick(View ignored) {
                    if (!SettingsNavigation.open(context)) {
                        Log.w(TAG, "BTTV Settings launch unavailable: context not an active Activity");
                    }
                }
            });
            root.addView(item, new LinearLayout.LayoutParams(-1, -2));
            // Preserve Compose layout and scrolling: it still gets all remaining height.
            root.addView(composeView, new LinearLayout.LayoutParams(-1, 0, 1f));
            Log.i(TAG, "Visible BTTV Settings row installed in MainSettingsFragmentV2");
            return root;
        } catch (Throwable t) {
            Log.e(TAG, "Could not wrap Compose settings; retaining stock view", t);
            return composeView;
        }
    }
}
