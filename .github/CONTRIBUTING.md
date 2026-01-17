# Contributing

## Local Prerequisites

The pre-commit hook runs Android quality tasks via Gradle. You need:
- JDK 17
- Android SDK with platform 34 and build-tools 34.0.0

Recommended installs:
- JDK 17: install via your OS package manager or Android Studio JDK.
- Android SDK: install via Android Studio (SDK Manager) or the `sdkmanager` CLI.

If using the CLI, set these env vars in your shell:

```
export ANDROID_SDK_ROOT=$HOME/Library/Android/sdk
export ANDROID_HOME=$ANDROID_SDK_ROOT
```

## Install git hooks (one-time)

```
./scripts/install-githooks.sh
```

To skip hooks for a single commit:

```
SKIP_ANDROID_QUALITY=1 git commit -m "..."
```

## What runs on commit

```
./scripts/android-quality.sh --format
```

This runs `ktlintFormat`, then `ktlintCheck`, `lint`, and lastly `testDebugUnitTest`.
