package com.pluto.app.ui.screens.discovery

import android.text.format.DateUtils
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.pluto.app.data.model.AppSummary
import com.pluto.app.data.repository.AppRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Locale
import java.util.TimeZone

enum class DiscoveryTab { MY_CREATIONS, COMMUNITY }

class DiscoveryViewModel : ViewModel() {
    private val repository = AppRepository()

    private val _selectedTab = MutableStateFlow(DiscoveryTab.MY_CREATIONS)
    val selectedTab: StateFlow<DiscoveryTab> = _selectedTab.asStateFlow()

    private val _myAppsState = MutableStateFlow<TabUiState>(TabUiState.Loading)
    val myAppsState: StateFlow<TabUiState> = _myAppsState.asStateFlow()

    private val _communityState = MutableStateFlow<TabUiState>(TabUiState.Loading)
    val communityState: StateFlow<TabUiState> = _communityState.asStateFlow()

    fun selectTab(tab: DiscoveryTab) {
        _selectedTab.value = tab
        when (tab) {
            DiscoveryTab.MY_CREATIONS -> loadMyApps()
            DiscoveryTab.COMMUNITY -> loadCommunityApps()
        }
    }

    fun loadMyApps() {
        viewModelScope.launch {
            _myAppsState.value = TabUiState.Loading
            runCatching {
                repository.getMyApps()
            }.onSuccess { apps ->
                _myAppsState.value = if (apps.isEmpty()) TabUiState.Empty else TabUiState.Success(apps)
            }.onFailure { e ->
                _myAppsState.value = TabUiState.Error(AppRepository.extractErrorMessage(e))
            }
        }
    }

    fun loadCommunityApps() {
        viewModelScope.launch {
            _communityState.value = TabUiState.Loading
            runCatching {
                repository.discoverApps()
            }.onSuccess { apps ->
                _communityState.value = if (apps.isEmpty()) TabUiState.Empty else TabUiState.Success(apps)
            }.onFailure { e ->
                _communityState.value = TabUiState.Error(AppRepository.extractErrorMessage(e))
            }
        }
    }

    fun togglePublish(app: AppSummary) {
        viewModelScope.launch {
            val wasPublished = app.published
            runCatching {
                if (wasPublished) repository.unpublishApp(app.appId)
                else repository.publishApp(app.appId)
            }.onSuccess { nowPublished ->
                val current = _myAppsState.value
                if (current is TabUiState.Success) {
                    _myAppsState.value = TabUiState.Success(
                        current.apps.map {
                            if (it.appId == app.appId) it.copy(published = nowPublished) else it
                        },
                    )
                }
            }
        }
    }

    fun timeLabel(isoTimestamp: String?): String {
        if (isoTimestamp.isNullOrBlank()) return ""
        return runCatching {
            val sdf = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.US)
            sdf.timeZone = TimeZone.getTimeZone("UTC")
            val cleaned = isoTimestamp.replace("Z", "").substringBefore("+")
            val date = sdf.parse(cleaned) ?: return ""
            DateUtils.getRelativeTimeSpanString(
                date.time,
                System.currentTimeMillis(),
                DateUtils.MINUTE_IN_MILLIS,
            ).toString()
        }.getOrDefault("")
    }
}

sealed interface TabUiState {
    data object Loading : TabUiState
    data object Empty : TabUiState
    data class Success(val apps: List<AppSummary>) : TabUiState
    data class Error(val message: String) : TabUiState
}
