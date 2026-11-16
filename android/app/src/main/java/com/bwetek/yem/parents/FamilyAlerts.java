package com.bwetek.yem.parents;

import android.Manifest;
import android.app.Activity;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.webkit.CookieManager;
import android.widget.Toast;
import org.json.JSONArray;
import org.json.JSONObject;
import java.net.URL;
import javax.net.ssl.HttpsURLConnection;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.util.HashSet;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** Foreground-only native alerts; never a claim of background push delivery. */
final class FamilyAlerts {
    private static final String CHANNEL = "yem_family_updates";
    private static final int NOTIFICATION = 71;
    private final Activity activity;
    private final String origin;
    private final NotificationManager manager;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private boolean visible, inFlight;
    private long generation;
    private String account;
    private Set<String> baseline = new HashSet<>();
    private final Runnable tick = this::poll;

    FamilyAlerts(Activity activity, String origin) {
        this.activity = activity;
        this.origin = origin;
        manager = activity.getSystemService(NotificationManager.class);
        NotificationChannel channel = new NotificationChannel(CHANNEL, "Actualités YEM Parents", NotificationManager.IMPORTANCE_DEFAULT);
        channel.setDescription("Alertes génériques ; aucun nom, montant ou résultat scolaire");
        channel.setLockscreenVisibility(Notification.VISIBILITY_SECRET);
        manager.createNotificationChannel(channel);
    }

    private boolean optedIn() {
        return FamilyPush.prefs(activity).getBoolean("family_alerts", false);
    }

    void toggle() {
        boolean enabled = !optedIn();
        FamilyPush.prefs(activity).edit().putBoolean("family_alerts", enabled).apply();
        if (!enabled) FamilyPush.disable(activity, origin);
        reset();
        if (enabled && Build.VERSION.SDK_INT >= 33 && activity.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED)
            activity.requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, 71);
        Toast.makeText(activity, enabled ? "Alertes activées si autorisées par Android. Les push dépendent de la configuration YEM." : "Alertes désactivées.", Toast.LENGTH_LONG).show();
        if (visible && enabled) handler.post(tick);
    }

    void resume() {
        visible = true;
        reset();
        handler.post(tick);
    }

    void pause() {
        visible = false;
        reset();
    }

    void destroy() {
        pause();
        worker.shutdownNow();
    }

    private void reset() {
        generation++;
        account = null;
        baseline.clear();
        handler.removeCallbacks(tick);
        manager.cancel(NOTIFICATION);
    }

    private static String sessionCookie(String cookies) {
        if (cookies == null) return null;
        for (String part : cookies.split(";")) {
            String value = part.trim();
            if (value.startsWith("sessionid=") && value.length() > 10) return value;
        }
        return null;
    }

    private void poll() {
        handler.removeCallbacks(tick);
        if (!visible || !optedIn()) return;
        handler.postDelayed(tick, 60000);
        if (inFlight || !manager.areNotificationsEnabled()) return;
        if (Build.VERSION.SDK_INT >= 33 && activity.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) return;
        String session = sessionCookie(CookieManager.getInstance().getCookie(origin + "/"));
        if (session == null) { account = null; baseline.clear(); FamilyPush.clearBinding(activity); manager.cancel(NOTIFICATION); return; }
        long expected = generation;
        inFlight = true;
        worker.execute(() -> {
            String identity = null;
            Set<String> items = new HashSet<>();
            boolean valid = false;
            try {
                JSONObject me = get("/api/v1/auth/me", session);
                JSONObject user = me.optJSONObject("user");
                if (me.optBoolean("authenticated") && "parent".equals(me.optString("login_scope")) && user != null && !user.optBoolean("is_platform_admin")) {
                    identity = user.getString("id");
                    FamilyPush.refresh(activity, origin, session);
                    JSONArray rows = get("/api/v1/parents/notifications", session).getJSONArray("notifications");
                    for (int i = 0; i < rows.length(); i++) {
                        JSONObject row = rows.getJSONObject(i);
                        items.add(row.getString("kind") + ":" + row.getString("id") + ":" + row.optString("status"));
                    }
                    valid = true;
                }
            } catch (Exception ignored) { }
            String id = identity;
            boolean ok = valid;
            handler.post(() -> {
                inFlight = false;
                if (!visible || !optedIn() || expected != generation || !session.equals(sessionCookie(CookieManager.getInstance().getCookie(origin + "/")))) return;
                if (!ok) { account = null; baseline.clear(); FamilyPush.clearBinding(activity); manager.cancel(NOTIFICATION); return; }
                if (id.equals(account)) {
                    Set<String> added = new HashSet<>(items);
                    added.removeAll(baseline);
                    if (!added.isEmpty() && !FamilyPush.hasBinding(activity)) notifyUpdate();
                }
                // First reading or changed account is a silent baseline.
                account = id;
                baseline = items;
            });
        });
    }

    private JSONObject get(String route, String session) throws Exception {
        HttpsURLConnection connection = (HttpsURLConnection) new URL(origin + route).openConnection();
        try {
            connection.setInstanceFollowRedirects(false);
            connection.setConnectTimeout(10000);
            connection.setReadTimeout(15000);
            connection.setRequestProperty("Cookie", session);
            connection.setRequestProperty("Accept", "application/json");
            connection.setUseCaches(false);
            String type = connection.getContentType();
            if (connection.getResponseCode() != 200 || type == null || !type.startsWith("application/json")) throw new IOException("response");
            try (InputStream input = connection.getInputStream(); ByteArrayOutputStream body = new ByteArrayOutputStream()) {
                byte[] buffer = new byte[8192];
                int n;
                while ((n = input.read(buffer)) != -1) {
                    if (body.size() + n > 524288) throw new IOException("size");
                    body.write(buffer, 0, n);
                }
                return new JSONObject(new String(body.toByteArray(), StandardCharsets.UTF_8));
            }
        } finally { connection.disconnect(); }
    }

    private void notifyUpdate() {
        if (Build.VERSION.SDK_INT >= 33 && activity.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) return;
        if (!manager.areNotificationsEnabled()) return;
        Intent intent = new Intent(activity, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP);
        PendingIntent open = PendingIntent.getActivity(activity, 0, intent, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        // Never display school, child identity, finances or message text outside authenticated UI.
        manager.notify(NOTIFICATION, new Notification.Builder(activity, CHANNEL)
            .setSmallIcon(android.R.drawable.ic_dialog_info).setContentTitle("YEM Parents")
            .setContentText("Une nouvelle information est disponible dans votre espace.")
            .setContentIntent(open).setAutoCancel(true).setVisibility(Notification.VISIBILITY_SECRET).build());
    }
}
