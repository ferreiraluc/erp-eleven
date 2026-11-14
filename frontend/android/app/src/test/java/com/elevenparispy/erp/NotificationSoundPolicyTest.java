package com.elevenparispy.erp;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;
import org.junit.Test;

public class NotificationSoundPolicyTest {
    private static final String PACKAGE = "com.elevenparispy.erp";

    @Test
    public void repairsOnlyOurUnselectedMissingRawResource() {
        assertTrue(NotificationSoundPolicy.useSystemDefault("android.resource://" + PACKAGE + "/raw/default", PACKAGE, false));
        assertFalse(NotificationSoundPolicy.useSystemDefault("android.resource://" + PACKAGE + "/raw/default", PACKAGE, true));
        assertFalse(NotificationSoundPolicy.useSystemDefault("android.resource://another.app/raw/default", PACKAGE, false));
    }

    @Test
    public void preservesSilenceAndCustomOrSystemSounds() {
        for (String sound : new String[] { null, "", "content://settings/system/notification_sound", "content://media/internal/audio/media/7" }) {
            assertFalse(NotificationSoundPolicy.useSystemDefault(sound, PACKAGE, false));
            assertFalse(NotificationSoundPolicy.useSystemDefault(sound, PACKAGE, true));
        }
    }
}
