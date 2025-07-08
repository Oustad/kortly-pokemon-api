# Pokemon Card Scanner 🎴

## TL;DR

**AI-powered internal microservice** that identifies Pokemon cards from photos in under 2 seconds for less than $0.005 per scan. Built with Google Gemini AI and Pokemon TCG API, designed for secure internal deployment on Google Cloud Run.

**Quick Start:**
```bash
# Local development
git clone <repo> && cd pokemon-card-scanner
uv sync && cp .env.example .env  # Add your GOOGLE_API_KEY and POKEMON_TCG_API_KEY
uv run python -m src.scanner.main

# Docker deployment
docker-compose up --build

# Google Cloud Run (internal only)
./deployment/cloud-run/deploy.sh
```

---

## 📋 Table of Contents

- [Overview](#overview)
- [API Documentation](#api-documentation)
- [Local Development](#local-development)
- [Testing](#testing)
- [Docker Deployment](#docker-deployment)
- [Google Cloud Run Deployment](#google-cloud-run-deployment)
- [Webhook Setup](#webhook-setup)
- [Configuration Reference](#configuration-reference)
- [Troubleshooting](#troubleshooting)

---

## 🎯 Overview

The Pokemon Card Scanner is a production-ready **internal microservice** that uses Google Gemini AI to identify Pokemon cards from photos. It's designed for secure deployment within your infrastructure, providing accurate card identification for applications like inventory management, collection tracking, or marketplace integration.

### ✨ Key Features

- **🤖 AI-Powered Identification**: Google Gemini 2.0 Flash for accurate card recognition
- **🎯 TCG Database Integration**: Comprehensive Pokemon card database matching with 95%+ accuracy
- **📱 Multi-Format Support**: JPEG, PNG, HEIC, WebP with automatic optimization
- **⚡ Lightning Fast**: Sub-2-second processing with optimized image handling
- **💰 Cost Effective**: ~$0.003-0.005 per scan with real-time cost tracking
- **🔒 Secure Internal Service**: No public internet access, identity-based authentication
- **📊 Comprehensive Monitoring**: Health checks, metrics, and error notifications
- **🛡️ Production Ready**: Rate limiting, security headers, and webhook notifications

### 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────┐    ┌─────────────────┐
│  Client Service │───▶│  Pokemon     │───▶│  Google Gemini  │
│ (Authenticated) │    │  Scanner API │    │  2.0 Flash      │
└─────────────────┘    │ (Internal)   │    └─────────────────┘
                       │              │    ┌─────────────────┐
                       │              │───▶│  Pokemon TCG    │
                       │              │    │  Database API   │
                       └──────────────┘    └─────────────────┘
```

### 📊 Performance Metrics

| Metric | Value |
|--------|-------|
| **Processing Time** | 800-1500ms |
| **Cost per Scan** | $0.003-0.005 USD |
| **Accuracy** | >95% for clear images |
| **Supported Formats** | JPEG, PNG, HEIC, WebP |
| **Rate Limiting** | 60 req/min (configurable) |
| **Concurrent Users** | 100 per instance |

---

## 📡 API Documentation

### 🔐 Authentication

The service requires **Google Cloud identity tokens** for authentication when deployed internally:

```bash
# Get identity token (from another Cloud service)
TOKEN=$(gcloud auth print-identity-token --audiences="https://your-service-url")

# Use in requests
curl -H "Authorization: Bearer $TOKEN" \
  https://your-service-url/api/v1/health
```

### 🛠️ Core Endpoints

#### POST `/api/v1/scan` - Scan Pokemon Card

**Request:**
```json
{
  "image": "base64_encoded_image_data",
  "filename": "card.jpg",
  "options": {
    "optimize_for_speed": true,
    "include_cost_tracking": true,
    "quality_threshold": 30
  }
}
```

**Successful Response (200):**
```json
{
  "name": "Charizard",
  "set_name": "Base Set",
  "number": "4/102",
  "hp": "120",
  "types": ["Fire"],
  "rarity": "Rare Holo",
  "image": "https://images.pokemontcg.io/base1/4_hires.png",
  "detected_language": "en",
  "match_score": 950,
  "market_prices": {
    "low": 299.99,
    "mid": 450.00,
    "high": 650.00,
    "market": 425.00
  },
  "quality_score": 87.5,
  "other_matches": [
    {
      "name": "Charizard",
      "set_name": "Base Set 2",
      "number": "4/130",
      "match_score": 780,
      "market_prices": {...}
    }
  ]
}
```

#### GET `/api/v1/health` - Health Check

**Response (200):**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "services": {
    "gemini": true,
    "tcg_api": true,
    "tcg_remaining_requests": 850
  }
}
```

#### GET `/api/v1/metrics` - Performance Metrics

**Response (200):**
```json
{
  "uptime_seconds": 3600,
  "requests": {
    "total": 1250,
    "successful": 1180,
    "failed": 70,
    "rate_per_second": 0.35,
    "error_rate_percent": 5.6
  },
  "response_times_ms": {
    "average": 1250.5,
    "minimum": 780.0,
    "maximum": 2100.0,
    "p50": 1200.0,
    "p95": 1800.0,
    "p99": 2000.0
  },
  "api_usage": {
    "gemini_calls": 1250,
    "tcg_calls": 1180,
    "total_cost_usd": 4.25,
    "avg_cost_per_request": 0.0034
  }
}
```

#### GET `/api/v1/info` - Service Information

**Response (200):**
```json
{
  "name": "Pokemon Card Scanner API",
  "version": "1.0.0",
  "description": "Internal microservice for AI-powered Pokemon card identification",
  "endpoints": {
    "scan": "/api/v1/scan",
    "health": "/api/v1/health",
    "metrics": "/api/v1/metrics"
  },
  "features": [
    "HEIC/JPEG/PNG image support",
    "Real-time cost tracking",
    "Quality assessment",
    "Market price lookup"
  ]
}
```

### ❌ Error Responses

#### 400 Bad Request - Invalid Input
```json
{
  "error": "validation_error",
  "message": "Invalid image format. Supported: JPEG, PNG, HEIC, WebP",
  "details": {
    "field": "image",
    "provided_format": "gif"
  }
}
```

#### 401 Unauthorized - Missing Authentication
```json
{
  "error": "authentication_required",
  "message": "Valid Google Cloud identity token required for internal service access"
}
```

#### 413 Payload Too Large - Image Size Limit
```json
{
  "error": "image_too_large",
  "message": "Image size exceeds 10MB limit",
  "details": {
    "max_size_mb": 10,
    "provided_size_mb": 15.2
  }
}
```

#### 422 Unprocessable Entity - Processing Failed
```json
{
  "error": "image_quality_too_low",
  "message": "Image quality insufficient for accurate identification",
  "details": {
    "quality_score": 15.5,
    "minimum_required": 30,
    "suggestions": [
      "Use better lighting",
      "Reduce glare and shadows",
      "Ensure card fills frame"
    ]
  }
}
```

#### 429 Too Many Requests - Rate Limited
```json
{
  "error": "rate_limit_exceeded",
  "message": "Request rate limit exceeded",
  "details": {
    "limit": "60 requests per minute",
    "retry_after": 45
  }
}
```

#### 500 Internal Server Error - Service Failure
```json
{
  "error": "service_unavailable",
  "message": "Gemini AI service temporarily unavailable",
  "details": {
    "service": "gemini",
    "error_code": "QUOTA_EXCEEDED"
  }
}
```

---

## 🚀 Local Development

### Prerequisites

- **Python 3.12+**
- **[uv](https://docs.astral.sh/uv/)** package manager
- **Google API key** with Gemini API enabled
- **Pokemon TCG API key** (optional, for higher rate limits)

### Setup

1. **Clone and install dependencies:**
   ```bash
   git clone <repository-url>
   cd pokemon-card-scanner
   uv sync
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env and add your API keys:
   # GOOGLE_API_KEY=your_google_api_key_here
   # POKEMON_TCG_API_KEY=your_pokemon_tcg_api_key_here (optional)
   ```

3. **Run the service:**
   ```bash
   uv run python -m src.scanner.main
   ```

4. **Access the service:**
   - Health check: http://localhost:8000/api/v1/health
   - API documentation: http://localhost:8000/docs (if enabled)
   - Service info: http://localhost:8000/api/v1/info

### Development Tools

```bash
# Code formatting
uv run black src tests

# Linting
uv run ruff check src tests

# Type checking
uv run mypy src

# Run all checks
uv run black src tests && uv run ruff check src tests && uv run mypy src
```

### Getting API Keys

#### Google API Key (Required)
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable the **Generative Language API**
4. Create credentials → **API Key**
5. Restrict the key to **Generative Language API**

#### Pokemon TCG API Key (Optional)
1. Visit [Pokemon TCG Developer Portal](https://dev.pokemontcg.io/)
2. Sign up for a free account
3. Get your API key for higher rate limits (1000+ requests/hour vs 100/hour)

---

## 🧪 Testing

### Unit Tests

The project includes a comprehensive test suite with 247+ tests covering all major components.

```bash
# Run all tests
uv run pytest

# Run with coverage report
uv run pytest --cov=src --cov-report=html

# Run specific test file
uv run pytest tests/unit/services/test_gemini_service.py

# Run tests with verbose output
uv run pytest -v

# Run only fast tests (skip slow integration tests)
uv run pytest -m "not slow"
```

**Coverage Reports:**
- Terminal: Displayed after test run
- HTML: Open `htmlcov/index.html` in browser

### Accuracy Testing

Test the scanner's accuracy against real Pokemon card images:

```bash
# Run accuracy tests on sample images
python simple_accuracy_tester.py

# Test specific card categories
python simple_accuracy_tester.py --card-type vintage
python simple_accuracy_tester.py --card-type modern
python simple_accuracy_tester.py --card-type japanese

# Test with custom image directory
python simple_accuracy_tester.py --image-dir /path/to/card/images

# Generate detailed report
python simple_accuracy_tester.py --output-file accuracy_report.json
```

### Webhook Testing

Test error notification webhooks locally:

1. **Start the fake webhook server:**
   ```bash
   python fake_slack_webhook.py
   ```
   This starts a local server on `http://localhost:3000` that mimics Slack's webhook API.

2. **Configure webhook in `.env`:**
   ```bash
   ERROR_WEBHOOK_URL=http://localhost:3000/webhook
   ERROR_WEBHOOK_ENABLED=true
   ERROR_WEBHOOK_MIN_LEVEL=ERROR
   ```

3. **Run webhook tests:**
   ```bash
   python test_webhook.py
   ```

4. **Manual testing:**
   Start the scanner and trigger errors by uploading invalid images or making malformed requests.

**Webhook Test Scenarios:**
- Invalid image data (malformed base64)
- Poor quality images (blurry, dark, damaged)
- Rate limiting (multiple rapid requests)
- Service errors (API failures)

---

## 🐳 Docker Deployment

### Local Docker Setup

**Option 1: Docker Build and Run**
```bash
# Build the image
docker build -t pokemon-scanner .

# Run with environment file
docker run -p 8000:8000 --env-file .env pokemon-scanner

# Run with individual environment variables
docker run -p 8000:8000 \
  -e GOOGLE_API_KEY="your_key_here" \
  -e POKEMON_TCG_API_KEY="your_key_here" \
  pokemon-scanner
```

**Option 2: Docker Compose (Recommended)**
```bash
# Copy and configure environment
cp .env.example .env
# Edit .env with your API keys

# Start with Docker Compose
docker-compose up --build

# Run in background
docker-compose up -d --build

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Docker Configuration

The Docker setup uses:
- **Multi-stage build** for smaller production images
- **Python 3.12 slim** base image
- **Non-root user** for security
- **Health checks** for container orchestration
- **Layer caching** for faster builds

**Resource Requirements:**
- **CPU**: 1-2 cores
- **Memory**: 2GB minimum, 4GB recommended
- **Storage**: 1GB for image and dependencies

---

## ☁️ Google Cloud Run Deployment

The service is configured as an **internal microservice** with no public internet access.

### Quick Deployment

```bash
# Set required environment variables
export GOOGLE_CLOUD_PROJECT="your-project-id"
export GOOGLE_API_KEY="your_google_api_key"
export POKEMON_TCG_API_KEY="your_pokemon_tcg_api_key"

# Deploy using automated script
./deployment/cloud-run/deploy.sh
```

### Manual Deployment

1. **Setup Google Cloud:**
   ```bash
   gcloud config set project YOUR_PROJECT_ID
   gcloud services enable cloudbuild.googleapis.com
   gcloud services enable run.googleapis.com
   gcloud services enable containerregistry.googleapis.com
   ```

2. **Build and push image:**
   ```bash
   docker build -t gcr.io/YOUR_PROJECT_ID/pokemon-card-scanner .
   docker push gcr.io/YOUR_PROJECT_ID/pokemon-card-scanner
   ```

3. **Deploy to Cloud Run:**
   ```bash
   gcloud run deploy pokemon-card-scanner \
     --image gcr.io/YOUR_PROJECT_ID/pokemon-card-scanner \
     --platform managed \
     --region us-central1 \
     --no-allow-unauthenticated \
     --ingress internal \
     --port 8000 \
     --cpu 2 \
     --memory 2Gi \
     --set-env-vars "GOOGLE_API_KEY=${GOOGLE_API_KEY}" \
     --set-env-vars "POKEMON_TCG_API_KEY=${POKEMON_TCG_API_KEY}"
   ```

### Internal Service Access

The deployed service can only be accessed by:

1. **Other Cloud Run services** in the same project
2. **Compute Engine VMs** with proper IAM roles
3. **Cloud Functions** in the same project
4. **App Engine** applications in the same project
5. **GKE clusters** with appropriate service accounts

### Required IAM Permissions

Grant access to calling services:
```bash
gcloud run services add-iam-policy-binding pokemon-card-scanner \
  --member="serviceAccount:YOUR_SERVICE@PROJECT.iam.gserviceaccount.com" \
  --role="roles/run.invoker" \
  --region=us-central1
```

### Calling from Another Service

**Python example:**
```python
import google.auth.transport.requests
import google.oauth2.id_token
import requests

# Get identity token
audience = "https://pokemon-card-scanner-abc123-uc.a.run.app"
auth_req = google.auth.transport.requests.Request()
id_token = google.oauth2.id_token.fetch_id_token(auth_req, audience)

# Make authenticated request
headers = {"Authorization": f"Bearer {id_token}"}
response = requests.post(f"{audience}/api/v1/scan", 
                        headers=headers, 
                        json={"image": image_b64, "filename": "card.jpg"})
```

**Bash example:**
```bash
# Get identity token
TOKEN=$(gcloud auth print-identity-token --audiences="https://your-service-url")

# Call the service
curl -H "Authorization: Bearer $TOKEN" \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"image":"'$IMAGE_B64'","filename":"card.jpg"}' \
  https://your-service-url/api/v1/scan
```

### Cloud Run Configuration

**Resource Allocation (Medium):**
- **CPU**: 2 vCPU
- **Memory**: 2Gi RAM
- **Concurrency**: 100 requests per instance
- **Min Instances**: 0 (cost optimization)
- **Max Instances**: 10 (scaling limit)
- **Request Timeout**: 60 seconds

---

## 🔔 Webhook Setup

Configure error notifications to be sent to Slack, Discord, or custom endpoints when errors occur.

### Slack Webhook Setup

1. **Create a Slack App:**
   - Go to [Slack API](https://api.slack.com/apps)
   - Create new app → "From scratch"
   - Choose workspace and app name

2. **Enable Incoming Webhooks:**
   - Go to "Incoming Webhooks" in your app settings
   - Activate incoming webhooks
   - "Add New Webhook to Workspace"
   - Choose channel and authorize

3. **Configure environment variables:**
   ```bash
   ERROR_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK
   ERROR_WEBHOOK_ENABLED=true
   ERROR_WEBHOOK_MIN_LEVEL=ERROR
   ERROR_WEBHOOK_INCLUDE_TRACEBACK=true
   ERROR_WEBHOOK_RATE_LIMIT=5
   ERROR_WEBHOOK_ENVIRONMENT_TAG=production
   ```

### Local Webhook Testing

For development and testing:

1. **Start fake webhook server:**
   ```bash
   python fake_slack_webhook.py
   ```

2. **Configure for local testing:**
   ```bash
   ERROR_WEBHOOK_URL=http://localhost:3000/webhook
   ERROR_WEBHOOK_ENABLED=true
   ERROR_WEBHOOK_MIN_LEVEL=ERROR
   ```

3. **Test webhook notifications:**
   ```bash
   python test_webhook.py
   ```

### Webhook Message Format

Error notifications include:
- **Timestamp** and **log level**
- **Service name** and **environment**
- **Error message** and **endpoint**
- **Request ID** for tracing
- **Context data** (status codes, processing time)
- **Stack trace** (if enabled)

**Example Slack message:**
```
🚨 [ERROR] Pokemon Card Scanner - production
📦 Service: pokemon-card-scanner
🔗 Endpoint: /api/v1/scan
💬 Message: Image quality too low for processing
📊 Context: {"status_code": 422, "quality_score": 15.5}
🕐 2025-07-08 20:30:45 UTC
```

### Custom Webhook Endpoints

The service can send webhooks to any HTTP endpoint that accepts POST requests:

```bash
ERROR_WEBHOOK_URL=https://your-custom-endpoint.com/alerts
ERROR_WEBHOOK_ENABLED=true
```

**Payload format:**
```json
{
  "text": "🚨 [ERROR] Pokemon Card Scanner Alert",
  "attachments": [
    {
      "color": "danger",
      "fields": [
        {"title": "Service", "value": "pokemon-card-scanner", "short": true},
        {"title": "Environment", "value": "production", "short": true},
        {"title": "Error", "value": "Image quality too low", "short": false}
      ],
      "timestamp": "2025-07-08T20:30:45.123Z"
    }
  ]
}
```

---

## ⚙️ Configuration Reference

### Required Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `GOOGLE_API_KEY` | Google Gemini API key | **Yes** | - |
| `POKEMON_TCG_API_KEY` | Pokemon TCG API key for higher rate limits | No | - |

### Server Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `HOST` | Server bind address | `0.0.0.0` |
| `PORT` | Server port | `8000` |
| `ENVIRONMENT` | Environment mode | `production` |
| `DEBUG` | Enable debug mode | `false` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `ENABLE_API_DOCS` | Enable /docs endpoint | `false` (prod) |

### AI Model Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `GEMINI_MODEL` | Gemini model name | `models/gemini-2.0-flash` |

### Security & Rate Limiting

| Variable | Description | Default |
|----------|-------------|---------|
| `CORS_ORIGINS` | Allowed CORS origins | `""` (internal service) |

### Error Webhook Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `ERROR_WEBHOOK_URL` | Webhook endpoint URL | - |
| `ERROR_WEBHOOK_ENABLED` | Enable error notifications | `false` |
| `ERROR_WEBHOOK_TIMEOUT` | Request timeout (seconds) | `10` |
| `ERROR_WEBHOOK_MIN_LEVEL` | Minimum log level | `ERROR` |
| `ERROR_WEBHOOK_INCLUDE_TRACEBACK` | Include stack traces | `true` |
| `ERROR_WEBHOOK_RATE_LIMIT` | Max requests per minute | `5` |
| `ERROR_WEBHOOK_ENVIRONMENT_TAG` | Environment identifier | `production` |

### Hardcoded Configuration

The following settings are hardcoded for stability:

**Gemini AI:**
- Max Tokens: 2000
- Temperature: 0.1 (consistent results)
- Max Retries: 3
- Timeout: 60 seconds

**Image Processing:**
- Max Dimension: 1024px
- JPEG Quality: 85%
- Max File Size: 10MB

**Rate Limiting:**
- Per Minute: 60 requests
- Burst: 20 requests

---

## 🐛 Troubleshooting

### Common Issues

#### Service Won't Start

**Error:** `Configuration error: GOOGLE_API_KEY is required`
```bash
# Solution: Set required environment variables
export GOOGLE_API_KEY="your_key_here"
# Or add to .env file
echo "GOOGLE_API_KEY=your_key_here" >> .env
```

**Error:** `Port 8000 already in use`
```bash
# Check what's using the port
lsof -i :8000

# Kill the process or use different port
export PORT=8080
```

#### Authentication Issues

**Error:** `Gemini API authentication failed`
```bash
# Verify API key is valid
curl -H "x-goog-api-key: $GOOGLE_API_KEY" \
  https://generativelanguage.googleapis.com/v1/models

# Check API is enabled
gcloud services list --enabled --filter="name:generativelanguage.googleapis.com"
```

**Error:** `401 Unauthorized` on internal service
```bash
# Check IAM permissions
gcloud run services get-iam-policy pokemon-card-scanner --region=us-central1

# Grant invoker role
gcloud run services add-iam-policy-binding pokemon-card-scanner \
  --member="serviceAccount:YOUR_SERVICE@PROJECT.iam.gserviceaccount.com" \
  --role="roles/run.invoker"
```

#### Processing Issues

**Error:** `Image quality too low for processing`
- Use better lighting when photographing cards
- Reduce glare and shadows
- Ensure card fills most of the frame
- Try different angles or backgrounds

**Error:** `Rate limit exceeded`
- Add `POKEMON_TCG_API_KEY` for higher limits
- Implement request queuing in your application
- Consider caching results for frequently scanned cards

#### Memory Issues

**Error:** `Memory limit exceeded` in Cloud Run
```bash
# Increase memory allocation
gcloud run services update pokemon-card-scanner \
  --memory 4Gi \
  --region us-central1
```

#### Container Issues

**Error:** Docker build fails
```bash
# Clear Docker cache
docker system prune -a

# Build with no cache
docker build --no-cache -t pokemon-scanner .
```

**Error:** Container exits immediately
```bash
# Check container logs
docker logs CONTAINER_ID

# Run interactively for debugging
docker run -it --entrypoint /bin/bash pokemon-scanner
```

### Debugging

#### Enable Debug Logging

```bash
# Local development
export DEBUG=true
export LOG_LEVEL=DEBUG

# Cloud Run
gcloud run services update pokemon-card-scanner \
  --set-env-vars "DEBUG=true,LOG_LEVEL=DEBUG"
```

#### View Logs

**Local:**
```bash
# Application logs are written to stdout
uv run python -m src.scanner.main

# Docker logs
docker logs CONTAINER_ID -f
```

**Cloud Run:**
```bash
# View recent logs
gcloud logs read --service=pokemon-card-scanner --region=us-central1

# Follow live logs
gcloud logs tail --service=pokemon-card-scanner --region=us-central1
```

#### Health Checks

```bash
# Local health check
curl http://localhost:8000/api/v1/health

# Internal service health check (requires auth)
TOKEN=$(gcloud auth print-identity-token --audiences="https://your-service-url")
curl -H "Authorization: Bearer $TOKEN" https://your-service-url/api/v1/health
```

#### Performance Monitoring

```bash
# Get performance metrics
curl -H "Authorization: Bearer $TOKEN" \
  https://your-service-url/api/v1/metrics

# Monitor processing times and error rates
# Set up alerts based on metrics thresholds
```

### Getting Help

1. **Check the logs** for detailed error messages
2. **Verify environment variables** are correctly set
3. **Test API keys** independently to ensure they work
4. **Check service health** endpoints for dependency status
5. **Review Cloud Run service** configuration and IAM permissions

---

## 🔗 Additional Resources

- **[Pokemon TCG API Documentation](https://pokemontcg.io/)** - Card database API reference
- **[Google Gemini API Documentation](https://ai.google.dev/)** - AI service documentation
- **[Google Cloud Run Documentation](https://cloud.google.com/run/docs)** - Deployment platform guide
- **[FastAPI Documentation](https://fastapi.tiangolo.com/)** - Web framework reference

---

*Last updated: 2025-07-08*