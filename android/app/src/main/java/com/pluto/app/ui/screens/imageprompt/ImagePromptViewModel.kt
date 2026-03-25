package com.pluto.app.ui.screens.imageprompt

import android.app.Application
import android.net.Uri
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.viewModelScope
import com.pluto.app.data.model.CreateJobResponse
import com.pluto.app.data.repository.AppRepository
import com.pluto.app.data.repository.AppRepository.Companion.extractErrorMessage
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import org.json.JSONArray
import java.io.File

class ImagePromptViewModel(
    application: Application,
    savedStateHandle: SavedStateHandle,
) : AndroidViewModel(application) {
    companion object {
        const val DESCRIPTION_REQUIRED_ERROR = "An app description is required."
        const val CHANGES_REQUIRED_ERROR = "A description of changes is required."
        private const val PREFS_NAME = "my_apps_store"
        private const val KEY_SAVED_APPS = "saved_apps"
    }

    private val repository = AppRepository()

    private val editAppId: String? = savedStateHandle["editAppId"]
    val editAppName: String? by lazy { resolveEditAppName(editAppId) }
    val isEditMode: Boolean = !editAppId.isNullOrBlank()

    private val _prompt = MutableStateFlow("")
    val prompt: StateFlow<String> = _prompt.asStateFlow()

    private val _selectedImages = MutableStateFlow<List<Uri>>(emptyList())
    val selectedImages: StateFlow<List<Uri>> = _selectedImages.asStateFlow()

    private val _isLoading = MutableStateFlow(false)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()

    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error.asStateFlow()

    private val _jobResult = MutableStateFlow<CreateJobResponse?>(null)
    val jobResult: StateFlow<CreateJobResponse?> = _jobResult.asStateFlow()

    fun updateImagePrompt(text: String) {
        _error.value = null
        _prompt.value = text
    }

    fun addImages(uris: List<Uri>) {
        _selectedImages.update { current ->
            (current + uris).take(3)
        }
    }

    fun removeImage(uri: Uri) {
        _selectedImages.update { current ->
            current.filterNot { it == uri }
        }
    }

    fun submitImagePrompt() {
        val currentPrompt = _prompt.value.trim()
        val images = _selectedImages.value

        viewModelScope.launch {
            _isLoading.value = true
            _error.value = null
            try {
                if (currentPrompt.isBlank()) {
                    _error.value = if (isEditMode) CHANGES_REQUIRED_ERROR else DESCRIPTION_REQUIRED_ERROR
                    return@launch
                }

                // Step 1: Upload images and get their IDs from the server
                val imageIds = if (images.isNotEmpty()) {
                    images.map { uri ->
                        repository.uploadImage(getApplication(), uri)
                    }
                } else {
                    emptyList()
                }

                // Step 2: Trigger the actual app generation
                val result = if (isEditMode) {
                    val htmlFile = File(getApplication<Application>().filesDir, "saved_apps/$editAppId/index.html")
                    val currentHtml = if (htmlFile.exists()) htmlFile.readText() else ""
                    repository.editJob(editAppId!!, currentPrompt, currentHtml, imageIds)
                } else {
                    repository.createJob(currentPrompt, imageIds)
                }
                _jobResult.value = result
            } catch (e: Exception) {
                _error.value = extractErrorMessage(e)
            } finally {
                _isLoading.value = false
            }
        }
    }

    fun resetJobResult() {
        _jobResult.value = null
    }

    private fun resolveEditAppName(appId: String?): String? {
        if (appId.isNullOrBlank()) return null

        val prefs = getApplication<Application>().getSharedPreferences(PREFS_NAME, 0)
        val raw = prefs.getString(KEY_SAVED_APPS, null) ?: return null

        return runCatching {
            val array = JSONArray(raw)
            for (index in 0 until array.length()) {
                val item = array.optJSONObject(index) ?: continue
                val name = item.optString("name").takeIf { it.isNotBlank() } ?: continue
                val id = item.optString("id")
                val localPath = item.optString("localPath")
                val previewId = File(localPath).let { file ->
                    if (file.isFile) {
                        file.parentFile?.name.orEmpty()
                    } else {
                        file.name.orEmpty()
                    }
                }

                if (id == appId || previewId == appId) {
                    return@runCatching name
                }
            }
            null
        }.getOrNull()
    }
}
