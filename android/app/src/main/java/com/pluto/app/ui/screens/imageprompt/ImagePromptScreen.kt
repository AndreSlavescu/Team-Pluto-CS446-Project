package com.pluto.app.ui.screens.imageprompt

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.net.Uri
import androidx.compose.ui.platform.LocalContext
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkVertically
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.animation.core.tween
import androidx.core.content.ContextCompat
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.ime
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.AddAPhoto
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Home
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.IconButtonDefaults
import androidx.compose.material3.ListItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.core.content.FileProvider
import coil.compose.AsyncImage
import com.pluto.app.R
import java.io.File


@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ImagePromptScreen(
    onJobCreated: (jobId: String, appId: String) -> Unit,
    onOpenApps: () -> Unit,
    onBack: (() -> Unit),
    viewModel: ImagePromptViewModel = viewModel(),
) {
    val prompt by viewModel.prompt.collectAsState()
    val selectedImages by viewModel.selectedImages.collectAsState()
    val isLoading by viewModel.isLoading.collectAsState()
    val error by viewModel.error.collectAsState()
    val jobResult by viewModel.jobResult.collectAsState()
    val isEditMode = viewModel.isEditMode
    val editAppName = viewModel.editAppName

    val scrollState = rememberScrollState()
    val context = LocalContext.current
    val cameraImageUri = remember { mutableStateOf<Uri?>(null) }
    val showImageSourceSheet = remember { mutableStateOf(false) }
    val imageSourceSheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    val density = LocalDensity.current
    val isKeyboardOpen = WindowInsets.ime.getBottom(density) > 0
    val topSpacing by animateDpAsState(
        targetValue = if (isKeyboardOpen) 12.dp else 24.dp,
        animationSpec = tween(durationMillis = 180),
        label = "imagePromptTopSpacing",
    )
    val logoBottomSpacing by animateDpAsState(
        targetValue = if (isKeyboardOpen) 8.dp else 32.dp,
        animationSpec = tween(durationMillis = 180),
        label = "imagePromptLogoBottomSpacing",
    )

    val launcher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.PickMultipleVisualMedia(3)
    ) { uris ->
        viewModel.addImages(uris)
    }

    val cameraLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.TakePicture()
    ) { success ->
        if (success) {
            cameraImageUri.value?.let { uri -> viewModel.addImages(listOf(uri)) }
        } else {
            cameraImageUri.value?.let { uri ->
                try { context.contentResolver.delete(uri, null, null) } catch (_: Exception) {}
            }
            cameraImageUri.value = null
        }
    }

    val cameraPermissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        if (granted) {
            val uri = createTempImageUri(context)
            if (uri != null) {
                cameraImageUri.value = uri
                cameraLauncher.launch(uri)
            }
        }
    }

    LaunchedEffect(jobResult) {
        jobResult?.let { result ->
            onJobCreated(result.jobId, result.appId)
            viewModel.resetJobResult()
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        if (isEditMode) {
                            editAppName?.let { "Editing $it" } ?: "Edit App"
                        } else {
                            "Pluto"
                        },
                        style = MaterialTheme.typography.headlineMedium,
                        color = MaterialTheme.colorScheme.primary,
                    )
                },
                navigationIcon = {
                    if (isEditMode) {
                        IconButton(onClick = onBack) {
                            Icon(
                                imageVector = Icons.AutoMirrored.Filled.ArrowBack,
                                contentDescription = "Back",
                            )
                        }
                    }
                },
                actions = {
                    IconButton(
                        onClick = onOpenApps,
                        colors = IconButtonDefaults.iconButtonColors(
                            containerColor = MaterialTheme.colorScheme.surfaceVariant,
                            contentColor = MaterialTheme.colorScheme.onSurfaceVariant,
                        ),
                    ) {
                        Icon(
                            imageVector = Icons.Default.Home,
                            contentDescription = "Apps",
                        )
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.background,
                ),
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 24.dp)
                .verticalScroll(scrollState)
                .imePadding()
                .navigationBarsPadding(),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Spacer(modifier = Modifier.height(topSpacing))

            if (!isEditMode) {
                AnimatedVisibility(
                    visible = !isKeyboardOpen,
                    enter = fadeIn(animationSpec = tween(220)) + expandVertically(),
                    exit = fadeOut(animationSpec = tween(160)) + shrinkVertically(),
                ) {
                    // Logo fades/collapses when the IME is shown.
                    Image(
                        painter = painterResource(id = R.drawable.pluto),
                        contentDescription = "Pluto Logo",
                        modifier = Modifier
                            .size(120.dp)
                            .clip(CircleShape)
                    )
                }
                Spacer(modifier = Modifier.height(logoBottomSpacing))
            }

            Text(
                text = if (isEditMode) "Describe your changes" else "Describe your app",
                style = MaterialTheme.typography.headlineLarge,
                color = MaterialTheme.colorScheme.onBackground,
            )

            Spacer(modifier = Modifier.height(8.dp))

            Text(
                text = if (isEditMode) "What would you like to change?" else "What do you want to build?",
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center,
            )

            Spacer(modifier = Modifier.height(32.dp))

            OutlinedTextField(
                value = prompt,
                onValueChange = viewModel::updateImagePrompt,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(140.dp),
                placeholder = {
                    Text(
                        if (isEditMode) {
                            "Add reminders for each todo..."
                        } else {
                            "A todo app with categories and due dates..."
                        }
                    )
                },
                shape = RoundedCornerShape(16.dp),
                enabled = !isLoading,
                isError = error == ImagePromptViewModel.DESCRIPTION_REQUIRED_ERROR,
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = MaterialTheme.colorScheme.primary,
                    unfocusedBorderColor = MaterialTheme.colorScheme.surfaceVariant
                )
            )
            Spacer(modifier = Modifier.height(24.dp))

            val firstRightPreview = selectedImages.getOrNull(0)
            val secondRightPreview = selectedImages.getOrNull(1)
            val leftSlotImageWhenFull = selectedImages.getOrNull(2)

            // Image Selection Row
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                if (leftSlotImageWhenFull != null) {
                    SelectedImageItem(
                        uri = leftSlotImageWhenFull,
                        onRemove = { viewModel.removeImage(leftSlotImageWhenFull) },
                        modifier = Modifier
                            .weight(1f)
                            .height(100.dp)
                    )
                } else {
                    AddImageButton(
                        onClick = {
                            showImageSourceSheet.value = true
                        }, modifier = Modifier
                            .weight(1f)
                            .height(100.dp)
                    )
                }

                if (firstRightPreview != null) {
                    SelectedImageItem(
                        uri = firstRightPreview,
                        onRemove = { viewModel.removeImage(firstRightPreview) },
                        modifier = Modifier
                            .weight(1f)
                            .height(100.dp)
                    )
                } else {
                    EmptyImagePreview(
                        modifier = Modifier
                            .weight(1f)
                            .height(100.dp)
                    )
                }

                if (secondRightPreview != null) {
                    SelectedImageItem(
                        uri = secondRightPreview,
                        onRemove = { viewModel.removeImage(secondRightPreview) },
                        modifier = Modifier
                            .weight(1f)
                            .height(100.dp)
                    )
                } else {
                    EmptyImagePreview(
                        modifier = Modifier
                            .weight(1f)
                            .height(100.dp)
                    )
                }
            }

            Spacer(modifier = Modifier.height(24.dp))

            Button(
                onClick = viewModel::submitImagePrompt,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(56.dp),
                enabled = !isLoading,
                shape = RoundedCornerShape(16.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = MaterialTheme.colorScheme.primary,
                ),
            ) {
                if (isLoading) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(24.dp),
                        color = MaterialTheme.colorScheme.onPrimary,
                        strokeWidth = 2.dp,
                    )
                } else {
                    Text(
                        text = if (isEditMode) "Apply Changes" else "Generate App",
                        style = MaterialTheme.typography.titleMedium,
                        color = MaterialTheme.colorScheme.onPrimary,
                    )
                }
            }

            error?.let { errorMsg ->
                Spacer(modifier = Modifier.height(8.dp))
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(12.dp),
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.errorContainer,
                    ),
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text(
                            text = "An error occurred",
                            style = MaterialTheme.typography.titleMedium,
                            color = MaterialTheme.colorScheme.onErrorContainer,
                        )
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            text = errorMsg,
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onErrorContainer,
                        )
                    }
                }
                Spacer(modifier = Modifier.height(8.dp))
            }

            // Extra spacer to allow scrolling past the button when keyboard is up
            Spacer(modifier = Modifier.height(32.dp))
        }

        if (showImageSourceSheet.value) {
            ModalBottomSheet(
                onDismissRequest = { showImageSourceSheet.value = false },
                sheetState = imageSourceSheetState,
            ) {
                Text(
                    text = "Add image",
                    style = MaterialTheme.typography.titleLarge,
                    modifier = Modifier.padding(horizontal = 24.dp, vertical = 8.dp)
                )

                ListItem(
                    headlineContent = { Text("Choose from gallery") },
                    leadingContent = {
                        Icon(
                            imageVector = Icons.Default.AddAPhoto,
                            contentDescription = null,
                        )
                    },
                    modifier = Modifier.clickable {
                        showImageSourceSheet.value = false
                        launcher.launch(
                            PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)
                        )
                    }
                )

                ListItem(
                    headlineContent = { Text("Take photo") },
                    leadingContent = {
                        Icon(
                            imageVector = Icons.Default.CameraAlt,
                            contentDescription = null,
                        )
                    },
                    modifier = Modifier.clickable {
                        showImageSourceSheet.value = false
                        val hasCameraPermission =
                            ContextCompat.checkSelfPermission(
                                context,
                                Manifest.permission.CAMERA
                            ) == PackageManager.PERMISSION_GRANTED

                        if (hasCameraPermission) {
                            val uri = createTempImageUri(context)
                            if (uri != null) {
                                cameraImageUri.value = uri
                                cameraLauncher.launch(uri)
                            }
                        } else {
                            cameraPermissionLauncher.launch(Manifest.permission.CAMERA)
                        }
                    }
                )

                Spacer(modifier = Modifier.height(16.dp))
            }
        }
    }
}

