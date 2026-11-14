package com.elevenparispy.erp;

import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Notification;
import android.content.Intent;
import android.net.Uri;
import android.os.Build;
import android.provider.Settings;
import androidx.core.app.NotificationManagerCompat;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

/** Own-channel setup/settings only; never grants OS permission or deletes channels. */
@CapacitorPlugin(name = "ElevenNotificationSettings")
public class ElevenNotificationSettingsPlugin extends Plugin {
    private static final String CHANNEL = "eleven-updates-v2";
    private static final String LEGACY_CHANNEL = "eleven-updates";

    @PluginMethod
    public void prepareChannel(PluginCall call) {
        NotificationManager manager = getContext().getSystemService(NotificationManager.class);
        if (manager == null) {
            call.reject("Notification settings are unavailable", "SETTINGS_UNAVAILABLE");
            return;
        }
        // Android channels are immutable after creation. Preserve a channel the
        // user already configured, and keep v1 for older installed app versions.
        if (manager.getNotificationChannel(CHANNEL) == null) {
            NotificationChannel previous = manager.getNotificationChannel(LEGACY_CHANNEL);
            NotificationChannel channel = new NotificationChannel(CHANNEL, "Avisos da Eleven",
                previous == null ? NotificationManager.IMPORTANCE_DEFAULT : previous.getImportance());
            channel.setDescription("Vendas, rastreios e recados da equipe");
            channel.setLockscreenVisibility(Notification.VISIBILITY_PRIVATE);
            if (previous != null) {
                channel.setLockscreenVisibility(previous.getLockscreenVisibility());
                channel.setShowBadge(previous.canShowBadge());
                channel.setGroup(previous.getGroup());
                channel.setBypassDnd(previous.canBypassDnd());
                channel.setLightColor(previous.getLightColor());
                channel.enableLights(previous.shouldShowLights());
                channel.setVibrationPattern(previous.getVibrationPattern());
                channel.enableVibration(previous.shouldVibrate());
                Uri sound = previous.getSound();
                boolean userSetSound = Build.VERSION.SDK_INT >= Build.VERSION_CODES.R && previous.hasUserSetSound();
                if (!NotificationSoundPolicy.useSystemDefault(sound == null ? null : sound.toString(),
                        getContext().getPackageName(), userSetSound)) {
                    // null is an intentional silent channel; never turn it on.
                    channel.setSound(sound, previous.getAudioAttributes());
                }
            }
            // No setSound for fresh installs/the known invalid v1 URI. Android's
            // constructor uses Settings.System.DEFAULT_NOTIFICATION_URI; passing
            // "default" to Capacitor would instead reference a missing raw file.
            manager.createNotificationChannel(channel);
        }
        JSObject result = new JSObject();
        result.put("channelId", CHANNEL);
        call.resolve(result);
    }

    @PluginMethod
    public void status(PluginCall call) {
        NotificationManager manager = getContext().getSystemService(NotificationManager.class);
        NotificationChannel channel = manager == null ? null : manager.getNotificationChannel(CHANNEL);
        JSObject result = new JSObject();
        result.put("enabled", NotificationManagerCompat.from(getContext()).areNotificationsEnabled()
            && (channel == null || channel.getImportance() != NotificationManager.IMPORTANCE_NONE));
        call.resolve(result);
    }

    @PluginMethod
    public void open(PluginCall call) {
        getActivity().runOnUiThread(() -> {
            try {
                NotificationManager manager = getContext().getSystemService(NotificationManager.class);
                boolean hasChannel = manager != null && manager.getNotificationChannel(CHANNEL) != null;
                boolean appEnabled = NotificationManagerCompat.from(getContext()).areNotificationsEnabled();
                Intent intent = new Intent(hasChannel && appEnabled
                    ? Settings.ACTION_CHANNEL_NOTIFICATION_SETTINGS : Settings.ACTION_APP_NOTIFICATION_SETTINGS)
                    .putExtra(Settings.EXTRA_APP_PACKAGE, getContext().getPackageName());
                if (hasChannel && appEnabled) intent.putExtra(Settings.EXTRA_CHANNEL_ID, CHANNEL);
                getActivity().startActivity(intent);
                call.resolve();
            } catch (Exception unavailable) {
                try {
                    Intent fallback = new Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                        Uri.parse("package:" + getContext().getPackageName()));
                    getActivity().startActivity(fallback);
                    call.resolve();
                } catch (Exception ignored) {
                    call.reject("Notification settings are unavailable", "SETTINGS_UNAVAILABLE");
                }
            }
        });
    }
}
