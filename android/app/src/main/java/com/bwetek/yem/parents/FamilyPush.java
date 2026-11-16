package com.bwetek.yem.parents;

import android.content.Context;
import android.content.SharedPreferences;
import android.app.NotificationManager;
import android.webkit.CookieManager;
import com.google.firebase.FirebaseApp;
import com.google.firebase.messaging.FirebaseMessaging;
import com.google.android.gms.tasks.Tasks;
import org.json.JSONObject;
import javax.net.ssl.HttpsURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.concurrent.TimeUnit;

/** Optional FCM device registration. No token or credentials are logged. */
final class FamilyPush {
    private static final long VALID_MS = 8L * 60 * 60 * 1000;
    private static final Object LOCK = new Object();
    private static long lastTry;

    static SharedPreferences prefs(Context context) {
        return context.getSharedPreferences("yem_family_alerts", Context.MODE_PRIVATE);
    }

    private static boolean configured(Context context) {
        return !FirebaseApp.getApps(context).isEmpty();
    }

    private static String namedCookie(String cookies, String name) {
        if (cookies == null) return null;
        for (String part : cookies.split(";")) {
            String trimmed = part.trim();
            if (trimmed.startsWith(name + "=")) return trimmed;
        }
        return null;
    }

    private static String sessionDigest(String session) throws Exception {
        byte[] bytes = MessageDigest.getInstance("SHA-256").digest(session.getBytes(StandardCharsets.UTF_8));
        StringBuilder result = new StringBuilder();
        for (byte b : bytes) result.append(String.format(java.util.Locale.ROOT, "%02x", b & 0xff));
        return result.toString();
    }

    static boolean hasBinding(Context context) {
        SharedPreferences store = prefs(context);
        if (!store.getBoolean("family_alerts", false) || store.getLong("bound_until", 0) <= System.currentTimeMillis()) return false;
        try {
            String session = namedCookie(CookieManager.getInstance().getCookie("https://yem-api.onrender.com/"), "sessionid");
            return session != null && sessionDigest(session).equals(store.getString("bound_session", ""));
        } catch (Exception ignored) { return false; }
    }

    static void clearBinding(Context context) {
        prefs(context).edit().remove("bound_until").remove("bound_session").apply();
        context.getSystemService(NotificationManager.class).cancel(72);
    }

    /** Called on the foreground inbox worker only after authenticated /auth/me. */
    static void refresh(Context context, String origin, String session) {
        if (!configured(context) || !prefs(context).getBoolean("family_alerts", false)) return;
        synchronized (LOCK) {
            long now = System.currentTimeMillis();
            if (now - lastTry < 60_000L) return;
            if (hasBinding(context) && prefs(context).getLong("bound_until", 0) - now > VALID_MS - 15 * 60_000L) return;
            lastTry = now;
            try {
                // Auto-init remains off; request token explicitly after consent.
                String token = Tasks.await(FirebaseMessaging.getInstance().getToken(), 15, TimeUnit.SECONDS);
                if (!prefs(context).getBoolean("family_alerts", false)) return;
                String cookies = CookieManager.getInstance().getCookie(origin + "/");
                if (!session.equals(namedCookie(cookies, "sessionid"))) return;
                String csrf = namedCookie(cookies, "csrftoken");
                if (csrf == null) return; // existing Django auth/me sets the cookie
                JSONObject data = new JSONObject().put("token", token);
                int code = request(origin, "POST", session, csrf, data.toString());
                if ((code == 200 || code == 201) && prefs(context).getBoolean("family_alerts", false)) {
                    String current = namedCookie(CookieManager.getInstance().getCookie(origin + "/"), "sessionid");
                    if (session.equals(current))
                        prefs(context).edit().putString("bound_session", sessionDigest(session)).putLong("bound_until", now + VALID_MS).apply();
                } else if (code == 401 || code == 403 || code == 409 || code == 503) clearBinding(context);
            } catch (Exception ignored) { /* Inbox polling still works. */ }
        }
    }

    static void disable(Context context, String origin) {
        clearBinding(context);
        if (!configured(context)) return;
        Context app = context.getApplicationContext();
        String cookies = CookieManager.getInstance().getCookie(origin + "/");
        String session = namedCookie(cookies, "sessionid");
        String csrf = namedCookie(cookies, "csrftoken");
        new Thread(() -> {
            synchronized (LOCK) {
                if (prefs(app).getBoolean("family_alerts", false)) return;
                try {
                    if (session != null && csrf != null) request(origin, "DELETE", session, csrf, null);
                } catch (Exception ignored) { }
                try { Tasks.await(FirebaseMessaging.getInstance().deleteToken(), 15, TimeUnit.SECONDS); }
                catch (Exception ignored) { }
                lastTry = 0;
            }
        }, "yem-push-optout").start();
    }

    private static int request(String origin, String method, String session, String csrf, String body) throws Exception {
        HttpsURLConnection c = (HttpsURLConnection) new URL(origin + "/api/v1/parents/push-device").openConnection();
        try {
            c.setRequestMethod(method);
            c.setInstanceFollowRedirects(false);
            c.setConnectTimeout(10000);
            c.setReadTimeout(10000);
            c.setUseCaches(false);
            c.setRequestProperty("Cookie", session + "; " + csrf);
            c.setRequestProperty("X-CSRFToken", csrf.substring("csrftoken=".length()));
            c.setRequestProperty("Origin", origin);
            c.setRequestProperty("Referer", origin + "/parents-app/");
            c.setRequestProperty("Accept", "application/json");
            if (body != null) {
                c.setDoOutput(true);
                c.setRequestProperty("Content-Type", "application/json");
                byte[] data = body.getBytes(StandardCharsets.UTF_8);
                c.setFixedLengthStreamingMode(data.length);
                try (java.io.OutputStream out = c.getOutputStream()) { out.write(data); }
            }
            return c.getResponseCode();
        } finally { c.disconnect(); }
    }
}
