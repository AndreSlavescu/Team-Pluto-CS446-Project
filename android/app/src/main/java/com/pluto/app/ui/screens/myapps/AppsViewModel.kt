package com.pluto.app.ui.screens.myapps

import android.annotation.SuppressLint
import android.app.Application
import android.content.Intent
import android.content.pm.ShortcutInfo
import android.content.pm.ShortcutManager
import android.graphics.drawable.Icon
import com.pluto.app.MainActivity
import android.text.format.DateUtils
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.pluto.app.BuildConfig
import com.pluto.app.data.repository.AppRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.UUID

class AppsViewModel(application: Application) : AndroidViewModel(application) {
    private val repository = AppRepository()
    private val prefs = application.getSharedPreferences(PREFS_NAME, 0)
    private val _savedApps = MutableStateFlow<List<AppsModel>>(emptyList())
    val savedApps: StateFlow<List<AppsModel>> = _savedApps.asStateFlow()
    private val _selectedIds = MutableStateFlow<Set<String>>(emptySet())
    val selectedIds: StateFlow<Set<String>> = _selectedIds.asStateFlow()

    @Suppress("KotlinConstantConditions")
    fun loadSavedApps() {
        viewModelScope.launch {
            val persisted = readPersistedApps()
            val scanned = scanSavedAppPaths()
            val mergedApps = mergeSavedApps(
                persisted = persisted,
                scanned = scanned
            )
            val apps = if (!BuildConfig.USE_DEFAULT_APPS) {
                enrichAppNames(mergedApps)
            } else {
                defaultApps()
            }
            _savedApps.value = apps.sortedByDescending { it.updatedAtMillis }
            _selectedIds.value = _selectedIds.value.intersect(_savedApps.value.map { it.id }.toSet())
            persistApps(_savedApps.value)
        }
    }

    fun toggleSelection(appId: String) {
        _selectedIds.update { selected ->
            if (selected.contains(appId)) selected - appId else selected + appId
        }
    }

    fun clearSelection() {
        _selectedIds.value = emptySet()
    }

    fun registerSavedApp(localPath: String, name: String? = null) {
        val file = File(localPath)
        if (!file.exists()) return
        val normalizedPath = if (file.isDirectory) file.absolutePath else file.parentFile?.absolutePath
            ?: file.absolutePath
        val fallbackName = if (file.isDirectory) {
            file.nameWithoutExtension.ifBlank { "Generated App" }
        } else {
            file.parentFile?.nameWithoutExtension?.ifBlank { "Generated App" } ?: "Generated App"
        }

        upsertSavedApp(
            localPath = normalizedPath,
            name = name ?: fallbackName
        )
    }

    fun registerGeneratedApp(appId: String, name: String? = null) {
        val generatedDir = File(
            getApplication<Application>().filesDir,
            "$DEFAULT_SAVED_APPS_DIR/$appId"
        )
        upsertSavedApp(
            localPath = generatedDir.absolutePath,
            name = name ?: "Generated App",
            preferredId = appId
        )
        viewModelScope.launch {
            runCatching {
                repository.getLatestVersion(appId).manifest.displayName
            }.onSuccess { resolvedName ->
                if (resolvedName.isNotBlank()) {
                    upsertSavedApp(
                        localPath = generatedDir.absolutePath,
                        name = resolvedName,
                        preferredId = appId
                    )
                }
            }
        }
    }

    fun previewAppIdFor(app: AppsModel): String {
        return extractPreviewAppId(app)
    }

    private fun upsertSavedApp(localPath: String, name: String, preferredId: String? = null) {
        val updatedAt = System.currentTimeMillis()
        _savedApps.update { current ->
            val existing = current.firstOrNull { it.localPath == localPath }
            val updatedEntry = if (existing != null) {
                existing.copy(
                    name = name,
                    updatedAtMillis = updatedAt
                )
            } else {
                AppsModel(
                    id = preferredId ?: UUID.randomUUID().toString(),
                    name = name,
                    localPath = localPath,
                    updatedAtMillis = updatedAt
                )
            }
            (current.filterNot { it.localPath == localPath } + updatedEntry)
                .sortedByDescending { it.updatedAtMillis }
        }
        persistApps(_savedApps.value)
    }

