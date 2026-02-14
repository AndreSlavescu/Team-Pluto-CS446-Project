package com.example.plutogen

import androidx.lifecycle.ViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

enum class GenerationStage {
    INPUT,
    LOADING,
    PREVIEW,
}

data class GenerationState(
    val appDescription: String = "Create a simple todo list app with checkboxes, task creation, and a clean minimal UI",
    //val isGenerating: Boolean = false,    // for when API call is implemented
    val stage: GenerationStage = GenerationStage.INPUT,
)

class GenerationViewModel : ViewModel() {
    private val _uiState = MutableStateFlow(GenerationState())
    val uiState: StateFlow<GenerationState> = _uiState.asStateFlow()

    fun onDescriptionChanged(description: String) {
        _uiState.update { currentState ->
            currentState.copy(appDescription = description)
        }
    }

    fun onGenerateApp() {
        _uiState.update { currentState ->
            currentState.copy(stage = GenerationStage.LOADING)
        }
    }

    fun onEdit() {
        _uiState.update { currentState ->
            currentState.copy(stage = GenerationStage.INPUT)
        }
    }

    fun onApps() {
        _uiState.update { currentState ->
            currentState.copy(stage = GenerationStage.INPUT)
        }
    }

    fun onLoadingCompleted() {
        _uiState.update { currentState ->
            currentState.copy(stage = GenerationStage.PREVIEW)
        }
    }
}