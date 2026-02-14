package com.pluto.app.data.api

import com.pluto.app.data.model.AppVersionResponse
import com.pluto.app.data.model.CreateJobRequest
import com.pluto.app.data.model.CreateJobResponse
import com.pluto.app.data.model.JobStatusResponse
import com.pluto.app.data.model.UploadResponse
import okhttp3.MultipartBody
import okhttp3.ResponseBody
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Multipart
import retrofit2.http.POST
import retrofit2.http.Part
import retrofit2.http.Path
import retrofit2.http.Streaming

interface PlutoApiService {

    @POST("v1/generation-jobs")
    suspend fun createGenerationJob(@Body request: CreateJobRequest): CreateJobResponse

    @GET("v1/generation-jobs/{jobId}")
    suspend fun getGenerationJob(@Path("jobId") jobId: String): JobStatusResponse

    @GET("v1/apps/{appId}/versions/latest")
    suspend fun getLatestVersion(@Path("appId") appId: String): AppVersionResponse

    @Streaming
    @GET("v1/artifacts/{artifactId}/download")
    suspend fun downloadArtifact(@Path("artifactId") artifactId: String): ResponseBody

    @Multipart
    @POST("v1/uploads")
    suspend fun uploadFile(@Part file: MultipartBody.Part): UploadResponse
}
