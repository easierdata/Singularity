#!/bin/sh
set -e

# --- Environment Setup ---
# The necessary environment variables (like DB_STRING, DATABASE_CONNECTION_STRING, PATH)
# should primarily be set via ENV in the Dockerfile or 'environment' in docker-compose.
# Sourcing .bashrc here is generally not needed for the script's execution environment,
# as it only affects interactive shells started later unless variables are explicitly exported.

# Use DATABASE_CONNECTION_STRING if set, otherwise fall back to DB_STRING
# These should be available from the environment (Dockerfile ENV or docker-compose environment)
EFFECTIVE_DB_STRING="${DATABASE_CONNECTION_STRING:-$DB_STRING}"

if [ -z "$EFFECTIVE_DB_STRING" ]; then
    echo "Warning: Neither DATABASE_CONNECTION_STRING nor DB_STRING is set in the environment."
    # Decide if this is a fatal error or if singularity can run without it initially
    # exit 1 # Uncomment if the connection string is always required
fi

# Since the connection string has been validated, we can set expected ENV var that singularity expects
# and export it for the current shell session and save it to .bashrc for future interactive shells
DATABASE_CONNECTION_STRING="${EFFECTIVE_DB_STRING}"
export DATABASE_CONNECTION_STRING
echo "export DATABASE_CONNECTION_STRING=${DATABASE_CONNECTION_STRING}" >> /home/appuser/.bashrc

# Uncomment for debugging purposes
# echo "Effective DB connection string (for potential init): ${DATABASE_CONNECTION_STRING}"

# --- Conditional Initialization ---
# Check if the RUN_SINGULARITY_INIT environment variable is set to "true"
if [ "$RUN_SINGULARITY_INIT" = "true" ]; then
    echo "RUN_SINGULARITY_INIT is true. Running database initialization..."

    if [ -z "$DATABASE_CONNECTION_STRING" ]; then
        echo "Error: Cannot run init because database connection string is not set."
        exit 1
    fi

    # Execute the init command directly
    echo "Executing: singularity admin init"
    if singularity --database-connection-string="$DATABASE_CONNECTION_STRING" admin init; then
        echo "Database initialization command executed successfully."
    else
        echo "Database initialization command failed with exit code $?" >&2 # Send error to stderr
        exit 1 # Exit if init fails
    fi
    echo "Initialization complete."
    exit 0 # Exit after initialization
else
    echo "RUN_SINGULARITY_INIT is not 'true'. Skipping database initialization."
fi

# --- Execute Main Command ---
# Execute the command passed as arguments (from CMD in Dockerfile or command in docker-compose)
echo "Executing main command: $@"
exec "$@"
