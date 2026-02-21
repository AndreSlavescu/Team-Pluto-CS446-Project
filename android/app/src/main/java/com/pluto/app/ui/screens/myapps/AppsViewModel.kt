package com.pluto.app.ui.screens.myapps

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.pluto.app.data.model.CreateJobResponse
import com.pluto.app.data.repository.AppRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class AppsViewModel : ViewModel() {

    private val repository = AppRepository()

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
                val result = repository.createJob(currentPrompt)
                _jobResult.value = result
                //_jobResult.value = CreateJobResponse("","","DONE","")
            } catch (e: Exception) {
                _error.value = e.message ?: "Failed to create generation job"
            } finally {
                _isLoading.value = false
            }
        }
    }

    fun resetResult() {
        _jobResult.value = null
    }
}
