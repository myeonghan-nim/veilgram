# ---------- builder ----------
FROM python:3.12-slim AS builder

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /wheels
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

# ---------- app (runtime) ----------
FROM python:3.12-slim AS app

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev curl postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /wheels /wheels
COPY requirements.txt /tmp/requirements.txt
RUN python -m pip install --upgrade pip \
    && pip install --no-cache-dir --no-index --find-links=/wheels -r /tmp/requirements.txt \
    && rm -f /tmp/requirements.txt

COPY assets ./assets/
COPY comments ./comments/
COPY feed ./feed/
COPY hashtags ./hashtags/
COPY profiles ./profiles/
COPY polls ./polls/
COPY posts ./posts/
COPY realtime ./realtime/
COPY relations ./relations/
COPY reports ./reports/
COPY search ./search/
COPY users ./users/
COPY veilgram ./veilgram/
COPY manage.py .
COPY entrypoint.sh .

RUN chmod +x entrypoint.sh
ENTRYPOINT ["./entrypoint.sh"]


# ---------- test (optional) ----------
FROM app AS test

# 테스트 타겟에서만 pytest.ini 복사
COPY pytest.ini .