@Composable
fun SelectedImageItem(
    uri: Uri, onRemove: () -> Unit, modifier: Modifier = Modifier
) {
    Box(
        modifier = modifier
            .clip(RoundedCornerShape(12.dp))
            .background(MaterialTheme.colorScheme.surfaceVariant)
    ) {
        AsyncImage(
            model = uri,
            contentDescription = null,
            modifier = Modifier.fillMaxSize(),
            contentScale = ContentScale.Crop
        )

        Box(
            modifier = Modifier
                .align(Alignment.TopEnd)
                .padding(4.dp)
                .size(24.dp)
                .background(MaterialTheme.colorScheme.error, CircleShape)
                .clickable { onRemove() },
            contentAlignment = Alignment.Center
        ) {
            Icon(
                imageVector = Icons.Default.Close,
                contentDescription = "Remove",
                tint = MaterialTheme.colorScheme.onError,
                modifier = Modifier.size(16.dp)
            )
        }
    }
}

@Composable
fun EmptyImagePreview(modifier: Modifier = Modifier) {
    Box(
        modifier = modifier
            .clip(RoundedCornerShape(12.dp))
            .background(MaterialTheme.colorScheme.surfaceVariant)
    )
}

@Composable
fun AddImageButton(
    onClick: () -> Unit, modifier: Modifier = Modifier
) {
    Box(
        modifier = modifier
            .clip(RoundedCornerShape(12.dp))
            .background(MaterialTheme.colorScheme.surfaceVariant)
            .clickable { onClick() },
        contentAlignment = Alignment.Center
    ) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Icon(
                imageVector = Icons.Default.AddAPhoto,
                contentDescription = "Add photo to prompt.",
                modifier = Modifier.size(32.dp),
                tint = MaterialTheme.colorScheme.primary
            )
        }
    }
}

private fun createTempImageUri(context: Context): Uri? {
    return try {
        val cameraDir = File(context.cacheDir, "camera_images").apply { mkdirs() }
        val file = File.createTempFile("camera_", ".jpg", cameraDir)
        FileProvider.getUriForFile(context, "${context.packageName}.provider", file)
    } catch (e: Exception) {
        null
    }
}
