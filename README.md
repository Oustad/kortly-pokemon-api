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
- **💰 Cost Effective**: ~$0.003-0.005 per scan with real-time cost tracking
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

### 🛠️ Core Endpoints

#### POST `/api/v1/scan` - Scan Pokemon Card

**Request:**
```json
{
  "image": "base64_encoded_image_data",
  "filename": "card.jpg"
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
    "tcg_api": true
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

**Invalid Image Format:**
```json
{
  "error": "unsupported_format",
  "message": "Unsupported image format. Supported: JPEG, PNG, HEIC, WebP",
  "details": {
    "provided_format": "gif"
  }
}
```

**Invalid Image Data:**
```json
{
  "error": "invalid_image",
  "message": "Invalid or corrupted image data",
  "details": {
    "issue": "Unable to decode base64 image data"
  }
}
```

**Non-TCG Card:**
```json
{
  "error": "non_tcg_card",
  "message": "This appears to be a Pokemon-related item but not an official TCG card. Please scan an official Pokemon Trading Card Game card.",
  "details": {
    "detected_type": "sticker or collectible"
  }
}
```

**Non-Pokemon Card:**
```json
{
  "error": "non_pokemon_card",
  "message": "This appears to be a Magic: The Gathering card, not a Pokemon card.",
  "details": {
    "detected_type": "Magic: The Gathering card"
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

#### 404 Not Found - No Match Found
```json
{
  "error": "no_card_found",
  "message": "No matching Pokemon card found in our database",
  "details": {
    "attempted_search": {
      "name": "Pikachu",
      "set": "Base Set",
      "number": "25"
    }
  }
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

**Card Back Detection:**
```json
{
  "error": "card_back_detected",
  "message": "This appears to be the back of a Pokemon card. Please take a picture of the front side for identification.",
  "details": {
    "card_side": "back",
    "suggestion": "Flip the card over and photograph the front side"
  }
}
```

**Poor Image Quality:**
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
  "error": "internal_error",
  "message": "An unexpected error occurred during processing",
  "details": {
    "context": "processing"
  }
}
```

#### 502 Bad Gateway - AI Service Error
```json
{
  "error": "ai_service_error",
  "message": "AI vision service is temporarily unavailable",
  "details": {
    "service": "gemini",
    "original_error": "QUOTA_EXCEEDED"
  }
}
```

#### 503 Service Unavailable - Database Error
```json
{
  "error": "database_error",
  "message": "Card database service is temporarily unavailable",
  "details": {
    "service": "tcg"
  }
}
```

#### 504 Gateway Timeout - Processing Timeout
```json
{
  "error": "timeout_error",
  "message": "Processing timeout exceeded (60s). Please try again with a simpler image.",
  "details": {
    "timeout_seconds": 60
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


```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/unit/services/test_gemini_service.py

# Run tests with verbose output
uv run pytest -v

```


### Accuracy Testing

Test the scanner's accuracy against Pokemon card images:

```bash
# Test with image directory
uv run simple_accuracy_tester.py --image-dir /path/to/card/images

# Generate detailed report
uv run simple_accuracy_tester.py --output-file accuracy_report.json
```

### Webhook Testing

Test error notification webhooks locally:

1. **Start the fake webhook server:**
   ```bash
   uv run fake_slack_webhook.py
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
   uv run test_webhook.py
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

### 🔐 Authentication

When deployed to Google Cloud Run, the service requires **Google Cloud identity tokens** for authentication:

```bash
# Get identity token (from another Cloud service)
TOKEN=$(gcloud auth print-identity-token --audiences="https://your-service-url")

# Use in requests
curl -H "Authorization: Bearer $TOKEN" \
  https://your-service-url/api/v1/health
```

**Note:** This authentication is only required for Cloud Run deployment. Local development and Docker deployments do not require authentication.

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

## 🔗 Additional Resources

- **[Pokemon TCG API Documentation](https://pokemontcg.io/)** - Card database API reference
- **[Google Gemini API Documentation](https://ai.google.dev/)** - AI service documentation
- **[Google Cloud Run Documentation](https://cloud.google.com/run/docs)** - Deployment platform guide
- **[FastAPI Documentation](https://fastapi.tiangolo.com/)** - Web framework reference
