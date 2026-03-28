package com.pluto.app.ui.screens.versionhistory

import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.pluto.app.data.model.AppVersionResponse
import com.pluto.app.data.repository.AppRepository
import com.pluto.app.data.repository.AppRepository.Companion.extractErrorMessage
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class VersionHistoryViewModel(savedStateHandle: SavedStateHandle) : ViewModel() {
    private val repository = AppRepository()
    val appId: String = savedStateHandle["appId"] ?: ""

    private val _versions = MutableStateFlow<List<AppVersionResponse>>(emptyList())
    val versions: StateFlow<List<AppVersionResponse>> = _versions.asStateFlow()

    private val _isLoading = MutableStateFlow(true)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()

    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error.asStateFlow()

    private val _appName = MutableStateFlow("Version History")
    val appName: StateFlow<String> = _appName.asStateFlow()

    fun loadVersions() {
        viewModelScope.launch {
            try {
                _isLoading.value = true
                _error.value = null
                val response = repository.getVersions(appId)
                // Reverse so newest is first
                _versions.value = response.versions.reversed()
                if (response.versions.isNotEmpty()) {
                    _appName.value = response.versions.last().manifest.displayName
                }
            } catch (e: Exception) {
                _error.value = extractErrorMessage(e)
            } finally {
                _isLoading.value = false
            }
        }
    }

    fun retry() {
        loadVersions()
    }
}
