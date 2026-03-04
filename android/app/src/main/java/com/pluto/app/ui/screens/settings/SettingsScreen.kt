package com.pluto.app.ui.screens.settings

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.pluto.app.BuildConfig

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(onBack: () -> Unit) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        "About",
                        style = MaterialTheme.typography.headlineSmall,
                        fontWeight = FontWeight.SemiBold,
                    )
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(
                            imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = "Back",
                        )
                    }
                },
                colors =
                    TopAppBarDefaults.topAppBarColors(
                        containerColor = MaterialTheme.colorScheme.background,
                    ),
            )
        },
    ) { padding ->
        Column(
            modifier =
                Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .padding(horizontal = 20.dp)
                    .navigationBarsPadding()
                    .verticalScroll(rememberScrollState()),
        ) {
            Text(
                text = "Pluto",
                style = MaterialTheme.typography.headlineMedium,
                color = MaterialTheme.colorScheme.primary,
                fontWeight = FontWeight.Bold,
            )
            Text(
                text = "Version ${BuildConfig.VERSION_NAME}",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            Spacer(modifier = Modifier.height(24.dp))

            SectionCard("Privacy Policy") {
                Text(
                    text = PRIVACY_POLICY_TEXT,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurface,
                )
            }

            Spacer(modifier = Modifier.height(16.dp))

            SectionCard("Contact") {
                Text(
                    text = "For questions or concerns about this policy, contact us at pluto-cs446@uwaterloo.ca",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurface,
                )
            }

            Spacer(modifier = Modifier.height(32.dp))
        }
    }
}

@Composable
private fun SectionCard(
    title: String,
    content: @Composable () -> Unit,
) {
    Column(
        modifier =
            Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(14.dp))
                .background(MaterialTheme.colorScheme.surface)
                .padding(16.dp),
    ) {
        Text(
            text = title,
            style = MaterialTheme.typography.titleMedium,
            color = MaterialTheme.colorScheme.primary,
            fontWeight = FontWeight.SemiBold,
        )
        Spacer(modifier = Modifier.height(8.dp))
        content()
    }
}

private val PRIVACY_POLICY_TEXT =
    """
    Effective Date: March 2026

    Pluto ("the App") is developed by Team Pluto as a university project at the University of Waterloo.

    Data We Collect
    The App does not require you to create an account. We do not collect personal information such as your name, email address, or location.

    When you use the App, the following data is sent to our server solely to generate your requested app:
    - The text prompt you enter describing the app you want to build
    - Any images you optionally upload as reference

    This data is processed by our server using a third-party AI service (OpenAI) to generate the app output. Your prompts and uploaded images may be retained on our server for a limited period to support generation and debugging. Data is not associated with any user identity.

    Data Stored on Your Device
    Generated apps are saved locally on your device. This data never leaves your device unless you choose to share it.

    Third-Party Services
    We use OpenAI's API to generate app content. Your prompts and uploaded images are sent to OpenAI for processing. OpenAI's use of this data is governed by their own privacy policy.

    Data Sharing
    We do not sell, trade, or share your data with any third parties beyond the AI processing described above.

    Children's Privacy
    The App is not directed at children under 13. We do not knowingly collect data from children.

    Changes to This Policy
    We may update this policy from time to time. Changes will be reflected in the App.

    Contact
    If you have questions about this policy, contact us at pluto-cs446@uwaterloo.ca.
    """.trimIndent()
