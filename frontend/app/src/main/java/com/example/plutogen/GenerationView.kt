package com.example.plutogen

import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.tooling.preview.Preview
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.example.plutogen.ui.theme.PlutogenTheme

// TODO: CAN INJECT COLORS FROM UI.THEME
private val Navy = Color(0xFF081736)
private val LightGray = Color(0xFF7D8697)
private val DisabledGray = Color(0xFFBFC6D1)
private val BackgroundGray = Color(0xFFF3F4F6)
private val HighlightGray = Color(0xFFd9d9d9)
private val DividerGray = Color(0xFFE3E6EC)

@Composable
fun GenerationRoute(viewModel: GenerationViewModel = viewModel()) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    key(uiState.stage) {
        when (uiState.stage) {
            GenerationStage.INPUT -> PromptScreen(
                uiState = uiState,
                onDescriptionChanged = viewModel::onDescriptionChanged,
                onGenerateApp = viewModel::onGenerateApp
            )

            GenerationStage.LOADING -> LoadingScreen(
                uiState = uiState,
                onLoadingCompleted = viewModel::onLoadingCompleted
            )

            GenerationStage.PREVIEW -> PreviewScreen(
                onApps = viewModel::onApps,
                onEdit = viewModel::onEdit
            )
        }
    }
}

@Preview(showBackground = true)
@Composable
private fun PromptPreview() {
    PlutogenTheme {
        PromptScreen(
            uiState = GenerationState(),
            onDescriptionChanged = {},
            onGenerateApp = {}
        )
    }
}

@Preview(showBackground = true)
@Composable
private fun LoadingPreview() {
    PlutogenTheme {
        LoadingScreen(
            //uiState = GenerationState(isGenerating = true)
            uiState = GenerationState(stage = GenerationStage.LOADING),
            onLoadingCompleted = {}
        )
    }
}

@Preview(showBackground = true)
@Composable
private fun GeneratedAppPreview() {
    PlutogenTheme {
        PreviewScreen()
    }
}



