#!/usr/bin/env bash
#!/usr/bin/env bash
set -euo pipefail

PROJECT="barq-assessment"
DB_USER="barq_app"
DB_NAME="barq_tasks"

if [ $# -ne 1 ]; then
    echo "Usage: $0 <backup_file.sql>" >&2
    exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
    echo "FAIL: backup file not found: $BACKUP_FILE" >&2
    exit 1
fi

echo "Checking postgres container is running..."
if ! docker compose -p "$PROJECT" ps postgres --status running --format json > /dev/null 2>&1; then
    echo "FAIL: postgres container is not running" >&2
    exit 1
fi

echo "Restoring $BACKUP_FILE into database '$DB_NAME'..."
RESTORE_OUTPUT="$(docker compose -p "$PROJECT" exec -T postgres psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$DB_NAME" < "$BACKUP_FILE" 2>&1)"
RESTORE_EXIT=$?

echo "$RESTORE_OUTPUT"

if [ $RESTORE_EXIT -ne 0 ]; then
    echo "FAIL: restore encountered errors (psql exit code $RESTORE_EXIT)" >&2
    exit 1
fi

echo "PASS: restore from $BACKUP_FILE complete"
