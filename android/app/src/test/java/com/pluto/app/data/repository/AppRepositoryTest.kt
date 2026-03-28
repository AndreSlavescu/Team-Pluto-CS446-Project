package com.pluto.app.data.repository

import com.pluto.app.data.api.PlutoApiService
import com.pluto.app.data.model.AppManifest
import com.pluto.app.data.model.AppVersionResponse
import com.pluto.app.data.model.AppVersionsResponse
import com.pluto.app.data.model.Artifact
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Test
import retrofit2.HttpException
import retrofit2.Response

class AppRepositoryTest {

    private fun makeVersion(versionId: String, displayName: String): AppVersionResponse {
        return AppVersionResponse(
            versionId = versionId,
            jobId = "job_123",
            createdAt = "2025-01-01T00:00:00Z",
            artifacts = listOf(
                Artifact(
                    type = "project_zip",
                    downloadUrl = "/v1/artifacts/art_123/download",
                    expiresAt = null,
                    sha256 = "abc123",
                ),
            ),
            manifest = AppManifest(
                displayName = displayName,
                packageName = "com.test.app",
                features = listOf("feature1"),
                ui = "material",
            ),
        )
    }

    @Test
    fun `getVersions delegates to api service`() = runTest {
        val expectedResponse = AppVersionsResponse(
            appId = "app_123",
            versions = listOf(
                makeVersion("ver_1", "App v1"),
                makeVersion("ver_2", "App v2"),
            ),
        )

        val fakeApi = object : PlutoApiService {
            override suspend fun register(request: com.pluto.app.data.model.RegisterRequest) = throw NotImplementedError()
            override suspend fun login(request: com.pluto.app.data.model.LoginRequest) = throw NotImplementedError()
            override suspend fun refreshToken(request: com.pluto.app.data.model.RefreshRequest) = throw NotImplementedError()
            override suspend fun logout(request: com.pluto.app.data.model.RefreshRequest) = throw NotImplementedError()
            override suspend fun getMe() = throw NotImplementedError()
            override suspend fun deleteAccount() = throw NotImplementedError()
            override suspend fun createGenerationJob(request: com.pluto.app.data.model.CreateJobRequest) = throw NotImplementedError()
            override suspend fun getGenerationJob(jobId: String) = throw NotImplementedError()
            override suspend fun getLatestVersion(appId: String) = throw NotImplementedError()
            override suspend fun downloadArtifact(artifactId: String) = throw NotImplementedError()
            override suspend fun uploadFile(file: okhttp3.MultipartBody.Part) = throw NotImplementedError()
            override suspend fun analyzeImages(request: com.pluto.app.data.api.AnalyzeImagesRequest) = throw NotImplementedError()

            override suspend fun getVersions(appId: String, limit: Int): AppVersionsResponse {
                assertEquals("app_123", appId)
                assertEquals(50, limit)
                return expectedResponse
            }
        }

        val repo = AppRepository(api = fakeApi)
        val result = repo.getVersions("app_123")

        assertEquals("app_123", result.appId)
        assertEquals(2, result.versions.size)
        assertEquals("ver_1", result.versions[0].versionId)
        assertEquals("ver_2", result.versions[1].versionId)
    }

    @Test
    fun `getVersions passes custom limit`() = runTest {
        var capturedLimit = -1
        val fakeApi = object : PlutoApiService {
            override suspend fun register(request: com.pluto.app.data.model.RegisterRequest) = throw NotImplementedError()
            override suspend fun login(request: com.pluto.app.data.model.LoginRequest) = throw NotImplementedError()
            override suspend fun refreshToken(request: com.pluto.app.data.model.RefreshRequest) = throw NotImplementedError()
            override suspend fun logout(request: com.pluto.app.data.model.RefreshRequest) = throw NotImplementedError()
            override suspend fun getMe() = throw NotImplementedError()
            override suspend fun deleteAccount() = throw NotImplementedError()
            override suspend fun createGenerationJob(request: com.pluto.app.data.model.CreateJobRequest) = throw NotImplementedError()
            override suspend fun getGenerationJob(jobId: String) = throw NotImplementedError()
            override suspend fun getLatestVersion(appId: String) = throw NotImplementedError()
            override suspend fun downloadArtifact(artifactId: String) = throw NotImplementedError()
            override suspend fun uploadFile(file: okhttp3.MultipartBody.Part) = throw NotImplementedError()
            override suspend fun analyzeImages(request: com.pluto.app.data.api.AnalyzeImagesRequest) = throw NotImplementedError()

            override suspend fun getVersions(appId: String, limit: Int): AppVersionsResponse {
                capturedLimit = limit
                return AppVersionsResponse(appId = appId, versions = emptyList())
            }
        }

        val repo = AppRepository(api = fakeApi)
        repo.getVersions("app_123", limit = 10)

        assertEquals(10, capturedLimit)
    }

    @Test
    fun `getVersions returns empty list for app with no versions`() = runTest {
        val fakeApi = object : PlutoApiService {
            override suspend fun register(request: com.pluto.app.data.model.RegisterRequest) = throw NotImplementedError()
            override suspend fun login(request: com.pluto.app.data.model.LoginRequest) = throw NotImplementedError()
            override suspend fun refreshToken(request: com.pluto.app.data.model.RefreshRequest) = throw NotImplementedError()
            override suspend fun logout(request: com.pluto.app.data.model.RefreshRequest) = throw NotImplementedError()
            override suspend fun getMe() = throw NotImplementedError()
            override suspend fun deleteAccount() = throw NotImplementedError()
            override suspend fun createGenerationJob(request: com.pluto.app.data.model.CreateJobRequest) = throw NotImplementedError()
            override suspend fun getGenerationJob(jobId: String) = throw NotImplementedError()
            override suspend fun getLatestVersion(appId: String) = throw NotImplementedError()
            override suspend fun downloadArtifact(artifactId: String) = throw NotImplementedError()
            override suspend fun uploadFile(file: okhttp3.MultipartBody.Part) = throw NotImplementedError()
            override suspend fun analyzeImages(request: com.pluto.app.data.api.AnalyzeImagesRequest) = throw NotImplementedError()

            override suspend fun getVersions(appId: String, limit: Int): AppVersionsResponse {
                return AppVersionsResponse(appId = appId, versions = emptyList())
            }
        }

        val repo = AppRepository(api = fakeApi)
        val result = repo.getVersions("app_empty")

        assertEquals("app_empty", result.appId)
        assertEquals(0, result.versions.size)
    }

    @Test
    fun `extractErrorMessage handles HttpException`() {
        val response = Response.error<Any>(500, okhttp3.ResponseBody.create(null, ""))
        val exception = HttpException(response)
        val message = AppRepository.extractErrorMessage(exception)
        assertEquals("Server error. Please try again later.", message)
    }

    @Test
    fun `extractErrorMessage handles unknown exception`() {
        val exception = RuntimeException("Something went wrong")
        val message = AppRepository.extractErrorMessage(exception)
        assertEquals("Something went wrong", message)
    }
}
