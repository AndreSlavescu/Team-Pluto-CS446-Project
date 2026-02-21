package com.pluto.app.data.api

import com.pluto.app.data.model.AppManifest
import com.pluto.app.data.model.AppVersionResponse
import com.pluto.app.data.model.Artifact
import com.pluto.app.data.model.CreateJobRequest
import com.pluto.app.data.model.CreateJobResponse
import com.pluto.app.data.model.JobLog
import com.pluto.app.data.model.JobProgress
import com.pluto.app.data.model.JobStatusResponse
import com.pluto.app.data.model.UploadResponse
import kotlinx.coroutines.delay
import okhttp3.MultipartBody
import okhttp3.ResponseBody
import okhttp3.ResponseBody.Companion.toResponseBody
import okhttp3.MediaType.Companion.toMediaType
import java.io.ByteArrayOutputStream
import java.time.Instant
import java.util.concurrent.ConcurrentHashMap
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

class FakePlutoApiService : PlutoApiService {

    private val pollCounts = ConcurrentHashMap<String, Int>()
    private val jobToApp = ConcurrentHashMap<String, String>()
    private val appToName = ConcurrentHashMap<String, String>()

    override suspend fun createGenerationJob(request: CreateJobRequest): CreateJobResponse {
        delay(350)
        val now = Instant.now().toString()
        val jobId = "mock-job-${System.currentTimeMillis()}"
        val appId = "mock-app-${System.nanoTime()}"
        jobToApp[jobId] = appId
        appToName[appId] = request.prompt
            .trim()
            .ifBlank { "Generated App" }
            .split(" ")
            .take(4)
            .joinToString(" ")
            .replaceFirstChar { if (it.isLowerCase()) it.titlecase() else it.toString() }

        return CreateJobResponse(
            jobId = jobId,
            appId = appId,
            status = "QUEUED",
            createdAt = now
        )
    }

    override suspend fun getGenerationJob(jobId: String): JobStatusResponse {
        delay(300)
        val now = Instant.now().toString()
        val appId = jobToApp[jobId] ?: "mock-app-unknown"
        val attempt = pollCounts.merge(jobId, 1) { old, _ -> old + 1 } ?: 1

        return when {
            attempt <= 1 -> JobStatusResponse(
                jobId = jobId,
                appId = appId,
                status = "IN_PROGRESS",
                createdAt = now,
                updatedAt = now,
                progress = JobProgress(stage = "PLAN", percent = 25, message = "Designing UI..."),
                logs = listOf(JobLog(ts = now, level = "INFO", msg = "Created generation plan"))
            )

            attempt == 2 -> JobStatusResponse(
                jobId = jobId,
                appId = appId,
                status = "IN_PROGRESS",
                createdAt = now,
                updatedAt = now,
                progress = JobProgress(stage = "BUILD", percent = 72, message = "Building assets..."),
                logs = listOf(JobLog(ts = now, level = "INFO", msg = "Compiling preview bundle"))
            )

            else -> JobStatusResponse(
                jobId = jobId,
                appId = appId,
                status = "SUCCEEDED",
                createdAt = now,
                updatedAt = now,
                progress = JobProgress(stage = "DONE", percent = 100, message = "Complete"),
                logs = listOf(JobLog(ts = now, level = "INFO", msg = "Generation complete"))
            )
        }
    }

    override suspend fun getLatestVersion(appId: String): AppVersionResponse {
        delay(200)
        val now = Instant.now().toString()
        val displayName = appToName[appId] ?: "Mock Generated App"
        return AppVersionResponse(
            versionId = "mock-version-$appId",
            jobId = "mock-job-for-$appId",
            createdAt = now,
            artifacts = listOf(
                Artifact(
                    type = "web-preview",
                    downloadUrl = "https://mock.local/v1/artifacts/mock-artifact-$appId/download",
                    expiresAt = null,
                    sha256 = "mock-sha"
                )
            ),
            manifest = AppManifest(
                displayName = displayName,
                packageName = "com.pluto.mock.${appId.takeLast(8)}",
                features = listOf("mock", "offline"),
                ui = "compose"
            )
        )
    }

    override suspend fun downloadArtifact(artifactId: String): ResponseBody {
        delay(150)
        val appId = artifactId.removePrefix("mock-artifact-")
        val appName = appToName[appId] ?: "Mock Generated App"
        val bytes = createPreviewZip(appName)
        return bytes.toResponseBody("application/zip".toMediaType())
    }

    override suspend fun uploadFile(file: MultipartBody.Part): UploadResponse {
        return UploadResponse(
            uploadId = "mock-upload-${System.currentTimeMillis()}",
            mimeType = file.body.contentType()?.toString() ?: "application/octet-stream",
            sizeBytes = 0
        )
    }

    private fun createPreviewZip(appName: String): ByteArray {
        val html = """
            <!doctype html>
            <html>
            <head>
                <meta charset=\"utf-8\" />
                <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
                <title>$appName</title>
                <style>
                    body { font-family: sans-serif; margin: 0; background: #0f1115; color: #fff; display: grid; place-items: center; height: 100vh; }
                    .card { background: #1b1f27; border-radius: 16px; padding: 24px; width: min(90vw, 480px); }
                    h1 { margin: 0 0 8px; font-size: 24px; }
                    p { margin: 0; color: #b4bcc8; }
                </style>
            </head>
            <body>
                <div class=\"card\">
                    <h1>$appName</h1>
                    <p>This is a mocked preview artifact (no backend call required).</p>
                </div>
            </body>
            </html>
        """.trimIndent()

        val output = ByteArrayOutputStream()
        ZipOutputStream(output).use { zip ->
            zip.putNextEntry(ZipEntry("index.html"))
            zip.write(html.toByteArray())
            zip.closeEntry()
        }
        return output.toByteArray()
    }
}