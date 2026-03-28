package com.pluto.app.data.repository

import android.content.Context
import android.net.Uri
import com.pluto.app.data.api.AnalyzeImagesRequest
import com.pluto.app.data.api.ApiClient
import com.pluto.app.data.api.PlutoApiService
import com.pluto.app.data.model.AppVersionResponse
import com.pluto.app.data.model.AppVersionsResponse
import com.pluto.app.data.model.CreateJobRequest
import com.pluto.app.data.model.CreateJobResponse
import com.pluto.app.data.model.JobStatusResponse
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.ResponseBody
import org.json.JSONObject
import retrofit2.HttpException
import java.io.File
import java.io.FileOutputStream
import java.net.ConnectException
import java.net.SocketTimeoutException
import java.net.UnknownHostException

class AppRepository(
    private val api: PlutoApiService = ApiClient.service,
) {
    companion object {
        fun extractErrorMessage(e: Throwable): String {
            if (e is HttpException) {
                try {
                    val body = e.response()?.errorBody()?.string()
                    if (body != null) {
                        val json = JSONObject(body)
                        val detail = json.optJSONObject("detail")
                        if (detail != null) {
                            val message = detail.optString("message", "")
                            if (message.isNotBlank()) return message
                        }
                        val detailStr = json.optString("detail", "")
                        if (detailStr.isNotBlank()) return detailStr
                    }
                } catch (_: Exception) { }

                return when (e.code()) {
                    400 -> "Invalid request. Please check your input and try again."
                    404 -> "The requested resource was not found."
                    429 -> "Too many requests. Please wait a moment and try again."
                    in 500..599 -> "Server error. Please try again later."
                    else -> "Request failed (HTTP ${e.code()})."
                }
            }

            return when (e) {
                is UnknownHostException -> "No internet connection. Please check your network."
                is ConnectException -> "Unable to reach the server. Please try again later."
                is SocketTimeoutException -> "Connection timed out. Please try again."
                else -> e.message ?: "An unexpected error occurred."
            }
        }
    }

    suspend fun createJob(
        prompt: String,
        imageIds: List<String> = emptyList(),
    ): CreateJobResponse {
        val request =
            CreateJobRequest(
                prompt = prompt,
                inputImages = imageIds,
            )
        return api.createGenerationJob(request)
    }

    suspend fun editJob(
        appId: String,
        editPrompt: String,
        currentHtml: String,
        imageIds: List<String> = emptyList(),
    ): CreateJobResponse {
        val request =
            CreateJobRequest(
                prompt = editPrompt,
                appId = appId,
                baseTemplate = currentHtml,
                inputImages = imageIds,
            )
        return api.createGenerationJob(request)
    }

    suspend fun getJobStatus(jobId: String): JobStatusResponse {
        return api.getGenerationJob(jobId)
    }

    suspend fun getLatestVersion(appId: String): AppVersionResponse {
        return api.getLatestVersion(appId)
    }

    suspend fun getVersions(appId: String, limit: Int = 50): AppVersionsResponse {
        return api.getVersions(appId, limit)
    }

    suspend fun downloadArtifact(artifactId: String): ResponseBody {
        return api.downloadArtifact(artifactId)
    }

    suspend fun uploadImage(context: Context, uri: Uri): String {
        val file = uriToFile(context, uri)
        val requestFile = file.asRequestBody("image/*".toMediaTypeOrNull())
        val body = MultipartBody.Part.createFormData("file", file.name, requestFile)
        val response = api.uploadFile(body)
        return response.uploadId
    }

    suspend fun analyzeImages(imageIds: List<String>, userPrompt: String): String {
        val response = api.analyzeImages(AnalyzeImagesRequest(imageIds, userPrompt))
        return response.analysis
    }

    private fun uriToFile(context: Context, uri: Uri): File {
        val inputStream = context.contentResolver.openInputStream(uri)
        val tempFile = File(context.cacheDir, "upload_${System.currentTimeMillis()}.jpg")
        val outputStream = FileOutputStream(tempFile)
        inputStream?.use { input ->
            outputStream.use { output ->
                input.copyTo(output)
            }
        }
        return tempFile
    }
}