    fun deleteSelectedApps(): List<AppsModel> {
        val selected = _savedApps.value.filter { _selectedIds.value.contains(it.id) }
        selected.forEach { app ->
            runCatching {
                val file = File(app.localPath)
                if (file.exists()) {
                    if (file.isDirectory) file.deleteRecursively() else file.delete()
                }
            }
        }
        removeLauncherShortcuts(selected)

        _savedApps.update { apps -> apps.filterNot { _selectedIds.value.contains(it.id) } }
        _selectedIds.value = emptySet()
        persistApps(_savedApps.value)
        return selected
    }

    fun selectedApps(): List<AppsModel> {
        val selected = _selectedIds.value
        return _savedApps.value.filter { selected.contains(it.id) }
    }

    fun exportSelectedApps(onExportApps: (List<AppsModel>) -> Unit = {}): Int {
        val exportedApps = selectedApps()
        if (exportedApps.isEmpty()) return 0

        onExportApps(exportedApps)
        createLauncherShortcuts(exportedApps)
        return exportedApps.size
    }

    fun updatedLabel(updatedAtMillis: Long): String {
        val relative = DateUtils.getRelativeTimeSpanString(
            updatedAtMillis,
            System.currentTimeMillis(),
            DateUtils.MINUTE_IN_MILLIS
        )
        return "Updated $relative"
    }

    private fun createLauncherShortcuts(apps: List<AppsModel>) {
        val context = getApplication<Application>()
        val shortcutManager =
            context.getSystemService(ShortcutManager::class.java) ?: return

        val launchShortcuts = apps.map { app ->
            val targetIntent = Intent(context, MainActivity::class.java).apply {
                action = Intent.ACTION_VIEW
                putExtra(MainActivity.EXTRA_OPEN_APPS, true)
                putExtra(MainActivity.EXTRA_OPEN_APP_ID, extractPreviewAppId(app))
            }

            ShortcutInfo.Builder(context, generatedShortcutId(app.id))
                .setShortLabel(app.name.take(24))
                .setLongLabel("Open ${app.name}")
                .setIcon(Icon.createWithResource(context, android.R.drawable.sym_def_app_icon))
                .setIntent(targetIntent)
                .build()
        }

        val existingNonGenerated = shortcutManager.dynamicShortcuts
            .filterNot { it.id.startsWith(GENERATED_SHORTCUT_PREFIX) }

        shortcutManager.dynamicShortcuts = (existingNonGenerated + launchShortcuts)
            .take(4)
    }

    private fun removeLauncherShortcuts(apps: List<AppsModel>) {
        if (apps.isEmpty()) return

        val context = getApplication<Application>()
        val shortcutManager = context.getSystemService(ShortcutManager::class.java) ?: return
        val shortcutIdsToRemove = apps.map { generatedShortcutId(it.id) }
        shortcutManager.removeDynamicShortcuts(shortcutIdsToRemove)
        runCatching {
            shortcutManager.disableShortcuts(
                shortcutIdsToRemove,
                "This app was deleted"
            )
        }
    }

    private fun mergeSavedApps(
        persisted: List<AppsModel>,
        scanned: List<AppsModel>
    ): List<AppsModel> {
        val mergedByPreviewId = linkedMapOf<String, AppsModel>()

        persisted.forEach { app ->
            mergedByPreviewId[extractPreviewAppId(app)] = app
        }

        scanned.forEach { scannedApp ->
            val key = extractPreviewAppId(scannedApp)
            val existing = mergedByPreviewId[key]
            mergedByPreviewId[key] = if (existing == null) {
                scannedApp.copy(id = key)
            } else {
                existing.copy(
                    id = key,
                    name = if (existing.name.isNotBlank()) existing.name else scannedApp.name,
                    localPath = scannedApp.localPath,
                    updatedAtMillis = maxOf(existing.updatedAtMillis, scannedApp.updatedAtMillis)
                )
            }
        }

        return mergedByPreviewId.values.toList()
    }

