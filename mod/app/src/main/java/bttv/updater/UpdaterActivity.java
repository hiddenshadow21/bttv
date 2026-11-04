package bttv.updater;

import android.content.Intent;
import android.content.pm.ActivityInfo;
import android.content.res.Resources;
import android.net.Uri;
import android.os.Bundle;
import android.util.Log;
import android.widget.ProgressBar;
import android.widget.TextView;

import androidx.appcompat.app.AppCompatActivity;
import androidx.core.content.FileProvider;


import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.URL;
import java.net.HttpURLConnection;

import bttv.Res;
import bttv.ResUtil;
import bttv.Util;
import ru.noties.markwon.Markwon;
import ru.noties.markwon.SpannableConfiguration;

import static android.content.Intent.FLAG_ACTIVITY_NEW_TASK;
import static android.content.Intent.FLAG_GRANT_READ_URI_PERMISSION;

public class UpdaterActivity extends AppCompatActivity {

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_LOCKED);

        Resources res = getResources();
        int bttv_updater_activity = res.getIdentifier("bttv_updater_activity", "layout", getPackageName());
        int bttv_updater_activity_title = res.getIdentifier("bttv_updater_activity_title", "id", getPackageName());
        int bttv_updater_activity_body = res.getIdentifier("bttv_updater_activity_body", "id", getPackageName());
        int bttv_updater_activity_pb = res.getIdentifier("bttv_updater_activity_pb", "id", getPackageName());

        setContentView(bttv_updater_activity);

        Intent intent = getIntent();
        String newVersion = intent.getStringExtra("new_version");
        String body = intent.getStringExtra("body");
        String url = intent.getStringExtra("url");

        TextView titleView = findViewById(bttv_updater_activity_title);

        String titleTemplate = ResUtil.getLocaleString(this, Res.strings.bttv_updater_downloading_version);
        titleView.setText(String.format(titleTemplate, newVersion));

        TextView bodyView = findViewById(bttv_updater_activity_body);
        bodyView.setText(Markwon.markdown(SpannableConfiguration.create(this), body));

        ProgressBar bar = findViewById(bttv_updater_activity_pb);

        startDownload(url, bar);

    }

    // Twitch 31.8 compatibility: the old unshaded OkHttp/Okio runtime is unavailable.
    // Download updates as binary streams, NOT through Network.get() (JSON-only).
    private void startDownload(final String url, final ProgressBar bar) {
        new Thread(new Runnable() {
            @Override public void run() {
                final File partial = new File(getCacheDir(), "bttv.apk.partial");
                final File apk = new File(getCacheDir(), "bttv.apk");
                try {
                    downloadUpdateApk(url, partial, bar);
                    if (apk.exists() && !apk.delete()) {
                        throw new IOException("Could not replace the cached update APK");
                    }
                    if (!partial.renameTo(apk)) {
                        throw new IOException("Could not finalize downloaded APK");
                    }
                    final Intent install = new Intent("android.intent.action.INSTALL_PACKAGE");
                    final Uri uri = FileProvider.getUriForFile(
                        UpdaterActivity.this, "tv.twitch.bttvandroid.app.provider", apk);
                    install.setDataAndType(uri, "application/vnd.android.package-archive");
                    install.setFlags(FLAG_ACTIVITY_NEW_TASK | FLAG_GRANT_READ_URI_PERMISSION);
                    runOnUiThread(new Runnable() {
                        @Override public void run() { startActivity(install); }
                    });
                } catch (final Exception e) {
                    partial.delete();
                    Log.e("LBTTVUpdaterActivity", "Update failed", e);
                    runOnUiThread(new Runnable() {
                        @Override public void run() { Util.showError(UpdaterActivity.this, e); }
                    });
                }
            }
        }, "bttv-update-download").start();
    }

    private static boolean trustedReleaseUrl(URL url) {
        if (!"https".equalsIgnoreCase(url.getProtocol()) ||
                url.getUserInfo() != null ||
                (url.getPort() != -1 && url.getPort() != 443)) return false;
        final String host = url.getHost().toLowerCase(java.util.Locale.ROOT);
        if ("github.com".equals(host)) {
            return url.getPath().startsWith("/bttv-android/bttv/releases/download/");
        }
        return "release-assets.githubusercontent.com".equals(host) ||
               "objects.githubusercontent.com".equals(host);
    }

    private static HttpURLConnection openUpdateStream(String initialUrl) throws IOException {
        URL current = new URL(initialUrl);
        for (int hop = 0; hop <= 5; hop++) {
            if (!trustedReleaseUrl(current)) {
                throw new IOException("Untrusted update-download location");
            }
            HttpURLConnection conn = (HttpURLConnection) current.openConnection();
            conn.setConnectTimeout(30000);
            conn.setReadTimeout(30000);
            conn.setInstanceFollowRedirects(false);
            conn.setRequestMethod("GET");
            conn.setRequestProperty("User-Agent", "bttv-android/0.44.0-beta");
            final int code;
            try { code = conn.getResponseCode(); }
            catch (IOException e) { conn.disconnect(); throw e; }
            if (code == 301 || code == 302 || code == 303 || code == 307 || code == 308) {
                String location = conn.getHeaderField("Location");
                conn.disconnect();
                if (location == null) throw new IOException("Update redirect without Location");
                current = new URL(current, location);
                continue;
            }
            if (code != 200) {
                conn.disconnect();
                throw new IOException("Update download HTTP " + code);
            }
            return conn;
        }
        throw new IOException("Too many update-download redirects");
    }

    private void downloadUpdateApk(String url, File output, final ProgressBar bar) throws IOException {
        final long maxBytes = 350L * 1024 * 1024;
        HttpURLConnection conn = openUpdateStream(url);
        try {
            long total = conn.getContentLengthLong();
            if (total > maxBytes) throw new IOException("Update APK exceeds size limit");
            long copied = 0;
            int lastPercent = -1;
            try (InputStream in = conn.getInputStream();
                 FileOutputStream out = new FileOutputStream(output)) {
                byte[] buffer = new byte[32768];
                int n;
                while ((n = in.read(buffer)) != -1) {
                    copied += n;
                    if (copied > maxBytes) throw new IOException("Update APK exceeds size limit");
                    out.write(buffer, 0, n);
                    if (total > 0) {
                        int percent = (int) Math.min(100, (100L * copied) / total);
                        if (percent != lastPercent) {
                            lastPercent = percent;
                            final int progress = percent;
                            runOnUiThread(new Runnable() {
                                @Override public void run() { bar.setProgress(progress); }
                            });
                        }
                    }
                }
            }
            if (copied < 4 || (total > 0 && copied != total)) {
                throw new IOException("Truncated update APK");
            }
            // APKs are ZIP files. Reject unexpected HTML/API error pages.
            try (FileInputStream file = new FileInputStream(output)) {
                byte[] magic = new byte[4];
                if (file.read(magic) != 4 || magic[0] != 'P' || magic[1] != 'K' ||
                        magic[2] != 3 || magic[3] != 4) {
                    throw new IOException("Downloaded update is not an APK/ZIP");
                }
            }
            Log.i("LBTTVUpdaterActivity", "Update APK downloaded, bytes=" + copied);
        } finally {
            conn.disconnect();
        }
    }
}
