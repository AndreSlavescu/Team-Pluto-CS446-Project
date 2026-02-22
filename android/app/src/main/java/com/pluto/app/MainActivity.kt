package com.pluto.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import com.pluto.app.ui.navigation.PlutoNavGraph
import com.pluto.app.ui.theme.PlutoTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()

        val initialOpenAppId = intent.getStringExtra(EXTRA_OPEN_APP_ID)
        val forceOpenApps = intent.getBooleanExtra(EXTRA_OPEN_APPS, false)

        setContent {
            PlutoTheme {
                PlutoNavGraph(
                    initialOpenAppId = initialOpenAppId,
                    forceOpenApps = forceOpenApps,
                )
            }
        }
    }

    companion object {
        const val EXTRA_OPEN_APP_ID = "extra_open_app_id"
        const val EXTRA_OPEN_APPS = "extra_open_apps"
    }
}
