package com.pluto.app.ui.navigation

import androidx.compose.runtime.Composable
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.pluto.app.ui.screens.auth.AuthScreen
import com.pluto.app.ui.screens.imageprompt.ImagePromptScreen
import com.pluto.app.ui.screens.generation.GenerationScreen
import com.pluto.app.ui.screens.myapps.AppsScreen
import com.pluto.app.ui.screens.myapps.AppsViewModel
import com.pluto.app.ui.screens.preview.PreviewScreen
import com.pluto.app.ui.screens.settings.SettingsScreen
import com.pluto.app.data.auth.TokenStore
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

    val postAuthDestination =
        if (forceOpenApps || hasExistingApps(context)) {
            "apps"
        } else {
            "image-prompt"
        }
    val authSuccessDestination =
        if (!initialOpenAppId.isNullOrBlank()) {
            "preview/$initialOpenAppId?fromShortcut=true"
        } else {
            postAuthDestination
        }
    val startDestination = when {
        !initialOpenAppId.isNullOrBlank() && TokenStore.isLoggedIn() && TokenStore.isBiometricEnabled() ->
            "auth"
        !initialOpenAppId.isNullOrBlank() && TokenStore.isLoggedIn() ->
            "preview/$initialOpenAppId?fromShortcut=true"
        TokenStore.isLoggedIn() && !TokenStore.isBiometricEnabled() ->
            postAuthDestination
        else -> "auth"
    }

    NavHost(
        navController = navController,
        startDestination = startDestination,
    ) {
        composable("auth") {
            AuthScreen(
                onAuthSuccess = {
                    navController.navigate(authSuccessDestination) {
                        popUpTo("auth") { inclusive = true }
                    }
                },
            )
        }

        composable(
            route = "image-prompt?editAppId={editAppId}",
            arguments = listOf(
                navArgument("editAppId") {
                    type = NavType.StringType
                    nullable = true
                    defaultValue = null
                }
            )
        ) {
            ImagePromptScreen(
                onJobCreated = { jobId, appId ->
                    navController.navigate("generation/$jobId/$appId")
                },
                onOpenApps = {
                    navController.navigate("apps")
                },
                onBack = {
                    navController.popBackStack()
                }
            )
        }

        // Keep image-prompt without args for compatibility
        composable("image-prompt") {
            navController.navigate("image-prompt?editAppId=") {
                popUpTo("image-prompt") { inclusive = true }
            }
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
                        popUpTo("apps") { inclusive = false }
                    }
                },
                onError = {
                    navController.popBackStack()
                },
            )
        }

        composable(
            route = "preview/{appId}?fromShortcut={fromShortcut}",
            arguments = listOf(
                navArgument("appId") { type = NavType.StringType },
                navArgument("fromShortcut") {
                    type = NavType.BoolType
                    defaultValue = false
                },
            ),
        ) { backStackEntry ->
            val appId = backStackEntry.arguments?.getString("appId") ?: ""
            val fromShortcut = backStackEntry.arguments?.getBoolean("fromShortcut") == true
            PreviewScreen(
                hideQuickActions = fromShortcut,
                onBack = {
                    navController.popBackStack()
                },
                onOpenApps = {
                    navController.navigate("apps")
                },
                onEdit = {
                    navController.navigate("image-prompt?editAppId=$appId")
                },
            )
        }

        composable(route = "apps") {
            AppsScreen(
                onOpenApp = { appId ->
                    navController.navigate("preview/$appId")
                },
                onEditApp = { appId ->
                    navController.navigate("image-prompt?editAppId=$appId")
                },
                onCreateApps = { navController.navigate("image-prompt") },
                onOpenSettings = {
                    navController.navigate("settings")
                },
            )
        }

        composable(route = "settings") {
            SettingsScreen(
                onBack = { navController.popBackStack() },
                onLoggedOut = {
                    navController.navigate("auth") {
                        popUpTo(0) { inclusive = true }
                    }
                },
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
