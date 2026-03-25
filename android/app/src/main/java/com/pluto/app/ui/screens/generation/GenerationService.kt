package com.pluto.app.ui.screens.generation

import android.app.*
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import com.pluto.app.MainActivity
import com.pluto.app.R
import com.pluto.app.data.repository.AppRepository
import kotlinx.coroutines.*

class GenerationService : Service() {
    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val repository = AppRepository()
    private val manager by lazy { GenerationManager.getInstance(this) }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val jobId = intent?.getStringExtra("jobId") ?: return START_NOT_STICKY
        val appId = intent?.getStringExtra("appId") ?: return START_NOT_STICKY

        createNotificationChannel()
        val notification = createNotification("Initializing generation...")
        startForeground(NOTIFICATION_ID, notification)

        startPolling(jobId, appId)
        return START_STICKY
    }

    private fun startPolling(jobId: String, appId: String) {
        serviceScope.launch {
            var attempts = 0
            val maxAttempts = 150
            var consecutiveErrors = 0

            while (attempts < maxAttempts) {
                try {
                    val jobResponse = repository.getJobStatus(jobId)
                    manager.updateStatus(jobId, GenerationStatus.Loading(jobResponse))
                    
                    updateNotification("Progress: ${jobResponse.progress?.percent ?: 0}% - ${jobResponse.progress?.message ?: "Processing..."}")

                    when (jobResponse.status) {
                        "SUCCEEDED" -> {
                            manager.registerAppLocally(appId)
                            manager.updateStatus(jobId, GenerationStatus.Success(appId))
                            showCompletionNotification("Success!", "Your app is ready.")
                            stopSelf()
                            return@launch
                        }
                        "FAILED", "CANCELLED" -> {
                            val msg = jobResponse.error?.message ?: "Generation failed"
                            manager.updateStatus(jobId, GenerationStatus.Error(msg))
                            showCompletionNotification("Generation Failed", msg)
                            stopSelf()
                            return@launch
                        }
                    }
                    consecutiveErrors = 0
                } catch (e: Exception) {
                    consecutiveErrors++
                    if (consecutiveErrors >= 3) {
                        val errorMsg = AppRepository.extractErrorMessage(e)
                        manager.updateStatus(jobId, GenerationStatus.Error(errorMsg))
                        showCompletionNotification("Connection Issue", errorMsg)
                        stopSelf()
                        return@launch
                    }
                }
                attempts++
                delay(2000)
            }
            manager.updateStatus(jobId, GenerationStatus.Error("Timed out"))
            stopSelf()
        }
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "App Generation",
                NotificationManager.IMPORTANCE_LOW
            )
            val service = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            service.createNotificationChannel(channel)
        }
    }

    private fun createNotification(content: String): Notification {
        val intent = Intent(this, MainActivity::class.java)
        val pendingIntent = PendingIntent.getActivity(this, 0, intent, PendingIntent.FLAG_IMMUTABLE)

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Building your app")
            .setContentText(content)
            .setSmallIcon(android.R.drawable.stat_notify_sync)
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .build()
    }

    private fun updateNotification(content: String) {
        val notificationManager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        notificationManager.notify(NOTIFICATION_ID, createNotification(content))
    }

    private fun showCompletionNotification(title: String, content: String) {
        val notification = NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle(title)
            .setContentText(content)
            .setSmallIcon(android.R.drawable.stat_sys_download_done)
            .setAutoCancel(true)
            .build()
        val notificationManager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        notificationManager.notify(2, notification)
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        serviceScope.cancel()
        super.onDestroy()
    }

    companion object {
        private const val CHANNEL_ID = "generation_channel"
        private const val NOTIFICATION_ID = 1
    }
}
