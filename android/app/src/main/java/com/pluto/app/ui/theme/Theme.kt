package com.pluto.app.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable

private val DarkColorScheme =
    darkColorScheme(
        primary = PlutoTeal,
        onPrimary = PlutoDark,
        secondary = PlutoTealDark,
        background = PlutoDark,
        surface = PlutoSurface,
        surfaceVariant = PlutoCard,
        onBackground = PlutoText,
        onSurface = PlutoText,
        onSurfaceVariant = PlutoMuted,
        error = PlutoError,
        onError = PlutoText,
    )

@Composable
fun PlutoTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = DarkColorScheme,
        typography = PlutoTypography,
        content = content,
    )
}
