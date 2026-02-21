plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "com.pluto.app"
    compileSdk = 35
    defaultConfig {
        applicationId = "com.pluto.app"
        minSdk = 26
        targetSdk = 34
        versionCode = 1
        versionName = "0.1.0"

        buildConfigField("String", "API_BASE_URL", "\"http://127.0.0.1:8000\"")
        buildConfigField("boolean", "USE_MOCK_API", "false")
        buildConfigField("boolean", "USE_DEFAULT_APPS", "false")
    }

    buildTypes {
        debug {
            // Override with emulator localhost for local dev
            buildConfigField("String", "API_BASE_URL", "\"http://127.0.0.1:8000\"")
            // using a mocked api that returns a pregenerated html app
            buildConfigField("boolean", "USE_MOCK_API", "false")
            // using dummy apps
            buildConfigField("boolean", "USE_DEFAULT_APPS", "false")
        }
        release {
            isMinifyEnabled = false
            buildConfigField("boolean", "USE_MOCK_API", "false")
            buildConfigField("boolean", "USE_DEFAULT_APPS", "false")
            signingConfig = signingConfigs.getByName("debug")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2024.09.03")
    implementation(composeBom)

    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")

    implementation("androidx.activity:activity-compose:1.9.2")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.6")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.6")

    implementation("androidx.navigation:navigation-compose:2.8.3")

    implementation("com.squareup.retrofit2:retrofit:2.11.0")
    implementation("com.squareup.retrofit2:converter-gson:2.11.0")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("com.squareup.okhttp3:logging-interceptor:4.12.0")

    debugImplementation("androidx.compose.ui:ui-tooling")
}
