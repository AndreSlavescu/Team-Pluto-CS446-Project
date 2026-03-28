package com.pluto.app.ui.screens.preview

import android.Manifest
import android.content.pm.PackageManager
import android.view.ViewGroup
import android.webkit.PermissionRequest
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Home
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.IconButtonDefaults
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
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.webkit.WebViewAssetLoader
import com.pluto.app.data.auth.TokenStore

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PreviewScreen(
    hideQuickActions: Boolean = false,
    onBack: () -> Unit,
    onOpenApps: () -> Unit,
    onEdit: () -> Unit,
    onVersionHistory: () -> Unit = {},
    viewModel: PreviewViewModel = viewModel(),
) {
    val previewPath by viewModel.previewPath.collectAsState()
    val isLoading by viewModel.isLoading.collectAsState()
    val error by viewModel.error.collectAsState()
    val appName by viewModel.appName.collectAsState()
    val isHistoricalVersion by viewModel.isHistoricalVersion.collectAsState()
    val previewDirName by viewModel.previewDirName.collectAsState()
    val context = LocalContext.current.applicationContext

    // Bridge WebView camera/mic permission requests to Android runtime permissions.
    // Use a plain list ref so the PermissionRequest survives recomposition.
    val pendingRequests = remember { mutableListOf<PermissionRequest>() }
    val mediaPermissionLauncher =
        rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { results ->
            val req = pendingRequests.removeLastOrNull() ?: return@rememberLauncherForActivityResult
            val allGranted = results.values.all { it }
            if (allGranted) {
                req.grant(req.resources)
            } else {
                req.deny()
            }
        }

    LaunchedEffect(Unit) {
        viewModel.loadPreview(context)
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(appName) },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(
                            Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = "Back",
                        )
                    }
                },
                actions = {
                    if (!hideQuickActions) {
                        IconButton(
                            onClick = onVersionHistory,
                            colors =
                                IconButtonDefaults.iconButtonColors(
                                    containerColor = MaterialTheme.colorScheme.surfaceVariant,
                                    contentColor = MaterialTheme.colorScheme.onSurfaceVariant,
                                ),
                        ) {
                            Icon(
                                imageVector = Icons.Default.History,
                                contentDescription = "Version History",
                            )
                        }
                        if (!isHistoricalVersion) {
                            IconButton(
                                onClick = onEdit,
                                colors =
                                    IconButtonDefaults.iconButtonColors(
                                        containerColor = MaterialTheme.colorScheme.surfaceVariant,
                                        contentColor = MaterialTheme.colorScheme.onSurfaceVariant,
                                    ),
                            ) {
                                Icon(
                                    imageVector = Icons.Default.Edit,
                                    contentDescription = "Edit App",
                                )
                            }
                        }
                        IconButton(
                            onClick = onOpenApps,
                            colors =
                                IconButtonDefaults.iconButtonColors(
                                    containerColor = MaterialTheme.colorScheme.surfaceVariant,
                                    contentColor = MaterialTheme.colorScheme.onSurfaceVariant,
                                ),
                        ) {
                            Icon(
                                imageVector = Icons.Default.Home,
                                contentDescription = "My Apps",
                            )
                        }
                    }
                },
                colors =
                    TopAppBarDefaults.topAppBarColors(
                        containerColor = MaterialTheme.colorScheme.background,
                    ),
            )
        },
    ) { padding ->
        Box(
            modifier = Modifier.fillMaxSize().padding(padding).navigationBarsPadding(),
        ) {
            when {
                isLoading -> {
                    CircularProgressIndicator(
                        modifier = Modifier.align(Alignment.Center),
                        color = MaterialTheme.colorScheme.primary,
                    )
                }

                error != null -> {
                    Column(
                        modifier = Modifier.align(Alignment.Center).padding(horizontal = 24.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                    ) {
                        Card(
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(12.dp),
                            colors =
                                CardDefaults.cardColors(
                                    containerColor = MaterialTheme.colorScheme.errorContainer,
                                ),
                        ) {
                            Column(modifier = Modifier.padding(16.dp)) {
                                Text(
                                    text = "Preview Failed",
                                    style = MaterialTheme.typography.titleMedium,
                                    color = MaterialTheme.colorScheme.onErrorContainer,
                                )
                                Spacer(modifier = Modifier.height(4.dp))
                                Text(
                                    text = error ?: "Unknown error",
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = MaterialTheme.colorScheme.onErrorContainer,
                                )
                            }
                        }
                        Spacer(modifier = Modifier.height(16.dp))
                        Button(onClick = { viewModel.retry(context) }) {
                            Text("Retry")
                        }
                        Spacer(modifier = Modifier.height(8.dp))
                        OutlinedButton(onClick = onBack) {
                            Text("Go Back")
                        }
                    }
                }

                previewPath != null -> {
                    val webViewDir = previewDirName
                    AndroidView(
                        factory = { ctx ->
                            WebView(ctx).apply {
                                layoutParams =
                                    ViewGroup.LayoutParams(
                                        ViewGroup.LayoutParams.MATCH_PARENT,
                                        ViewGroup.LayoutParams.MATCH_PARENT,
                                    )

                                // Use WebViewAssetLoader to serve local files from a virtual
                                // HTTPS origin. This allows the generated app's fetch() calls
                                // to reach the backend (file:// blocks cross-origin requests).
                                val assetLoader =
                                    WebViewAssetLoader.Builder()
                                        .setDomain("plutoapp.local")
                                        .addPathHandler(
                                            "/",
                                            WebViewAssetLoader.InternalStoragePathHandler(
                                                ctx,
                                                ctx.filesDir,
                                            ),
                                        )
                                        .build()

                                webViewClient =
                                    object : WebViewClient() {
                                        override fun shouldOverrideUrlLoading(
                                            view: WebView?,
                                            request: WebResourceRequest?,
                                        ): Boolean {
                                            // Keep all navigation inside the WebView
                                            return false
                                        }

                                        override fun shouldInterceptRequest(
                                            view: WebView?,
                                            request: WebResourceRequest?,
                                        ): WebResourceResponse? {
                                            val uri = request?.url ?: return null
                                            val response = assetLoader.shouldInterceptRequest(uri)
                                            // Inject auth token script into the HTML before any
                                            // other JS runs, so AppDB._token is set at parse time.
                                            val authToken = TokenStore.getAccessToken()
                                            if (response != null &&
                                                authToken != null &&
                                                uri.path?.endsWith("index.html") == true
                                            ) {
                                                val html = response.data.bufferedReader().readText()
                                                val injection =
                                                    "<script>localStorage.setItem('pluto_token','$authToken');</script>"
                                                val patched = html.replaceFirst("<head>", "<head>$injection")
                                                return WebResourceResponse(
                                                    "text/html",
                                                    "utf-8",
                                                    patched.byteInputStream(),
                                                )
                                            }
                                            return response
                                        }

                                        override fun onPageFinished(
                                            view: WebView?,
                                            url: String?,
                                        ) {
                                            super.onPageFinished(view, url)
                                            val authToken = TokenStore.getAccessToken()
                                            if (authToken != null) {
                                                view?.evaluateJavascript(
                                                    "if(typeof AppDB!=='undefined')AppDB._token='$authToken';",
                                                    null,
                                                )
                                            }
                                        }
                                    }

                                // Handle camera/media permission requests from generated apps
                                webChromeClient =
                                    object : WebChromeClient() {
                                        override fun onPermissionRequest(request: PermissionRequest?) {
                                            request ?: return
                                            val resources = request.resources
                                            val wantsCamera = resources.contains(PermissionRequest.RESOURCE_VIDEO_CAPTURE)
                                            val wantsMic = resources.contains(PermissionRequest.RESOURCE_AUDIO_CAPTURE)
                                            if (!wantsCamera && !wantsMic) {
                                                request.deny()
                                                return
                                            }
                                            // Map WebView resources to Android permissions
                                            val needed = mutableListOf<String>()
                                            if (wantsCamera) needed.add(Manifest.permission.CAMERA)
                                            if (wantsMic) needed.add(Manifest.permission.RECORD_AUDIO)
                                            // Check if all needed permissions are already granted
                                            val allGranted = needed.all {
                                                ContextCompat.checkSelfPermission(ctx, it) ==
                                                    PackageManager.PERMISSION_GRANTED
                                            }
                                            if (allGranted) {
                                                request.grant(resources)
                                            } else {
                                                pendingRequests.add(request)
                                                mediaPermissionLauncher.launch(needed.toTypedArray())
                                            }
                                        }
                                    }

                                settings.javaScriptEnabled = true
                                settings.domStorageEnabled = true
                                settings.allowFileAccess = true
                                settings.allowFileAccessFromFileURLs = false
                                settings.allowUniversalAccessFromFileURLs = false
                                settings.mediaPlaybackRequiresUserGesture = false

                                // Load via the virtual HTTPS origin.
                                // Token is injected by shouldInterceptRequest into
                                // the HTML before any JS parses.
                                val relativePath = "$webViewDir/index.html"
                                loadUrl("https://plutoapp.local/$relativePath")
                            }
                        },
                        modifier = Modifier.fillMaxSize(),
                    )
                }
            }
        }
    }
}
