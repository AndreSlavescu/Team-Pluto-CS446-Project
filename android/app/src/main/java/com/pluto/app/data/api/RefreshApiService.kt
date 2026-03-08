package com.pluto.app.data.api

import com.pluto.app.data.model.RefreshRequest
import com.pluto.app.data.model.TokenResponse
import retrofit2.Call
import retrofit2.http.Body
import retrofit2.http.POST

interface RefreshApiService {
    @POST("v1/auth/refresh")
    fun refreshToken(
        @Body request: RefreshRequest,
    ): Call<TokenResponse>
}
