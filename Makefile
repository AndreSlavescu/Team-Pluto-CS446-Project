.PHONY: format format-python format-android lint lint-python lint-android test-android quality-android install-python-tools

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
	@if [ -f gradlew ]; then \
		chmod +x gradlew && ./gradlew ktlintFormat; \
	else \
		echo "gradlew not found; skipping Android formatting."; \
	fi

lint-android:
	@if [ -f gradlew ]; then \
		chmod +x gradlew && ./gradlew ktlintCheck lint; \
	else \
		echo "gradlew not found; skipping Android linting."; \
	fi

test-android:
	@if [ -f gradlew ]; then \
		chmod +x gradlew && ./gradlew testDebugUnitTest; \
	else \
		echo "gradlew not found; skipping Android tests."; \
	fi

# Run all Android quality checks (lint + tests)
quality-android: lint-android test-android
