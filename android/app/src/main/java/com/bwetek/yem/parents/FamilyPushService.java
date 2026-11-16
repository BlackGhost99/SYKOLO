package com.bwetek.yem.parents;

import android.Manifest;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;
import com.google.firebase.messaging.FirebaseMessagingService;
import com.google.firebase.messaging.RemoteMessage;

/** Receives generic data-only messages, never private student information. */
public final class FamilyPushService extends FirebaseMessagingService {
    @Override public void onNewToken(String token) {
        // Refresh on next authenticated foreground poll; don't persist or log token.
        FamilyPush.clearBinding(this);
    }

    @Override public void onMessageReceived(RemoteMessage message) {
        if (!"family_update".equals(message.getData().get("kind")) || !FamilyPush.hasBinding(this)) return;
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) return;
        NotificationManager manager = getSystemService(NotificationManager.class);
        if (!manager.areNotificationsEnabled()) return;
        NotificationChannel channel = new NotificationChannel("yem_family_updates", "Actualités YEM Parents", NotificationManager.IMPORTANCE_DEFAULT);
        channel.setLockscreenVisibility(Notification.VISIBILITY_SECRET);
        manager.createNotificationChannel(channel);
        PendingIntent open = PendingIntent.getActivity(this, 0,
                new Intent(this, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        manager.notify(72, new Notification.Builder(this, "yem_family_updates")
                .setSmallIcon(android.R.drawable.ic_dialog_info)
                .setContentTitle("YEM Parents")
                .setContentText("Une nouvelle information est disponible dans votre espace.")
                .setContentIntent(open).setAutoCancel(true).setVisibility(Notification.VISIBILITY_SECRET).build());
    }
}
