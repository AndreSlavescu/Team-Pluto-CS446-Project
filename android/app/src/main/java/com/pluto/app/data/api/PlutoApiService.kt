package com.pluto.app.data.api

import com.pluto.app.data.model.AppVersionResponse
import com.pluto.app.data.model.AppVersionsResponse
import com.pluto.app.data.model.CreateJobRequest
import com.pluto.app.data.model.CreateJobResponse
import com.pluto.app.data.model.JobStatusResponse
import com.pluto.app.data.model.LoginRequest
import com.pluto.app.data.model.DiscoverAppsResponse
import com.pluto.app.data.model.MyAppsResponse
import com.pluto.app.data.model.PublishResponse
import com.pluto.app.data.model.RefreshRequest
import com.pluto.app.data.model.RegisterRequest
import com.pluto.app.data.model.TokenResponse
import com.pluto.app.data.model.UploadResponse
import com.pluto.app.data.model.UserResponse
import okhttp3.MultipartBody
import okhttp3.ResponseBody
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.Multipart
import retrofit2.http.POST
import retrofit2.http.Part
import retrofit2.http.Path
import retrofit2.http.Query
import retrofit2.http.Streaming

interface PlutoApiService {
    @POST("v1/auth/register")
    suspend fun register(
        @Body request: RegisterRequest,
    ): TokenResponse

    @POST("v1/auth/login")
    suspend fun login(
        @Body request: LoginRequest,
    ): TokenResponse

    @POST("v1/auth/refresh")
    suspend fun refreshToken(
        @Body request: RefreshRequest,
    ): TokenResponse

    @POST("v1/auth/logout")
    suspend fun logout(
        @Body request: RefreshRequest,
    )

    @GET("v1/auth/me")
    suspend fun getMe(): UserResponse

    @DELETE("v1/auth/account")
    suspend fun deleteAccount()

    @GET("v1/my-apps")
    suspend fun getMyApps(): MyAppsResponse

    @GET("v1/discover")
    suspend fun discoverApps(): DiscoverAppsResponse

    @POST("v1/apps/{appId}/publish")
    suspend fun publishApp(
        @Path("appId") appId: String,
    ): PublishResponse

    @POST("v1/apps/{appId}/unpublish")
    suspend fun unpublishApp(
        @Path("appId") appId: String,
    ): PublishResponse

    @POST("v1/generation-jobs")
    suspend fun createGenerationJob(
        @Body request: CreateJobRequest,
    ): CreateJobResponse

    @GET("v1/generation-jobs/{jobId}")
    suspend fun getGenerationJob(
        @Path("jobId") jobId: String,
    ): JobStatusResponse

    @GET("v1/apps/{appId}/versions/latest")
    suspend fun getLatestVersion(
        @Path("appId") appId: String,
    ): AppVersionResponse

    @GET("v1/apps/{appId}/versions")
    suspend fun getVersions(
        @Path("appId") appId: String,
        @Query("limit") limit: Int = 50,
    ): AppVersionsResponse

    @Streaming
    @GET("v1/artifacts/{artifactId}/download")
    suspend fun downloadArtifact(
        @Path("artifactId") artifactId: String,
    ): ResponseBody

    @Multipart
    @POST("v1/uploads")
    suspend fun uploadFile(
        @Part file: MultipartBody.Part,
    ): UploadResponse

    @POST("v1/analyze-images")
    suspend fun analyzeImages(
        @Body request: AnalyzeImagesRequest,
    ): AnalyzeImagesResponse
}

data class AnalyzeImagesRequest(
    val imageIds: List<String>,
    val userPrompt: String,
)

data class AnalyzeImagesResponse(
    val analysis: String,
)
