package com.pluto.app.ui.screens.auth

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.pluto.app.data.auth.AuthRepository
import com.pluto.app.data.auth.TokenStore
import com.pluto.app.data.repository.AppRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

class AuthViewModel : ViewModel() {
    private val authRepo = AuthRepository()

    private val _requiresBiometricUnlock =
        MutableStateFlow(TokenStore.isLoggedIn() && TokenStore.isBiometricEnabled())
    val requiresBiometricUnlock: StateFlow<Boolean> = _requiresBiometricUnlock

    private val _email = MutableStateFlow("")
    val email: StateFlow<String> = _email

    private val _password = MutableStateFlow("")
    val password: StateFlow<String> = _password

    private val _isLoginTab = MutableStateFlow(true)
    val isLoginTab: StateFlow<Boolean> = _isLoginTab

    private val _isLoading = MutableStateFlow(false)
    val isLoading: StateFlow<Boolean> = _isLoading

    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error

    private val _authSuccess = MutableStateFlow(false)
    val authSuccess: StateFlow<Boolean> = _authSuccess

    fun updateEmail(value: String) {
        _email.value = value
        _error.value = null
    }

    fun updatePassword(value: String) {
        _password.value = value
        _error.value = null
    }

    fun switchTab(isLogin: Boolean) {
        _isLoginTab.value = isLogin
        _error.value = null
    }

    fun submit() {

        val emailVal = _email.value.trim()
        val passwordVal = _password.value

        if (emailVal.isBlank() || passwordVal.isBlank()) {
            _error.value = "Please fill in all fields"
            return
        }

        if (!emailVal.contains("@")) {
            _error.value = "Please enter a valid email"
            return
        }

        if (passwordVal.length < 8) {
            _error.value = "Password must be at least 8 characters"
            return
        }

        _isLoading.value = true
        _error.value = null

        viewModelScope.launch {
            try {
                if (_isLoginTab.value) {
                    authRepo.login(emailVal, passwordVal)
                } else {
                    authRepo.register(emailVal, passwordVal)
                }
                _authSuccess.value = true
            } catch (e: Exception) {
                _error.value = AppRepository.extractErrorMessage(e)
            } finally {
                _isLoading.value = false
            }
        }
    }

    fun onBiometricUnlockSuccess() {
        _requiresBiometricUnlock.value = false
        _error.value = null
        _authSuccess.value = true
    }

    fun setBiometricError(message: String) {
        _error.value = message
    }

    fun resetSuccess() {
        _authSuccess.value = false
    }
}
