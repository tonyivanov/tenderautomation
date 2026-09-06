#!/bin/sh
set -eu

IMAGE="${1:?usage: scripts/smoke_test.sh IMAGE}"
SUFFIX="${CI_JOB_ID:-$$}"
NETWORK="tenderautomation-smoke-${SUFFIX}"
DB_CONTAINER="tenderautomation-smoke-db-${SUFFIX}"
APP_CONTAINER="tenderautomation-smoke-app-${SUFFIX}"
DATABASE_URL="postgresql://smoke:smoke@${DB_CONTAINER}:5432/smoke?sslmode=disable"

cleanup() {
    docker rm -f "$APP_CONTAINER" "$DB_CONTAINER" >/dev/null 2>&1 || true
    docker network rm "$NETWORK" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

docker network create "$NETWORK" >/dev/null
docker run -d --name "$DB_CONTAINER" --network "$NETWORK" \
    -e POSTGRES_USER=smoke \
    -e POSTGRES_PASSWORD=smoke \
    -e POSTGRES_DB=smoke \
    postgres:16-alpine >/dev/null

ready=0
attempt=1
while [ "$attempt" -le 30 ]; do
    if docker exec "$DB_CONTAINER" pg_isready -U smoke -d smoke >/dev/null 2>&1; then
        ready=1
        break
    fi
    attempt=$((attempt + 1))
    sleep 1
done
if [ "$ready" -ne 1 ]; then
    echo "PostgreSQL did not become ready" >&2
    exit 1
fi

docker run --rm --network "$NETWORK" \
    -e DATABASE_URL="$DATABASE_URL" \
    -e B2BCENTER_USERNAME=smoke \
    -e B2BCENTER_PASSWORD=smoke \
    "$IMAGE" alembic upgrade head

docker run --rm --network "$NETWORK" \
    -e DATABASE_URL="$DATABASE_URL" \
    -e B2BCENTER_USERNAME=smoke \
    -e B2BCENTER_PASSWORD=smoke \
    "$IMAGE" python -m web.cli add-user \
    --username smoke@example.test \
    --password smoke-password-123 \
    --role admin

docker run -d --name "$APP_CONTAINER" --network "$NETWORK" \
    -e DATABASE_URL="$DATABASE_URL" \
    -e B2BCENTER_USERNAME=smoke \
    -e B2BCENTER_PASSWORD=smoke \
    "$IMAGE" >/dev/null

ready=0
attempt=1
while [ "$attempt" -le 30 ]; do
    if docker exec "$APP_CONTAINER" python -c \
        'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8000/login", timeout=2)' \
        >/dev/null 2>&1; then
        ready=1
        break
    fi
    attempt=$((attempt + 1))
    sleep 1
done
if [ "$ready" -ne 1 ]; then
    docker logs "$APP_CONTAINER" >&2
    echo "Application did not become ready" >&2
    exit 1
fi

docker exec "$APP_CONTAINER" python /app/scripts/smoke_check.py
