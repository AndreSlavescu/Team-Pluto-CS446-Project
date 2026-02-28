package com.pluto.app.ui.screens.generation

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.pluto.app.data.model.JobStatusResponse
import com.pluto.app.data.repository.AppRepository
import com.pluto.app.data.repository.AppRepository.Companion.extractErrorMessage
import kotlinx.coroutines.Job
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

    private var pollingJob: Job? = null

    companion object {
        private const val MAX_CONSECUTIVE_ERRORS = 3
    }

    init {
        startPolling()
    }

    fun retry() {
        _error.value = null
        _isComplete.value = false
        startPolling()
    }

    private fun startPolling() {
        pollingJob?.cancel()
        pollingJob = viewModelScope.launch {
            var attempts = 0
            val maxAttempts = 150 // 5 minutes at 2 second intervals
            var consecutiveErrors = 0

            while (attempts < maxAttempts) {
                try {
                    val job = repository.getJobStatus(jobId)
                    _status.value = job
                    consecutiveErrors = 0

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
                    consecutiveErrors++
                    if (consecutiveErrors >= MAX_CONSECUTIVE_ERRORS) {
                        _error.value = extractErrorMessage(e)
                        return@launch
                    }
                }

                attempts++
                delay(2000)
            }

            // Timeout after max attempts
            _error.value = "Generation timed out after 5 minutes"
        }
    }
}
