package com.pluto.app.data.model

data class CreateJobRequest(
    val prompt: String,
    val inputImages: List<String> = emptyList(),
    val baseTemplate: String? = null,
    val constraints: JobConstraints? = null,
    val client: ClientInfo? = null,
)

data class JobConstraints(
    val platform: String? = null,
    val ui: String? = null,
    val offlineFirst: Boolean? = null,
    val maxGenerationSeconds: Int? = null,
)

data class ClientInfo(
    val deviceId: String? = null,
    val appVersion: String? = null,
)

data class CreateJobResponse(
    val jobId: String,
    val appId: String,
    val status: String,
    val createdAt: String,
)

data class JobStatusResponse(
    val jobId: String,
    val appId: String,
    val status: String,
    val createdAt: String,
    val updatedAt: String,
    val progress: JobProgress? = null,
    val logs: List<JobLog> = emptyList(),
    val error: ApiError? = null,
)

data class JobProgress(
    val stage: String,
    val percent: Int,
    val message: String? = null,
)

data class JobLog(
    val ts: String,
    val level: String,
    val msg: String,
)

data class ApiError(
    val code: String,
    val message: String,
    val details: Map<String, Any>? = null,
)

data class AppVersionResponse(
    val versionId: String,
    val jobId: String,
    val createdAt: String,
    val artifacts: List<Artifact>,
    val manifest: AppManifest,
)

data class Artifact(
    val type: String,
    val downloadUrl: String,
    val expiresAt: String? = null,
    val sha256: String,
)

data class AppManifest(
    val displayName: String,
    val packageName: String,
    val features: List<String> = emptyList(),
    val ui: String? = null,
)

data class UploadResponse(
    val uploadId: String,
    val mimeType: String,
    val sizeBytes: Int,
)
