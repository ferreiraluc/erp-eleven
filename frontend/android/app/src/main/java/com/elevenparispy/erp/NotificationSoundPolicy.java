package com.elevenparispy.erp;

/** Only the missing sound resource written by app 1.0.1 may be repaired. */
final class NotificationSoundPolicy {
    private NotificationSoundPolicy() {}

    static boolean useSystemDefault(String previousSound, String packageName, boolean userSetSound) {
        return !userSetSound && ("android.resource://" + packageName + "/raw/default").equals(previousSound);
    }
}
