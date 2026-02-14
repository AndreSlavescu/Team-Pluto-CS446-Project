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
	@if [ -f gradlew ]; then \
		chmod +x gradlew && ./gradlew $(GRADLE_ARGS) ktlintFormat; \
	else \
		echo "gradlew not found; skipping Android formatting."; \
	fi

lint-android:
	@if [ -f gradlew ]; then \
		chmod +x gradlew && ./gradlew $(GRADLE_ARGS) ktlintCheck lint; \
	else \
		echo "gradlew not found; skipping Android linting."; \
	fi

test-android:
	@if [ -f gradlew ]; then \
		chmod +x gradlew && ./gradlew $(GRADLE_ARGS) testDebugUnitTest; \
	else \
		echo "gradlew not found; skipping Android tests."; \
	fi

# Run all Android quality checks (lint + tests)
quality-android: lint-android test-android
