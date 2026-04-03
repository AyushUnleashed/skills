#!/usr/bin/env bash
# Verify required environment variables exist in .env without printing values.
# Usage: bash verify_env.sh [--provider openai|elevenlabs]

set -euo pipefail

PROVIDER="${2:-openai}"
ENV_FILE=".env"

if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: No .env file found in $(pwd)"
    exit 1
fi

REQUIRED_KEYS=("FAL_API_KEY")

if [ "$PROVIDER" = "openai" ]; then
    REQUIRED_KEYS+=("OPENAI_API_KEY")
elif [ "$PROVIDER" = "elevenlabs" ]; then
    REQUIRED_KEYS+=("ELEVEN_LABS_API_KEY")
fi

MISSING=()
for KEY in "${REQUIRED_KEYS[@]}"; do
    if ! grep -q "^${KEY}=" "$ENV_FILE"; then
        MISSING+=("$KEY")
    fi
done

if [ ${#MISSING[@]} -gt 0 ]; then
    echo "ERROR: Missing env vars in .env: ${MISSING[*]}"
    exit 1
fi

echo "OK: All required env vars present for provider=$PROVIDER"