    private fun extractPreviewAppId(app: AppsModel): String {
        val path = File(app.localPath)
        return if (path.isFile) {
            path.parentFile?.name ?: app.id
        } else {
            path.name.ifBlank { app.id }
        }
    }

    private fun scanSavedAppPaths(): List<AppsModel> {
        val root = File(getApplication<Application>().filesDir, DEFAULT_SAVED_APPS_DIR)
        if (!root.exists()) return emptyList()

        return root.listFiles().orEmpty().mapNotNull { file ->
            if (!file.exists()) return@mapNotNull null
            AppsModel(
                id = UUID.randomUUID().toString(),
                name = file.nameWithoutExtension.ifBlank { "Generated App" },
                localPath = file.absolutePath,
                updatedAtMillis = file.lastModified()
            )
        }
    }

    private suspend fun enrichAppNames(apps: List<AppsModel>): List<AppsModel> {
        return apps.map { app ->
            val previewId = extractPreviewAppId(app)
            val shouldResolveName = app.name == previewId || app.name == "Generated App"

            if (!shouldResolveName || previewId.isBlank()) {
                app
            } else {
                val resolvedName = runCatching {
                    repository.getLatestVersion(previewId).manifest.displayName
                }.getOrNull()

                if (resolvedName.isNullOrBlank()) app else app.copy(name = resolvedName)
            }
        }
    }

    private fun defaultApps(): List<AppsModel> {
        val now = System.currentTimeMillis()
        val root = File(getApplication<Application>().filesDir, DEFAULT_SAVED_APPS_DIR)
        return listOf(
            AppsModel(
                id = "default-todo",
                name = "Todo List App",
                localPath = File(root, "todo-list-app").absolutePath,
                updatedAtMillis = now - DateUtils.MINUTE_IN_MILLIS * 2
            ),
            AppsModel(
                id = "default-ecommerce",
                name = "E-commerce Store",
                localPath = File(root, "e-commerce-store").absolutePath,
                updatedAtMillis = now - DateUtils.HOUR_IN_MILLIS
            ),
            AppsModel(
                id = "default-portfolio",
                name = "Portfolio Site",
                localPath = File(root, "portfolio-site").absolutePath,
                updatedAtMillis = now - DateUtils.DAY_IN_MILLIS * 2
            ),
            AppsModel(
                id = "default-chat",
                name = "Chat Bot Interface",
                localPath = File(root, "chat-bot-interface").absolutePath,
                updatedAtMillis = now - DateUtils.DAY_IN_MILLIS * 5
            )
        )
    }

    @SuppressLint("UseKtx")
    private fun persistApps(apps: List<AppsModel>) {
        val json = JSONArray()
        apps.forEach { app ->
            json.put(
                JSONObject()
                    .put("id", app.id)
                    .put("name", app.name)
                    .put("localPath", app.localPath)
                    .put("updatedAtMillis", app.updatedAtMillis)
            )
        }
        prefs.edit().putString(KEY_SAVED_APPS, json.toString()).apply()
    }

    private fun readPersistedApps(): List<AppsModel> {
        val raw = prefs.getString(KEY_SAVED_APPS, null) ?: return emptyList()
        return runCatching {
            val array = JSONArray(raw)
            buildList {
                for (i in 0 until array.length()) {
                    val item = array.optJSONObject(i) ?: continue
                    val path = item.optString("localPath")
                    if (path.isBlank()) continue
                    add(
                        AppsModel(
                            id = item.optString("id").ifBlank { UUID.randomUUID().toString() },
                            name = item.optString("name").ifBlank { "Generated App" },
                            localPath = path,
                            updatedAtMillis = item.optLong("updatedAtMillis", System.currentTimeMillis())
                        )
                    )
                }
            }
        }.getOrDefault(emptyList())
    }

    companion object {
        private const val PREFS_NAME = "my_apps_store"
        private const val KEY_SAVED_APPS = "saved_apps"
        private const val DEFAULT_SAVED_APPS_DIR = "saved_apps"
        private const val GENERATED_SHORTCUT_PREFIX = "pluto-generated-"

        private fun generatedShortcutId(appId: String): String = "$GENERATED_SHORTCUT_PREFIX$appId"
    }

}
