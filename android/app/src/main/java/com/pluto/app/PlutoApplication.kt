package com.pluto.app

import android.app.Application
import com.pluto.app.data.auth.TokenStore

class PlutoApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        TokenStore.init(this)
    }
}
