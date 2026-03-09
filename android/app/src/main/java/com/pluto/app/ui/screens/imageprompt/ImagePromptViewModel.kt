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
import java.io.File

class ImagePromptViewModel(
    application: Application,
    savedStateHandle: SavedStateHandle,
) : AndroidViewModel(application) {
    private val repository = AppRepository()

    private val editAppId: String? = savedStateHandle["editAppId"]
    val isEditMode: Boolean = !editAppId.isNullOrBlank()

    private val _imageprompt = MutableStateFlow("")
    val imageprompt: StateFlow<String> = _imageprompt.asStateFlow()

    private val _selectedImages = MutableStateFlow<List<Uri>>(emptyList())
    val selectedImages: StateFlow<List<Uri>> = _selectedImages.asStateFlow()

    private val _isLoading = MutableStateFlow(false)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()

    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error.asStateFlow()

    private val _jobResult = MutableStateFlow<CreateJobResponse?>(null)
    val jobResult: StateFlow<CreateJobResponse?> = _jobResult.asStateFlow()

    fun updateImagePrompt(text: String) {
        _imageprompt.value = text
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
        val currentImagePrompt = _imageprompt.value.trim()
        val images = _selectedImages.value

        viewModelScope.launch {
            _isLoading.value = true
            _error.value = null
            try {
                // Step 1: Upload images and get their IDs from the server
                val imageIds = if (images.isNotEmpty()) {
                    images.map { uri ->
                        repository.uploadImage(getApplication(), uri)
                    }
                } else {
                    emptyList()
                }

                if (currentImagePrompt.isBlank() && imageIds.isEmpty()) {
                    _error.value = "Please provide a description or images."
                    return@launch
                }

                // Step 2: Trigger the actual app generation
                // We send both the text prompt AND the image IDs directly to the creation job.
                // The backend generator is already configured to handle both together.
                val result = if (isEditMode) {
                    val htmlFile = File(getApplication<Application>().filesDir, "saved_apps/$editAppId/index.html")
                    val currentHtml = if (htmlFile.exists()) htmlFile.readText() else ""
                    repository.editJob(editAppId!!, currentImagePrompt, currentHtml, imageIds)
                } else {
                    repository.createJob(currentImagePrompt, imageIds)
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
}
