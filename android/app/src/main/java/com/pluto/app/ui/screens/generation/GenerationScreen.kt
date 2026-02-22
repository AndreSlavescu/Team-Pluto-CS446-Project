package com.pluto.app.ui.screens.generation

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.tooling.preview.PreviewParameter
import androidx.compose.ui.tooling.preview.PreviewParameterProvider
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.pluto.app.data.model.JobProgress
import com.pluto.app.data.model.JobStatusResponse
import kotlinx.coroutines.delay

@Composable
fun GenerationScreen(
    onComplete: (appId: String) -> Unit,
    onError: () -> Unit,
    viewModel: GenerationViewModel = viewModel()
) {
    val status by viewModel.status.collectAsState()
    val isComplete by viewModel.isComplete.collectAsState()
    val error by viewModel.error.collectAsState()

    LaunchedEffect(isComplete) {
        if (isComplete) {
            onComplete(viewModel.appId)
        }
    }

    GenerationScreenContent(
        status = status,
        error = error,
        onBackClick = onError
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun GenerationScreenContent(
    status: JobStatusResponse?,
    error: String?,
    onBackClick: () -> Unit
) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Generating...") },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.background
                )
            )
        }) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 24.dp)
                .navigationBarsPadding(),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Spacer(modifier = Modifier.height(48.dp))

            val progress = status?.progress
            val percent = progress?.percent ?: 0
            val statusLabel = status?.status.orEmpty()
            val isCompleted = statusLabel.equals("COMPLETED", ignoreCase = true) ||
                    statusLabel.equals("SUCCEEDED", ignoreCase = true)
            val progressAnim = remember { Animatable(0f) }
            val currentPercent by rememberUpdatedState(percent)
            val currentIsCompleted by rememberUpdatedState(isCompleted)

            LaunchedEffect(Unit) {
                while (true) {
                    val serverProgress = (currentPercent.coerceIn(0, 100)) / 100f

                    if (currentIsCompleted) {
                        if (progressAnim.value < 1f) {
                            progressAnim.animateTo(
                                targetValue = 1f,
                                animationSpec = tween(
                                    durationMillis = 450,
                                    easing = LinearEasing
                                )
                            )
                        }
                        break
                    }

                    val capBeforeCompletion = 0.99f
                    val floor = maxOf(progressAnim.value, serverProgress).coerceAtMost(capBeforeCompletion)
                    val remaining = capBeforeCompletion - floor
                    val easedStep = (remaining * 0.10f).coerceAtLeast(0.0025f)
                    val target = maxOf(serverProgress, (floor + easedStep).coerceAtMost(capBeforeCompletion))

                    if (target > progressAnim.value) {
                        val deltaPercent = ((target - progressAnim.value) * 100).toInt().coerceAtLeast(1)
                        progressAnim.animateTo(
                            targetValue = target,
                            animationSpec = tween(
                                durationMillis = (deltaPercent * 45).coerceIn(220, 2100),
                                easing = LinearEasing
                            )
                        )
                    }

                    delay(120)
                }
            }

            if (progress == null && error == null) {
                CircularProgressIndicator(
                    modifier = Modifier.size(120.dp),
                    strokeWidth = 8.dp,
                    color = MaterialTheme.colorScheme.primary,
                    trackColor = MaterialTheme.colorScheme.surfaceVariant
                )
            } else {
                CircularProgressIndicator(
                    progress = { progressAnim.value },
                    modifier = Modifier.size(120.dp),
                    strokeWidth = 8.dp,
                    color = MaterialTheme.colorScheme.primary,
                    trackColor = MaterialTheme.colorScheme.surfaceVariant
                )
            }

            Spacer(modifier = Modifier.height(24.dp))

            Text(
                text = "${(progressAnim.value * 100).toInt()}%",
                style = MaterialTheme.typography.headlineLarge,
                color = MaterialTheme.colorScheme.onBackground
            )

            Spacer(modifier = Modifier.height(8.dp))

            Text(
                text = progress?.message ?: status?.status ?: "Starting...",
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )

            error?.let { errorMsg ->
                Spacer(modifier = Modifier.height(24.dp))

                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(12.dp),
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.errorContainer
                    )
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text(
                            text = "Generation Failed",
                            style = MaterialTheme.typography.titleMedium,
                            color = MaterialTheme.colorScheme.onErrorContainer
                        )
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            text = errorMsg,
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onErrorContainer
                        )
                    }
                }

                Spacer(modifier = Modifier.height(16.dp))

                OutlinedButton(onClick = onBackClick) {
                    Text("Go Back")
                }
            }

            val logs = status?.logs ?: emptyList()
            if (logs.isNotEmpty()) {
                Spacer(modifier = Modifier.height(32.dp))

                Text(
                    text = "Logs",
                    style = MaterialTheme.typography.titleMedium,
                    modifier = Modifier.align(Alignment.Start)
                )

                Spacer(modifier = Modifier.height(8.dp))

                LazyColumn(modifier = Modifier.weight(1f)) {
                    items(logs) { log ->
                        Text(
                            text = "${log.level}: ${log.msg}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.padding(vertical = 2.dp)
                        )
                    }
                }
            }
        }
    }
}

class GenerationStateProvider : PreviewParameterProvider<JobStatusResponse?> {
    override val values = sequenceOf(
        null,
        JobStatusResponse(
            jobId = "1",
            appId = "1",
            status = "IN_PROGRESS",
            createdAt = "",
            updatedAt = "",
            progress = JobProgress(stage = "Starting", percent = 20, message = "Initializing...")
        ),
        JobStatusResponse(
            jobId = "1",
            appId = "1",
            status = "IN_PROGRESS",
            createdAt = "",
            updatedAt = "",
            progress = JobProgress(stage = "Building", percent = 65, message = "Compiling assets...")
        )
    )
}

@Preview(showBackground = true)
@Composable
fun GenerationScreenPreview(
    @PreviewParameter(GenerationStateProvider::class) status: JobStatusResponse?
) {
    MaterialTheme {
        GenerationScreenContent(
            status = status,
            error = if (status?.status == "FAILED") "Mock Error" else null,
            onBackClick = {}
        )
    }
}
