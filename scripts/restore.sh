#!/usr/bin/env sh
# Восстановление заменяет содержимое БД. Требует явного аргумента --confirm.
set -eu
if [ "$#" -ne 2 ] || [ "$2" != '--confirm' ]; then
  echo 'Использование: sh scripts/restore.sh backups/имя.dump --confirm'; exit 1
fi
[ -s "$1" ] || { echo 'Файл отсутствует или пуст'; exit 1; }
docker compose stop web
if docker compose exec -T db pg_restore -U progress -d progress --clean --if-exists --single-transaction < "$1"; then
  docker compose start web
else
  echo 'Восстановление не выполнено; web оставлен остановленным для диагностики.'; exit 1
fi
