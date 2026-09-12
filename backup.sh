#!/usr/bin/env bash
#!/usr/bin/env bash
set -euo pipefail

PROJECT="barq-assessment"
DB_USER="barq_app"
DB_NAME="barq_tasks"
BACKUP_DIR="backups"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_FILE="${BACKUP_DIR}/backup_${TIMESTAMP}.sql"

mkdir -p "$BACKUP_DIR"

echo "Checking postgres container is running..."
if ! docker compose -p "$PROJECT" ps postgres --status running --format json > /dev/null 2>&1; then
    echo "FAIL: postgres container is not running" >&2
    exit 1
fi

echo "Backing up database '$DB_NAME' to $BACKUP_FILE..."
docker compose -p "$PROJECT" exec -T postgres pg_dump --clean --if-exists -U "$DB_USER" "$DB_NAME" > "$BACKUP_FILE"

if [ ! -s "$BACKUP_FILE" ]; then
    echo "FAIL: backup file is empty" >&2
    exit 1
fi

echo "PASS: backup written to $BACKUP_FILE ($(wc -l < "$BACKUP_FILE") lines)"
