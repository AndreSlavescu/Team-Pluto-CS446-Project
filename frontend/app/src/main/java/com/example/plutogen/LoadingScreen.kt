package com.example.plutogen

import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.example.plutogen.ui.theme.PlutogenTheme
import kotlinx.coroutines.delay

private val Navy = Color(0xFF081736)
private val LightGray = Color(0xFF7D8697)
private val DisabledGray = Color(0xFFBFC6D1)

@Composable
fun LoadingScreen(uiState: GenerationState, onLoadingCompleted: () -> Unit) {
    var activeStepIndex by remember { mutableIntStateOf(0) }

    val infiniteTransition = rememberInfiniteTransition(label = "loading-animations")
    val pulseAnimation = rememberInfiniteTransition(label = "loading-step-pulse")
    val activeStepAlpha by pulseAnimation.animateFloat(
        initialValue = 0.55f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(700),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "active-step-alpha",
    )

    val rotation by infiniteTransition.animateFloat(
        initialValue = 0f,
        targetValue = 360f,
        animationSpec = infiniteRepeatable(
            animation = tween(1000),
            repeatMode = RepeatMode.Restart
        ),
        label = "icon-rotation"
    )

    LaunchedEffect(Unit) {
        val totalSteps = 4
        repeat(totalSteps) { stepIndex ->
            activeStepIndex = stepIndex
            delay(1000)
        }
        onLoadingCompleted()
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = 24.dp, vertical = 48.dp)
    ) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(Color(0xFFF2F4F7), RoundedCornerShape(14.dp))
                .padding(horizontal = 16.dp, vertical = 14.dp)
        ) {
            Column {
                Text(
                    text = "PROMPT",
                    style = MaterialTheme.typography.labelLarge,
                    color = DisabledGray,
                    fontWeight = FontWeight.Bold
                )
                Spacer(modifier = Modifier.height(6.dp))
                Text(
                    text = "\"${uiState.appDescription}\"",
                    style = MaterialTheme.typography.bodyLarge,
                    color = LightGray,
                    fontStyle = FontStyle.Italic
                )
            }
        }

        Spacer(modifier = Modifier.height(32.dp))

        Text(
            text = "Generating your app…",
            style = MaterialTheme.typography.headlineMedium,
            color = Color(0xFF2C3443),
            fontWeight = FontWeight.Bold
        )

        Spacer(modifier = Modifier.height(26.dp))

        val stepLabels = listOf(
            "Interpret prompt",
            "Design UI",
            "Generate code",
            "Validate build",
        )

        stepLabels.forEachIndexed { index, label ->
            val isCompleted = index < activeStepIndex
            val isActive = index == activeStepIndex

            LoadingStep(
                icon = when {
                    isCompleted -> "✓"
                    isActive -> "◔"
                    else -> "○"
                },
                label = label,
                color = when {
                    isCompleted || isActive -> Navy
                    else -> DisabledGray
                },
                fontWeight = if (isActive) FontWeight.Bold else FontWeight.Normal,
                textDecoration = if (isCompleted) TextDecoration.LineThrough else null,
                alpha = if (isActive) activeStepAlpha else 1f,
                rotation = if (isActive) rotation else 0f
            )

            if (index < stepLabels.lastIndex) {
                Spacer(modifier = Modifier.height(18.dp))
            }
        }

        Spacer(modifier = Modifier.weight(1f))
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(Color(0xFFF2F4F7), RoundedCornerShape(14.dp))
                .padding(horizontal = 16.dp, vertical = 14.dp),
            contentAlignment = Alignment.BottomCenter
        ) {
            Column {
                Text(
                    text = "Remaining time: ${(stepLabels.size - activeStepIndex)} seconds",
                    modifier = Modifier.align(Alignment.CenterHorizontally),
                    style = MaterialTheme.typography.bodySmall,
                    color = Navy
                )
            }
        }
    }
}

@Composable
private fun LoadingStep(
    icon: String,
    label: String,
    color: Color,
    fontWeight: FontWeight = FontWeight.Normal,
    textDecoration: TextDecoration? = null,
    alpha: Float = 1f,
    rotation: Float = 0f
) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text(
            text = icon,
            color = color.copy(alpha = alpha),
            style = MaterialTheme.typography.titleMedium,
            modifier = Modifier.size(24.dp).graphicsLayer { rotationZ = rotation }
        )
        Text(
            text = label,
            modifier = Modifier.padding(start = 10.dp),
            style = TextStyle(
                fontSize = MaterialTheme.typography.titleMedium.fontSize,
                lineHeight = MaterialTheme.typography.titleMedium.lineHeight,
                fontWeight = fontWeight,
                textDecoration = textDecoration,
                color = color.copy(alpha = alpha),
            )
        )
    }
}

@Preview(showBackground = true)
@Composable
private fun LoadingPreview() {
    PlutogenTheme {
        LoadingScreen(
            //uiState = GenerationState(isGenerating = true)
            uiState = GenerationState(stage = GenerationStage.LOADING),
            onLoadingCompleted = {}
        )
    }
}

@Preview(showBackground = true)
@Composable
private fun LoadingStepPreview() {
    PlutogenTheme {
        LoadingStep(
            icon = "◔",
            label = "Waiting on rocket boosters",
            color = Navy,
            fontWeight = FontWeight.Normal,
            textDecoration = null,
            alpha = 1f,
            rotation = 0f
        )
    }
}