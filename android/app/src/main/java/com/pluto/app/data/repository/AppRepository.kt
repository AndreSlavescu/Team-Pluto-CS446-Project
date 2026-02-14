package com.pluto.app.data.repository

import com.pluto.app.data.api.ApiClient
import com.pluto.app.data.api.PlutoApiService
import com.pluto.app.data.model.AppVersionResponse
import com.pluto.app.data.model.CreateJobRequest
import com.pluto.app.data.model.CreateJobResponse
import com.pluto.app.data.model.JobStatusResponse
import okhttp3.ResponseBody

class AppRepository(
    private val api: PlutoApiService = ApiClient.service
) {

    suspend fun createJob(
        prompt: String,
        imageIds: List<String> = emptyList()
    ): CreateJobResponse {
        val request = CreateJobRequest(
            prompt = prompt,
            inputImages = imageIds
        )
        return api.createGenerationJob(request)
    }

    suspend fun getJobStatus(jobId: String): JobStatusResponse {
        return api.getGenerationJob(jobId)
    }

    suspend fun getLatestVersion(appId: String): AppVersionResponse {
        return api.getLatestVersion(appId)
    }

    suspend fun downloadArtifact(artifactId: String): ResponseBody {
        return api.downloadArtifact(artifactId)
    }
}
