package com.pluto.app.ui.screens.generation

import android.content.Context
import android.content.Intent
import com.pluto.app.data.model.JobStatusResponse
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.util.concurrent.ConcurrentHashMap

sealed class GenerationStatus {
    object Idle : GenerationStatus()
    data class Loading(val status: JobStatusResponse?) : GenerationStatus()
    data class Success(val appId: String) : GenerationStatus()
    data class Error(val message: String) : GenerationStatus()
}

class GenerationManager private constructor(context: Context) {
    private val appContext = context.applicationContext
    private val _jobs = ConcurrentHashMap<String, MutableStateFlow<GenerationStatus>>()

    fun getStatus(jobId: String): StateFlow<GenerationStatus> {
        return _jobs.getOrPut(jobId) { MutableStateFlow(GenerationStatus.Idle) }.asStateFlow()
    }

    fun startMonitoring(jobId: String, appId: String) {
        val statusFlow = _jobs.getOrPut(jobId) { MutableStateFlow(GenerationStatus.Idle) }
        if (statusFlow.value is GenerationStatus.Loading) return

        // Start the Foreground Service to handle polling in background
        val intent = Intent(appContext, GenerationService::class.java).apply {
            putExtra("jobId", jobId)
            putExtra("appId", appId)
        }
        
        if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
            appContext.startForegroundService(intent)
        } else {
            appContext.startService(intent)
        }
    }

    // Called by the Service to update the UI state
    fun updateStatus(jobId: String, status: GenerationStatus) {
        _jobs.getOrPut(jobId) { MutableStateFlow(GenerationStatus.Idle) }.value = status
    }

    fun registerAppLocally(appId: String) {
        val prefs = appContext.getSharedPreferences("my_apps_store", Context.MODE_PRIVATE)
        val raw = prefs.getString("saved_apps", "[]")
        try {
            val arr = org.json.JSONArray(raw)
            val generatedDir = java.io.File(appContext.filesDir, "saved_apps/$appId")
            
            var exists = false
            for (i in 0 until arr.length()) {
                if (arr.getJSONObject(i).optString("id") == appId) {
                    exists = true
                    break
                }
            }
            
            if (!exists) {
                val newApp = org.json.JSONObject()
                    .put("id", appId)
                    .put("name", "Generated App")
                    .put("localPath", generatedDir.absolutePath)
                    .put("updatedAtMillis", System.currentTimeMillis())
                arr.put(newApp)
                prefs.edit().putString("saved_apps", arr.toString()).apply()
            }
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    companion object {
        @Volatile
        private var INSTANCE: GenerationManager? = null

        fun getInstance(context: Context): GenerationManager {
            return INSTANCE ?: synchronized(this) {
                INSTANCE ?: GenerationManager(context).also { INSTANCE = it }
            }
        }
    }
}
