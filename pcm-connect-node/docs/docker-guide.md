# Docker Deployment Guide

This guide covers building and running the PCM/FHIR Adapter using Docker and Docker Compose.

## Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- Certificate bundle extracted to `secrets/` directory

## Quick Start

### 1. Build the Image

```bash
docker compose build
```

Expected output:
```
[+] Building 45.2s (16/16) FINISHED
 => [internal] load build definition from Dockerfile
 => => transferring dockerfile: 1.2kB
 => [internal] load .dockerignore
 => [builder 1/6] FROM docker.io/library/node:20-alpine
 => [builder 2/6] WORKDIR /app
 => [builder 3/6] COPY package*.json ./
 => [builder 4/6] RUN npm ci
 => [builder 5/6] COPY src ./src
 => [builder 6/6] RUN npm run build
 => [stage-1 1/4] COPY package*.json ./
 => [stage-1 2/4] RUN npm ci --omit=dev
 => [stage-1 3/4] COPY --from=builder /app/dist ./dist
 => [stage-1 4/4] RUN addgroup -g 1001 -S nodejs && adduser -S nodejs -u 1001
 => exporting to image
 => => exporting layers
 => => writing image sha256:abc123...
 => => naming to docker.io/library/pcm-project-pcm-adapter
```

### 2. Start the Service

```bash
docker compose up
```

Or run in detached mode:
```bash
docker compose up -d
```

### 3. View Logs

```bash
# Follow logs
docker compose logs -f

# View specific service logs
docker compose logs -f pcm-adapter
```

Expected startup logs:
```
pcm-adapter  | [Nest] 1  - LOG [InstanceLoader] ConfigModule dependencies initialized
pcm-adapter  | [Nest] 1  - LOG [ConfigValidationService] Configuration validation passed
pcm-adapter  | [Nest] 1  - LOG [InternalJwtService] Internal JWT service initialized
pcm-adapter  | [Nest] 1  - LOG [IdReplacementService] ID Replacement running in MOCK mode
pcm-adapter  | [Nest] 1  - LOG [FhirForwardService] FHIR Forwarding running in MOCK mode
pcm-adapter  | [Nest] 1  - WARN [PcmIntrospectionService] PCM Introspection running in MOCK mode
pcm-adapter  | PCM/FHIR Data Source Adapter listening on port 3009
```

### 4. Test the Endpoints

```bash
# Health check
curl http://localhost:3009/health

# Ready check
curl http://localhost:3009/ready

# FHIR query (mock mode)
curl -H "Authorization: Bearer test-token" \
  "http://localhost:3009/fhir/Observation?code=test"
```

### 5. Stop the Service

```bash
# Stop containers
docker compose down

# Stop and remove volumes
docker compose down -v
```

## Configuration

### Environment Variables

The service reads configuration from `.env` file via `docker-compose.yml`:

```yaml
env_file:
  - .env
```

Ensure your `.env` file is configured before starting:

```bash
cp .env.example .env
# Edit .env with your settings
```

### Mounted Volumes

Certificates are mounted read-only from host:

```yaml
volumes:
  - ./secrets:/app/secrets:ro
```

**Before starting**, ensure certificates exist:

```bash
ls -la secrets/connectathon/custom/
# Should show .crt and .key files
```

## Dockerfile Overview

The project uses a multi-stage build for efficiency:

### Stage 1: Builder
- Base: `node:20-alpine`
- Installs all dependencies (including dev)
- Compiles TypeScript to JavaScript

### Stage 2: Production
- Base: `node:20-alpine`
- Installs production dependencies only
- Copies compiled code from builder
- Runs as non-root user (`nodejs:nodejs`)
- Includes health check

**Image size**: ~200MB (optimized with Alpine Linux)

## Health Check

Docker health check runs every 30 seconds:

```dockerfile
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD node -e "require('http').get('http://localhost:${PORT:-3009}/health', ...)"
```

View health status:
```bash
docker compose ps
# Shows "healthy" or "unhealthy" status
```

## Troubleshooting

### Container Won't Start

```bash
# View full logs
docker compose logs pcm-adapter

# Check container status
docker compose ps

# Inspect container
docker compose exec pcm-adapter sh
```

Common issues:
1. **Missing certificates**: Ensure `secrets/` directory exists and contains required files
2. **Port conflict**: Check if port 3009 is already in use
3. **Invalid .env**: Verify environment variables are correctly formatted

### Rebuild Without Cache

```bash
docker compose build --no-cache
```

### Access Container Shell

```bash
# While container is running
docker compose exec pcm-adapter sh

# Check mounted secrets
ls -la /app/secrets

# View environment
env | grep PCM
```

### Debug Health Check Failures

```bash
# Check health check command manually
docker compose exec pcm-adapter sh -c 'wget --quiet --tries=1 --spider http://localhost:3009/health'

# Or test with curl
docker compose exec pcm-adapter sh -c 'wget -O- http://localhost:3009/health'
```

### View Build Progress

```bash
# Build with progress output
docker compose build --progress=plain
```

## Production Considerations

### Security

1. **Use secrets management**: Don't rely on mounted files in production
   ```yaml
   secrets:
     pcm_cert:
       external: true
     pcm_key:
       external: true
   ```

2. **Run as non-root**: Already configured in Dockerfile
   ```dockerfile
   USER nodejs
   ```

3. **Read-only filesystem**: Consider adding to compose:
   ```yaml
   read_only: true
   tmpfs:
     - /tmp
   ```

### Resource Limits

Add resource constraints:

```yaml
services:
  pcm-adapter:
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 512M
        reservations:
          cpus: '0.5'
          memory: 256M
```

### Restart Policy

Already configured for development:
```yaml
restart: unless-stopped
```

For production, consider:
```yaml
restart: on-failure:3
```

### Logging

For production, configure log driver:

```yaml
services:
  pcm-adapter:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

Or use centralized logging:
```yaml
logging:
  driver: "syslog"
  options:
    syslog-address: "tcp://logs.example.com:514"
```

## Alternative: Docker Run (Without Compose)

If not using Docker Compose:

```bash
# Build
docker build -t pcm-adapter:latest .

# Run
docker run -d \
  --name pcm-adapter \
  -p 3009:3009 \
  --env-file .env \
  -v $(pwd)/secrets:/app/secrets:ro \
  pcm-adapter:latest

# View logs
docker logs -f pcm-adapter

# Stop
docker stop pcm-adapter
docker rm pcm-adapter
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Build Docker Image

on: [push]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Build Docker image
        run: docker build -t pcm-adapter:${{ github.sha }} .
      
      - name: Test image
        run: |
          docker run -d --name test-adapter \
            -e PCM_INTROSPECTION_MODE=mock \
            -e FHIR_FORWARDING_MODE=mock \
            -e ID_REPLACEMENT_MODE=mock \
            -e FHIR_BASE_URL=http://mock \
            -e JWT_AUDIENCE=http://mock \
            pcm-adapter:${{ github.sha }}
          
          sleep 5
          docker exec test-adapter wget -O- http://localhost:3009/health
          docker stop test-adapter
```

## Additional Commands

```bash
# List images
docker images | grep pcm-adapter

# Remove old images
docker image prune -f

# View image layers
docker history pcm-project-pcm-adapter

# Export image
docker save pcm-project-pcm-adapter:latest | gzip > pcm-adapter.tar.gz

# Import image
docker load < pcm-adapter.tar.gz
```

## Support

For Docker-specific issues, check:
1. Docker Engine logs: `journalctl -u docker`
2. Container logs: `docker compose logs`
3. Build logs: `docker compose build --progress=plain`
