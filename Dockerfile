FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY profiles ./profiles/
COPY polls ./polls/
COPY posts ./posts/
COPY relations ./relations/
COPY users ./users/
COPY veilgram ./veilgram/
COPY entrypoint.sh .
COPY manage.py .

# Only for test
COPY pytest.ini .

RUN chmod +x entrypoint.sh
ENTRYPOINT ["./entrypoint.sh"]
