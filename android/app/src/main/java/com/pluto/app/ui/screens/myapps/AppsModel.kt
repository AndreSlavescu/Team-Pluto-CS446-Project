package com.pluto.app.ui.screens.myapps

data class AppsModel(
    val id: String,
    val name: String,
    val localPath: String,
    val updatedAtMillis: Long,
)
