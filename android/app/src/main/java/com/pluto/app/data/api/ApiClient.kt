package com.pluto.app.data.api

import com.pluto.app.BuildConfig
import com.pluto.app.data.auth.TokenStore
import com.pluto.app.data.model.RefreshRequest
import okhttp3.Authenticator
import okhttp3.Interceptor
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.Route
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

object ApiClient {
    private const val BASE_URL = BuildConfig.API_BASE_URL

    private val loggingInterceptor =
        HttpLoggingInterceptor().apply {
            level = if (BuildConfig.DEBUG) HttpLoggingInterceptor.Level.BODY else HttpLoggingInterceptor.Level.NONE
        }

    private val authInterceptor =
        Interceptor { chain ->
            val original = chain.request()
            val token = TokenStore.getAccessToken()
            if (token != null && !isAuthEndpoint(original)) {
                val request =
                    original.newBuilder()
                        .header("Authorization", "Bearer $token")
                        .build()
                chain.proceed(request)
            } else {
                chain.proceed(original)
            }
        }

    private val tokenAuthenticator =
        Authenticator { _: Route?, response: Response ->
            if (response.request.header("X-Retry-Auth") != null) {
                TokenStore.clearSession()
                return@Authenticator null
            }

            val refreshToken =
                TokenStore.getRefreshToken() ?: run {
                    TokenStore.clearSession()
                    return@Authenticator null
                }

            try {
                val refreshResponse =
                    refreshService
                        .refreshToken(RefreshRequest(refreshToken))
                        .execute()

                if (refreshResponse.isSuccessful) {
                    val body = refreshResponse.body()!!
                    TokenStore.saveTokens(body.accessToken, body.refreshToken)
                    response.request.newBuilder()
                        .header("Authorization", "Bearer ${body.accessToken}")
                        .header("X-Retry-Auth", "true")
                        .build()
                } else {
                    TokenStore.clearSession()
                    null
                }
            } catch (_: Exception) {
                TokenStore.clearSession()
                null
            }
        }

    private fun isAuthEndpoint(request: Request): Boolean {
        val path = request.url.encodedPath
        return path.contains("/v1/auth/login") ||
            path.contains("/v1/auth/register") ||
            path.contains("/v1/auth/refresh")
    }

    private val okHttpClient =
        OkHttpClient.Builder()
            .addInterceptor(authInterceptor)
            .addInterceptor(loggingInterceptor)
            .authenticator(tokenAuthenticator)
            .connectTimeout(10, TimeUnit.SECONDS)
            .readTimeout(120, TimeUnit.SECONDS)
            .writeTimeout(60, TimeUnit.SECONDS)
            .build()

    private val retrofit: Retrofit =
        Retrofit.Builder()
            .baseUrl(BASE_URL)
            .client(okHttpClient)
            .addConverterFactory(GsonConverterFactory.create())
            .build()

    private val refreshService: RefreshApiService =
        Retrofit.Builder()
            .baseUrl(BASE_URL)
            .client(
                OkHttpClient.Builder()
                    .connectTimeout(10, TimeUnit.SECONDS)
                    .readTimeout(30, TimeUnit.SECONDS)
                    .build(),
            )
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(RefreshApiService::class.java)

    @Suppress("KotlinConstantConditions")
    val service: PlutoApiService = if (BuildConfig.USE_MOCK_API) FakePlutoApiService() else retrofit.create(PlutoApiService::class.java)
}
