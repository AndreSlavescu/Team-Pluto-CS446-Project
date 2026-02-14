package com.pluto.app.ui.screens.preview

import android.content.Context
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.pluto.app.data.repository.AppRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.File
import java.io.FileOutputStream
import java.util.zip.ZipInputStream

class PreviewViewModel(savedStateHandle: SavedStateHandle) : ViewModel() {

    private val repository = AppRepository()

    val appId: String = savedStateHandle["appId"] ?: ""

    private val _previewPath = MutableStateFlow<String?>(null)
    val previewPath: StateFlow<String?> = _previewPath.asStateFlow()

    private val _isLoading = MutableStateFlow(true)
    val isLoading: StateFlow<Boolean> = _isLoading.asStateFlow()

    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error.asStateFlow()

    private val _appName = MutableStateFlow("Preview")
    val appName: StateFlow<String> = _appName.asStateFlow()

    fun loadPreview(context: Context) {
        viewModelScope.launch {
            try {
                _isLoading.value = true

                val version = repository.getLatestVersion(appId)
                _appName.value = version.manifest.displayName

                val artifact = version.artifacts.firstOrNull()
                    ?: throw Exception("No artifacts found")

                val artifactId = extractArtifactId(artifact.downloadUrl)

                val responseBody = repository.downloadArtifact(artifactId)

                val previewDir = File(context.cacheDir, "previews/$appId")
                withContext(Dispatchers.IO) {
                    if (previewDir.exists()) previewDir.deleteRecursively()
                    previewDir.mkdirs()

                    val zipBytes = responseBody.bytes()
                    ZipInputStream(zipBytes.inputStream()).use { zip ->
                        var entry = zip.nextEntry
                        while (entry != null) {
                            if (!entry.isDirectory) {
                                val file = File(previewDir, entry.name)
                                file.parentFile?.mkdirs()
                                FileOutputStream(file).use { out ->
                                    zip.copyTo(out)
                                }
                            }
                            entry = zip.nextEntry
                        }
                    }
                }

                val indexFile = File(previewDir, "index.html")
                if (indexFile.exists()) {
                    _previewPath.value = indexFile.absolutePath
                } else {
                    _error.value = "No index.html found in artifact"
                }

            } catch (e: Exception) {
                _error.value = e.message ?: "Failed to load preview"
            } finally {
                _isLoading.value = false
            }
        }
    }

    private fun extractArtifactId(downloadUrl: String): String {
        val parts = downloadUrl.split("/")
        val idx = parts.indexOf("artifacts")
        return if (idx >= 0 && idx + 1 < parts.size) parts[idx + 1] else ""
    }
}
