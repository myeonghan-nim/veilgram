#!/usr/bin/env bash
set -euo pipefail

TEMPLATE=".env.template"
TARGET=".env.test"

# 0) 템플릿 복사(없으면 새로 생성)
if [ -f "$TEMPLATE" ]; then
  cp "$TEMPLATE" "$TARGET"
else
  : > "$TARGET"
fi

# 1) KEY가 없거나 값이 비어있으면 기본값을 채워 넣는 헬퍼
ensure() {
  local key="$1"
  local val="$2"
  if ! grep -qE "^${key}=" "$TARGET"; then
    echo "${key}=${val}" >> "$TARGET"
  else
    # 값이 비어있으면 채움
    if grep -qE "^${key}=[[:space:]]*$" "$TARGET"; then
      # 구분자를 '|'로 사용 (URL 등 슬래시 포함 값 안전)
      sed -i "s|^${key}=.*|${key}=${val}|" "$TARGET"
    fi
  fi
}

###############################################################################
# Django
###############################################################################
ensure SECRET_KEY "$(openssl rand -hex 32)"
ensure DEBUG "1"
ensure ALLOWED_HOSTS "*"

###############################################################################
# PostgreSQL (docker-compose.test.yml의 서비스명 반영)
###############################################################################
ensure POSTGRES_HOST "veilgram_test_db"
ensure POSTGRES_DB "veilgram_test"
ensure POSTGRES_USER "postgres"
ensure POSTGRES_PASSWORD "postgres"

###############################################################################
# Redis (requirepass 사용)
###############################################################################
ensure REDIS_PASSWORD "redispass"
# REDIS_URL은 반드시 비어있지 않게 설정 (set -u 보호)
REDIS_PASSWORD_VAL="$(grep -E '^REDIS_PASSWORD=' "$TARGET" | cut -d= -f2- || true)"
if [ -z "${REDIS_PASSWORD_VAL:-}" ]; then REDIS_PASSWORD_VAL="redispass"; fi
ensure REDIS_URL "redis://:${REDIS_PASSWORD_VAL}@veilgram_test_redis:6379/0"

###############################################################################
# MinIO (compose는 ROOT_* 사용)
###############################################################################
ensure MINIO_ROOT_USER "minio"
ensure MINIO_ROOT_PASSWORD "minio12345"
ensure AWS_S3_ENDPOINT_URL "http://veilgram_test_minio:9000"
ensure AWS_STORAGE_BUCKET_NAME "veilgram-test"

###############################################################################
# OpenSearch (테스트 기본 비활성; 숫자/불리언 기본값 반드시 채움)
###############################################################################
ensure OPENSEARCH_ENABLED "0"
# 비활성이라도 HOSTS는 문자열로 채워 둠(빈 문자열로 두지 않음)
ensure OPENSEARCH_HOSTS "http://opensearch:9200"
ensure OPENSEARCH_USER ""
ensure OPENSEARCH_PASSWORD ""
ensure OPENSEARCH_INDEX_PREFIX "vg_test"
ensure OPENSEARCH_USE_NORI "0"
ensure OPENSEARCH_TIMEOUT "3"

###############################################################################
# Cassandra (테스트 기본 비활성)
###############################################################################
ensure CASSANDRA_ENABLED "0"
ensure CASSANDRA_CONTACT_POINTS "cassandra:9042"
ensure CASSANDRA_KEYSPACE "veilgram_test"

###############################################################################
# RabbitMQ (테스트에서는 보통 미사용, 값은 채워 둠)
###############################################################################
ensure RABBITMQ_USER "guest"
ensure RABBITMQ_PASSWORD "guest"

###############################################################################
# Feed Service (테스트: 인메모리 버스 사용)
###############################################################################
ensure FEED_BUS_DRIVER "inmemory"  # inmemory|redis|kafka|rabbitmq 등
ensure FEED_EVENT_TOPICS "post.created,post.deleted,comment.created"

# Kafka (미사용이지만 값은 채움)
ensure FEED_KAFKA_BOOTSTRAP "kafka:9092"
ensure FEED_KAFKA_GROUP_ID "veilgram-test"

# RabbitMQ (미사용이지만 값은 채움)
ensure FEED_RABBIT_URL "amqp://guest:guest@rabbitmq:5672/"
ensure FEED_RABBIT_EXCHANGE "feed"
ensure FEED_RABBIT_QUEUE "feed_updates"

###############################################################################
# Channels / Redis
###############################################################################
ensure CHANNEL_LAYER_CAPACITY "10000"
ensure FEED_UPDATES_CHANNEL "feed_updates"

###############################################################################
# Celery / Event bus
###############################################################################
ensure PUSH_PROVIDER "console"
ensure EVENT_BUS_BACKEND "inmemory"

###############################################################################
# Audit
###############################################################################
ensure AUDIT_HASH_SALT "testsalt"
ensure AUDIT_RETENTION_DAYS "30"

echo "[OK] Generated ${TARGET}"
