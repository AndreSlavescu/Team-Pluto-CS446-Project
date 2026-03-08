package com.pluto.app.data.auth

import com.pluto.app.data.api.ApiClient
import com.pluto.app.data.api.PlutoApiService
import com.pluto.app.data.model.LoginRequest
import com.pluto.app.data.model.RefreshRequest
import com.pluto.app.data.model.RegisterRequest

class AuthRepository(
    private val api: PlutoApiService = ApiClient.service,
) {
    suspend fun register(
        email: String,
        password: String,
    ) {
        val response = api.register(RegisterRequest(email, password))
        TokenStore.saveTokens(response.accessToken, response.refreshToken)
        TokenStore.saveEmail(email)
    }

    suspend fun login(
        email: String,
        password: String,
    ) {
        val response = api.login(LoginRequest(email, password))
        TokenStore.saveTokens(response.accessToken, response.refreshToken)
        TokenStore.saveEmail(email)
    }

    suspend fun logout() {
        val refreshToken = TokenStore.getRefreshToken()
        if (refreshToken != null) {
            try {
                api.logout(RefreshRequest(refreshToken))
            } catch (_: Exception) {
                // Best-effort server logout
            }
        }
        TokenStore.clearTokens()
    }

    suspend fun deleteAccount() {
        api.deleteAccount()
        TokenStore.clearTokens()
    }

    fun isLoggedIn(): Boolean = TokenStore.isLoggedIn()

    fun getEmail(): String? = TokenStore.getEmail()
}
