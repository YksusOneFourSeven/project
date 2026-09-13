#!/usr/bin/env sh
# Полная согласованная резервная копия PostgreSQL, включая пользователей и журнал.
set -eu
mkdir -p backups
archive="backups/progress-$(date +%Y%m%d-%H%M%S).dump"
docker compose exec -T db pg_dump -U progress -d progress -Fc > "$archive"
echo "Создана копия: $archive"
