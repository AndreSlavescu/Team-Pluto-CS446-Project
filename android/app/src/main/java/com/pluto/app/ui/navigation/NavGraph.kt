package com.pluto.app.ui.navigation

import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.pluto.app.ui.screens.generation.GenerationScreen
import com.pluto.app.ui.screens.myapps.AppsScreen
import com.pluto.app.ui.screens.myapps.AppsViewModel
import com.pluto.app.ui.screens.preview.PreviewScreen
import com.pluto.app.ui.screens.prompt.PromptScreen
import org.json.JSONArray
import java.io.File

@Composable
fun PlutoNavGraph(
    initialOpenAppId: String? = null,
    forceOpenApps: Boolean = false,
) {
    val navController = rememberNavController()
    val context = LocalContext.current
    val appsViewModel: AppsViewModel = viewModel()
    val startDestination = if (forceOpenApps || hasExistingApps(context)) "apps" else "prompt"
    var hasHandledInitialAppOpen by remember { mutableStateOf(false) }

    LaunchedEffect(initialOpenAppId, hasHandledInitialAppOpen) {
        if (!hasHandledInitialAppOpen && !initialOpenAppId.isNullOrBlank()) {
            hasHandledInitialAppOpen = true
            navController.navigate("preview/$initialOpenAppId")
        }
    }

    NavHost(
        navController = navController,
        startDestination = startDestination,
    ) {
        composable("prompt") {
            PromptScreen(
                onJobCreated = { jobId, appId ->
                    navController.navigate("generation/$jobId/$appId")
                },
                onOpenApps = {
                    navController.navigate("apps")
                },
            )
        }

        composable(
            route = "generation/{jobId}/{appId}",
            arguments =
                listOf(
                    navArgument("jobId") { type = NavType.StringType },
                    navArgument("appId") { type = NavType.StringType },
                ),
        ) {
            GenerationScreen(
                onComplete = { appId ->
                    appsViewModel.registerGeneratedApp(appId = appId)
                    navController.navigate("preview/$appId") {
                        popUpTo("prompt") { inclusive = false }
                    }
                },
                onError = {
                    navController.popBackStack(
                        "prompt",
                        inclusive = false,
                    )
                },
            )
        }

        composable(
            route = "preview/{appId}",
            arguments = listOf(navArgument("appId") { type = NavType.StringType }),
        ) {
            PreviewScreen(
                onBack = {
                    val previousRoute = navController.previousBackStackEntry?.destination?.route
                    if (previousRoute == "apps") {
                        navController.popBackStack()
                    } else {
                        navController.popBackStack(
                            "prompt",
                            inclusive = false,
                        )
                    }
                },
                onOpenApps = {
                    navController.navigate("apps")
                },
            )
        }

        composable(route = "apps") {
            AppsScreen(
                onOpenApp = { appId ->
                    navController.navigate("preview/$appId")
                },
                onCreateApps = { navController.navigate("prompt") },
            )
        }
    }
}

private fun hasExistingApps(context: android.content.Context): Boolean {
    val prefs = context.getSharedPreferences("my_apps_store", android.content.Context.MODE_PRIVATE)
    val raw = prefs.getString("saved_apps", null)
    if (!raw.isNullOrBlank()) {
        val hasPersisted =
            runCatching {
                val arr = JSONArray(raw)
                (0 until arr.length()).any { idx ->
                    val item = arr.optJSONObject(idx) ?: return@any false
                    item.optString("localPath").isNotBlank()
                }
            }.getOrDefault(false)
        if (hasPersisted) return true
    }

    val root = File(context.filesDir, "saved_apps")
    return root.exists() && root.listFiles().orEmpty().isNotEmpty()
}
