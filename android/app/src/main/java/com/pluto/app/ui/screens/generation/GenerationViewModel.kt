package com.pluto.app.ui.screens.generation

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.pluto.app.data.model.JobStatusResponse
import com.pluto.app.data.repository.AppRepository
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class GenerationViewModel(savedStateHandle: SavedStateHandle) : ViewModel() {
    private val repository = AppRepository()

    val jobId: String = savedStateHandle["jobId"] ?: ""
    val appId: String = savedStateHandle["appId"] ?: ""

    private val _status = MutableStateFlow<JobStatusResponse?>(null)
    val status: StateFlow<JobStatusResponse?> = _status.asStateFlow()

    private val _isComplete = MutableStateFlow(false)
    val isComplete: StateFlow<Boolean> = _isComplete.asStateFlow()

    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error.asStateFlow()

    init {;
        startPolling()
    }

    private fun startPolling() {
        viewModelScope.launch {
            var attempts = 0
            val maxAttempts = 150 // 5 minutes at 2 second intervals

            while (attempts < maxAttempts) {
                try {
                    val job = repository.getJobStatus(jobId)
                    _status.value = job

                    when (job.status) {
                        "SUCCEEDED" -> {
                            _isComplete.value = true
                            return@launch
                        }

                        "FAILED", "CANCELLED" -> {
                            _error.value = job.error?.message ?: "Generation failed"
                            return@launch
                        }
                    }
                } catch (e: Exception) {
                    _error.value = e.message ?: "Lost connection to server"
                    return@launch
                }

                attempts++
                delay(2000)
            }

            // Timeout after max attempts
            _error.value = "Generation timed out after 5 minutes"
        }
    }
}
