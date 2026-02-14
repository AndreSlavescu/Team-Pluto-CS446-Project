package com.pluto.app.ui.navigation

import androidx.compose.runtime.Composable
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.pluto.app.ui.screens.generation.GenerationScreen
import com.pluto.app.ui.screens.preview.PreviewScreen
import com.pluto.app.ui.screens.prompt.PromptScreen

@Composable
fun PlutoNavGraph() {
    val navController = rememberNavController()

    NavHost(navController = navController, startDestination = "prompt") {

        composable("prompt") {
            PromptScreen(
                onJobCreated = { jobId, appId ->
                    navController.navigate("generation/$jobId/$appId")
                }
            )
        }

        composable(
            route = "generation/{jobId}/{appId}",
            arguments = listOf(
                navArgument("jobId") { type = NavType.StringType },
                navArgument("appId") { type = NavType.StringType }
            )
        ) {
            GenerationScreen(
                onComplete = { appId ->
                    navController.navigate("preview/$appId") {
                        popUpTo("prompt") { inclusive = false }
                    }
                },
                onError = {
                    navController.popBackStack("prompt", inclusive = false)
                }
            )
        }

        composable(
            route = "preview/{appId}",
            arguments = listOf(
                navArgument("appId") { type = NavType.StringType }
            )
        ) {
            PreviewScreen(
                onBack = {
                    navController.popBackStack("prompt", inclusive = false)
                }
            )
        }
    }
}
