package com.pluto.app

import android.app.Activity
import android.app.Application
import android.os.Bundle
import com.pluto.app.data.auth.TokenStore

class PlutoApplication : Application() {
    private var startedActivities = 0

    override fun onCreate() {
        super<Application>.onCreate()
        TokenStore.init(this)
        TokenStore.consumePendingNonBiometricLogoutIfNeeded()

        registerActivityLifecycleCallbacks(
            object : ActivityLifecycleCallbacks {
                override fun onActivityCreated(
                    activity: Activity,
                    savedInstanceState: Bundle?,
                ) = Unit

                override fun onActivityStarted(activity: Activity) {
                    startedActivities++
                    TokenStore.clearPendingNonBiometricLogout()
                }

                override fun onActivityResumed(activity: Activity) = Unit

                override fun onActivityPaused(activity: Activity) = Unit

                override fun onActivityStopped(activity: Activity) {
                    startedActivities = (startedActivities - 1).coerceAtLeast(0)
                    // If the process is later killed while backgrounded, consume this marker on next launch.
                    if (startedActivities == 0 && TokenStore.isLoggedIn() && !TokenStore.isBiometricEnabled()) {
                        TokenStore.markPendingNonBiometricLogout()
                    }
                }

                override fun onActivitySaveInstanceState(
                    activity: Activity,
                    outState: Bundle,
                ) = Unit

                override fun onActivityDestroyed(activity: Activity) = Unit
            },
        )
    }
}
