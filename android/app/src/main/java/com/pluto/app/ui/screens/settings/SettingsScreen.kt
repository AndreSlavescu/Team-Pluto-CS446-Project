package com.pluto.app.ui.screens.settings

import android.content.Context
import androidx.biometric.BiometricManager
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
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.pluto.app.BuildConfig
import com.pluto.app.data.auth.AuthRepository
import com.pluto.app.data.auth.TokenStore
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    onBack: () -> Unit,
    onLoggedOut: () -> Unit = {},
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val authRepo = remember { AuthRepository() }
    val email = TokenStore.getEmail() ?: "Unknown"
    val canUseBiometrics = remember(context) { isBiometricAvailable(context) }
    var biometricEnabled by remember { mutableStateOf(TokenStore.isBiometricEnabled() && canUseBiometrics) }
    var showDeleteDialog by remember { mutableStateOf(false) }

    if (showDeleteDialog) {
        AlertDialog(
            onDismissRequest = { showDeleteDialog = false },
            title = { Text("Delete Account") },
            text = {
                Text(
                    "This will permanently delete your account and all associated data. This cannot be undone.",
                )
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        showDeleteDialog = false
                        scope.launch {
                            try {
                                authRepo.deleteAccount()
                            } catch (_: Exception) {
                                TokenStore.clearTokens()
                            }
                            onLoggedOut()
                        }
                    },
                ) {
                    Text("Delete", color = MaterialTheme.colorScheme.error)
                }
            },
            dismissButton = {
                TextButton(onClick = { showDeleteDialog = false }) {
                    Text("Cancel")
                }
            },
        )
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        "Settings",
                        style = MaterialTheme.typography.headlineMedium,
                        color = MaterialTheme.colorScheme.primary,
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

            SectionCard("Account") {
                Text(
                    text = email,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurface,
                )
                Spacer(modifier = Modifier.height(12.dp))
                OutlinedButton(
                    onClick = {
                        scope.launch {
                            try {
                                authRepo.logout()
                            } catch (_: Exception) {
                                // Ensure local auth + biometric state is wiped on sign out.
                                TokenStore.clearTokens()
                            }
                            biometricEnabled = false
                            onLoggedOut()
                        }
                    },
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(12.dp),
                ) {
                    Text("Sign Out")
                }
                Spacer(modifier = Modifier.height(8.dp))
                Button(
                    onClick = { showDeleteDialog = true },
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(12.dp),
                    colors =
                        ButtonDefaults.buttonColors(
                            containerColor = MaterialTheme.colorScheme.errorContainer,
                            contentColor = MaterialTheme.colorScheme.error,
                        ),
                ) {
                    Text("Delete Account")
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            SectionCard("Security") {
                Text(
                    text = if (canUseBiometrics) {
                        "Use your device biometrics to unlock your session."
                    } else {
                        "Biometric authentication is not available on this device."
                    },
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurface,
                )
                Spacer(modifier = Modifier.height(12.dp))
                FilterChip(
                    selected = biometricEnabled,
                    onClick = {
                        if (!canUseBiometrics) return@FilterChip
                        biometricEnabled = !biometricEnabled
                        TokenStore.setBiometricEnabled(biometricEnabled)
                    },
                    enabled = canUseBiometrics,
                    label = { Text("Enable biometric login") },
                    colors =
                        FilterChipDefaults.filterChipColors(
                            selectedContainerColor = MaterialTheme.colorScheme.primaryContainer,
                            selectedLabelColor = MaterialTheme.colorScheme.onPrimaryContainer,
                        ),
                )
            }

            Spacer(modifier = Modifier.height(16.dp))

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
    When you create an account, we collect your email address and a securely hashed version of your password. We do not collect your name, location, or other personal information.

    When you use the App, the following data is sent to our server solely to generate your requested app:
    - The text prompt you enter describing the app you want to build
    - Any images you optionally upload as reference

    This data is processed by our server using a third-party AI service (OpenAI) to generate the app output. Your prompts and uploaded images may be retained on our server for a limited period to support generation and debugging.

    Account Deletion
    You can delete your account at any time from within the App. When you delete your account, your email, password hash, and authentication tokens are permanently removed from our servers.

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

private fun isBiometricAvailable(context: Context): Boolean {
    val biometricManager = BiometricManager.from(context)
    return biometricManager.canAuthenticate(BiometricManager.Authenticators.BIOMETRIC_STRONG) ==
        BiometricManager.BIOMETRIC_SUCCESS
}

