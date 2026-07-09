FROM python:3.12-alpine AS builder

RUN apk add --no-cache build-base libffi-dev openssl-dev \
    && addgroup -S appgroup && adduser -S appuser -G appgroup

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-alpine AS runtime

RUN addgroup -S appgroup && adduser -S appuser -G appgroup \
    && apk add --no-cache ca-certificates tini

COPY --from=builder /install /usr/local

USER appuser
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY --chown=appuser:appgroup src ./src
COPY --chown=appuser:appgroup config.yaml ./config.yaml

EXPOSE 8000

ENTRYPOINT ["/sbin/tini", "--"]
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
