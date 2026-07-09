FROM python:3.12-alpine

RUN addgroup -S appgroup && adduser -S appuser -G appgroup \
    && apk add --no-cache ca-certificates tini

USER appuser
WORKDIR /app
ENV PATH="/home/appuser/.local/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY --chown=appuser:appgroup requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

COPY --chown=appuser:appgroup app.py ./
COPY --chown=appuser:appgroup api ./api
COPY --chown=appuser:appgroup core ./core
COPY --chown=appuser:appgroup services ./services
COPY --chown=appuser:appgroup config.json ./config.json
COPY --chown=appuser:appgroup config.docker.json ./config.docker.json

EXPOSE 8000

ENTRYPOINT ["/sbin/tini", "--"]
CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
