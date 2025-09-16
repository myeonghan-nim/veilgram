#!/usr/bin/env bash
set -euo pipefail

TEMPLATE=".env.template"
TARGET=".env.test"

# 1) 템플릿이 있으면 복사(비어있는 값은 아래에서 채움), 없으면 새로 생성
if [ -f "$TEMPLATE" ]; then
  cp "$TEMPLATE" "$TARGET"
else
  : > "$TARGET"
fi

# 2) 값이 비어있다면 테스트 기본값 주입
ensure() {
  local key="$1"
  local val="$2"
  if ! grep -qE "^${key}=" "$TARGET"; then
    echo "${key}=${val}" >> "$TARGET"
  else
    # 값이 비어있으면 채움
    if grep -qE "^${key}=$" "$TARGET"; then
      sed -i "s|^${key}=.*|${key}=${val}|" "$TARGET"
    fi
  fi
}

# Django
ensure SECRET_KEY "$(openssl rand -hex 32)"
ensure DEBUG "1"
ensure ALLOWED_HOSTS "*"

# PostgreSQL (compose의 서비스명 기준)
ensure POSTGRES_HOST "veilgram_test_db"
ensure POSTGRES_DB "veilgram_test"
ensure POSTGRES_USER "postgres"
ensure POSTGRES_PASSWORD "postgres"

# Redis (requirepass 사용)
ensure REDIS_PASSWORD "redispass"
REDIS_PASSWORD_VAL="$(grep -E '^REDIS_PASSWORD=' "$TARGET" | cut -d= -f2- || true)"
if [ -z "$REDIS_PASSWORD_VAL" ]; then REDIS_PASSWORD_VAL="redispass"; fi
ensure REDIS_URL "redis://:${REDIS_PASSWORD_VAL}@test_redis:6379/0"

# MinIO
ensure MINIO_ROOT_USER "minio"
ensure MINIO_ROOT_PASSWORD "minio12345"
ensure AWS_S3_ENDPOINT_URL "http://veilgram_test_minio:9000"
ensure AWS_STORAGE_BUCKET_NAME "veilgram-test"

# 검색/피드 등 선택 기능은 테스트에서 기본 OFF
ensure OPENSEARCH_ENABLED "0"
ensure CASSANDRA_ENABLED "0"

# Channels / Feed (테스트 기본값)
ensure CHANNEL_LAYER_CAPACITY "10000"
ensure FEED_UPDATES_CHANNEL "feed_updates"

# Celery / Event bus (단위/통합 테스트는 인메모리)
ensure PUSH_PROVIDER "console"
ensure EVENT_BUS_BACKEND "inmemory"

# Audit
ensure AUDIT_HASH_SALT "testsalt"
ensure AUDIT_RETENTION_DAYS "30"

echo "[OK] Generated ${TARGET}"
