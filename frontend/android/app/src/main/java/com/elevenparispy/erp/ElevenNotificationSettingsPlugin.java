package com.elevenparispy.erp;

import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.content.Intent;
import android.net.Uri;
import android.provider.Settings;
import androidx.core.app.NotificationManagerCompat;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

/** Read/open only this app's notification settings; never changes OS permission. */
@CapacitorPlugin(name = "ElevenNotificationSettings")
public class ElevenNotificationSettingsPlugin extends Plugin {
    private static final String CHANNEL = "eleven-updates";

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
                Intent intent = new Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS)
                    .putExtra(Settings.EXTRA_APP_PACKAGE, getContext().getPackageName());
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
