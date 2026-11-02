#!/usr/bin/env bash
# 관측 기록 DB(Neon) 매일 백업(2026-10-17). 서버 cron이 돌린다(배포 잡이 등록) — 저장소가 공개라 GitHub에는 두지 않는다.
# ~/backups/neon-YYYY-MM-DD.sql.gz, 14일 지난 것은 지운다. 주소는 .env의 DATABASE_URL(출력하지 않는다)
set -euo pipefail
cd "$HOME/maple-optimizer"
URL=$(grep '^DATABASE_URL=' .env | cut -d= -f2- || true)
if [ -z "$URL" ]; then
  echo "$(date -Is) DATABASE_URL이 없어 건너뜀"
  exit 0
fi
mkdir -p "$HOME/backups"
umask 077
out="$HOME/backups/neon-$(date +%F).sql.gz"
docker run --rm -e PGURL="$URL" postgres:17 sh -c 'pg_dump "$PGURL"' | gzip > "$out.tmp"
mv "$out.tmp" "$out"
find "$HOME/backups" -name 'neon-*.sql.gz' -mtime +14 -delete
echo "$(date -Is) 백업 $(du -h "$out" | cut -f1)"
