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
        setContent {
            PlutoTheme {
                PlutoNavGraph()
            }
        }
    }
}
