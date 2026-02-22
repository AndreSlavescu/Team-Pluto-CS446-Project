.PHONY: format format-python format-android lint lint-python lint-android test-android quality-android install-python-tools

GRADLE_ARGS :=
ifdef CI
	GRADLE_ARGS += --no-daemon
endif

# Install Python formatting and linting tools
install-python-tools:
	pip install black ruff

# Format all code
format: format-python format-android

# Lint all code
lint: lint-python lint-android

# Python targets
format-python:
	black backend/

lint-python:
	black --check --diff backend/
	ruff check backend/

# Android targets
format-android:
	@if [ ! -f android/gradlew ]; then \
		echo "ERROR: android/gradlew not found. Are you running from the repo root?"; exit 1; \
	elif ! command -v java >/dev/null 2>&1; then \
		echo "ERROR: Java is not installed. Install it with: brew install --cask temurin@17"; exit 1; \
	else \
		chmod +x android/gradlew && cd android && ./gradlew $(GRADLE_ARGS) ktlintFormat; \
	fi

lint-android:
	@if [ ! -f android/gradlew ]; then \
		echo "ERROR: android/gradlew not found. Are you running from the repo root?"; exit 1; \
	elif ! command -v java >/dev/null 2>&1; then \
		echo "ERROR: Java is not installed. Install it with: brew install --cask temurin@17"; exit 1; \
	else \
		chmod +x android/gradlew && cd android && ./gradlew $(GRADLE_ARGS) ktlintCheck; \
		if [ -n "$$ANDROID_HOME" ] || grep -q "sdk.dir" local.properties 2>/dev/null; then \
			./gradlew $(GRADLE_ARGS) lint; \
		else \
			echo "WARNING: Android lint skipped — Android SDK not found."; \
			echo "         To run Android lint, install Android Studio: https://developer.android.com/studio"; \
		fi; \
	fi

test-android:
	@if [ ! -f android/gradlew ]; then \
		echo "ERROR: android/gradlew not found. Are you running from the repo root?"; exit 1; \
	elif ! command -v java >/dev/null 2>&1; then \
		echo "ERROR: Java is not installed. Install it with: brew install --cask temurin@17"; exit 1; \
	else \
		chmod +x android/gradlew && cd android && ./gradlew $(GRADLE_ARGS) testDebugUnitTest; \
	fi

# Run all Android quality checks (lint + tests)
quality-android: lint-android test-android
