package com.pluto.app.ui.screens.prompt

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.viewModelScope
import com.pluto.app.data.model.CreateJobResponse
import com.pluto.app.data.repository.AppRepository
import com.pluto.app.data.repository.AppRepository.Companion.extractErrorMessage
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.io.File

class PromptViewModel(
    application: Application,
    savedStateHandle: SavedStateHandle,
) : AndroidViewModel(application) {
    private val repository = AppRepository()

    private val editAppId: String? = savedStateHandle["editAppId"]
    val isEditMode: Boolean = editAppId != null

    private val _prompt = MutableStateFlow("")
    val prompt: StateFlow<String> = _prompt.asStateFlow()

    private val _isLoading = MutableStateFlow(false)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()

    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error.asStateFlow()

    private val _jobResult = MutableStateFlow<CreateJobResponse?>(null)
    val jobResult: StateFlow<CreateJobResponse?> = _jobResult.asStateFlow()

    fun updatePrompt(text: String) {
        _prompt.value = text
    }

    fun submitPrompt() {
        val currentPrompt = _prompt.value.trim()
        if (currentPrompt.isBlank()) return

        viewModelScope.launch {
            _isLoading.value = true
            _error.value = null
            try {
                val result =
                    if (isEditMode) {
                        val htmlFile =
                            File(
                                getApplication<Application>().filesDir,
                                "saved_apps/$editAppId/index.html",
                            )
                        val currentHtml = if (htmlFile.exists()) htmlFile.readText() else ""
                        repository.editJob(editAppId!!, currentPrompt, currentHtml)
                    } else {
                        repository.createJob(currentPrompt)
                    }
                _jobResult.value = result
            } catch (e: Exception) {
                _error.value = extractErrorMessage(e)
            } finally {
                _isLoading.value = false
            }
        }
    }

    fun clearError() {
        _error.value = null
    }

    fun resetResult() {
        _jobResult.value = null
    }
}
