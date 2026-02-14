package com.example.plutogen

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import androidx.compose.runtime.Composable
import androidx.compose.ui.tooling.preview.Preview
import com.example.plutogen.ui.theme.PlutogenTheme

class MainActivity : ComponentActivity() {
    private val appCompilerViewModel: GenerationViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        //enableEdgeToEdge()
        setContent {
            PlutogenTheme {
                GenerationRoute(viewModel = appCompilerViewModel)
            }
        }
    }
}

@Preview(showBackground = true)
@Composable
fun AppPreview() {
    PlutogenTheme {
        GenerationRoute()
    }
}