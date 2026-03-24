package com.pluto.app.ui.screens.generation

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.viewModelScope
import com.pluto.app.data.model.JobStatusResponse
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class GenerationViewModel(
    application: Application,
    savedStateHandle: SavedStateHandle
) : AndroidViewModel(application) {
    private val manager = GenerationManager.getInstance(application)

    val jobId: String = savedStateHandle["jobId"] ?: ""
    val appId: String = savedStateHandle["appId"] ?: ""

    private val _status = MutableStateFlow<JobStatusResponse?>(null)
    val status: StateFlow<JobStatusResponse?> = _status.asStateFlow()

    private val _isComplete = MutableStateFlow(false)
    val isComplete: StateFlow<Boolean> = _isComplete.asStateFlow()

    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error.asStateFlow()

    init {
        startMonitoring()
    }

    private fun startMonitoring() {
        manager.startMonitoring(jobId, appId)
        viewModelScope.launch {
            manager.getStatus(jobId).collect { managerStatus ->
                when (managerStatus) {
                    is GenerationStatus.Loading -> {
                        _status.value = managerStatus.status
                    }
                    is GenerationStatus.Success -> {
                        _isComplete.value = true
                    }
                    is GenerationStatus.Error -> {
                        _error.value = managerStatus.message
                    }
                    else -> {}
                }
            }
        }
    }

    fun retry() {
        _error.value = null
        _isComplete.value = false
        startMonitoring()
    }
}
