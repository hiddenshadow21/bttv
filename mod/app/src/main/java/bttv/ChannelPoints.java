package bttv;

import android.util.Log;
import android.view.View.OnClickListener;

import java.util.HashSet;
import java.util.Set;

import bttv.settings.Settings;

/** Automatic claim of bonus channel points using Twitch's own claim interface. */
public final class ChannelPoints {
    private static final int MAX_RECORDED_CLAIMS = 128;
    private static final Set<String> attemptedClaimIds = new HashSet<>();

    private ChannelPoints() { }

    /** Kept for classic BTTV compatibility. */
    public static void autoRedeem(OnClickListener listener) {
        try {
            if (listener != null && Data.ctx != null &&
                    ResUtil.getBooleanFromSettings(Settings.AutoRedeemChannelPointsEnabled)) {
                listener.onClick(null);
            }
        } catch (Throwable error) {
            Log.w("LBTTVPoints318", "Legacy claim click failed", error);
        }
    }

    /** Called only when Twitch's 31.8.0 points presenter sees an available claim ID. */
    public static boolean shouldAutoRedeem(String claimId) {
        try {
            boolean enabled = Data.ctx != null &&
                    ResUtil.getBooleanFromSettings(Settings.AutoRedeemChannelPointsEnabled);
            boolean claim = once(claimId, enabled);
            if (claim) Log.i("LBTTVPoints318", "Attempting available bonus claim");
            return claim;
        } catch (Throwable error) {
            Log.w("LBTTVPoints318", "Auto-claim disabled after a preference failure", error);
            return false;
        }
    }

    static synchronized boolean once(String claimId, boolean enabled) {
        if (!enabled || claimId == null || claimId.isEmpty()) return false;
        if (!attemptedClaimIds.add(claimId)) return false;
        if (attemptedClaimIds.size() > MAX_RECORDED_CLAIMS) {
            attemptedClaimIds.clear();
            attemptedClaimIds.add(claimId);
        }
        return true;
    }
}
