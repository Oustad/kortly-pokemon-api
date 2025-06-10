# Pokemon Card Scanner 🎴

A production-ready Pokemon card scanner powered by Google Gemini AI and the Pokemon TCG API. Accurately identify Pokemon cards from photos with sub-2-second processing and costs under $0.005 per scan.

## ✨ Features

- **🤖 AI-Powered Identification**: Google Gemini 2.5 Flash for accurate card recognition
- **🎯 TCG Database Integration**: Comprehensive Pokemon card database matching
- **📱 Mobile Camera Support**: Direct photo capture on mobile devices with HEIC support
- **⚡ Lightning Fast**: Sub-2-second processing with optimized image handling
- **💰 Cost Effective**: ~$0.003-0.005 per scan with real-time cost tracking
- **🔧 Production Ready**: Full observability, monitoring, and deployment support
- **🛡️ Enterprise Security**: Rate limiting, security headers, and error notifications
- **📊 Comprehensive Metrics**: Performance monitoring with Prometheus support

## 🚀 Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Google API key with Gemini API enabled

### Installation

1. **Clone and setup**
   ```bash
   git clone <repository-url>
   cd pokemon-card-scanner
   uv sync
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env and add your GOOGLE_API_KEY
   ```

3. **Run the application**
   ```bash
   uv run python -m src.scanner.main
   ```

4. **Access the scanner**
   - Web interface: http://localhost:8000
   - API docs: http://localhost:8000/docs
   - Health check: http://localhost:8000/api/v1/health

## 🔧 Configuration

### Essential Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GOOGLE_API_KEY` | Google API key for Gemini | Yes |
| `POKEMON_TCG_API_KEY` | Pokemon TCG API key for higher rate limits | No |
| `ENVIRONMENT` | Environment mode (development/production) | No |
| `DEBUG` | Enable debug mode | No |

For complete configuration options, see [.env.example](.env.example).

### Getting API Keys

#### Google API Key (Required)
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable the Generative AI API
4. Create credentials → API Key
5. Restrict the key to Generative AI API

#### Pokemon TCG API Key (Optional)
1. Visit [Pokemon TCG Developer Portal](https://dev.pokemontcg.io/)
2. Sign up for a free account
3. Get your API key for higher rate limits (1000+ requests/hour vs 100/hour)

## 📡 API Usage

### Main Endpoints

- **POST** `/api/v1/scan` - Scan a Pokemon card image
- **GET** `/api/v1/health` - Service health status
- **GET** `/api/v1/metrics` - Performance metrics (if enabled)
- **GET** `/docs` - Interactive API documentation

### Example Scan Request

```bash
curl -X POST "http://localhost:8000/api/v1/scan" \
  -H "Content-Type: application/json" \
  -d '{
    "image": "base64_encoded_image_data",
    "filename": "card.jpg",
    "options": {
      "optimize_for_speed": true,
      "include_cost_tracking": true
    }
  }'
```

For detailed API documentation, visit `/docs` when the application is running.

## 🚀 Deployment

### Quick Docker Setup

```bash
# Build and run with Docker
docker build -t pokemon-card-scanner .
docker run -p 8000:8000 -e GOOGLE_API_KEY=your_key_here pokemon-card-scanner
```

### Docker Compose

```bash
# Copy environment file
cp .env.example .env
# Edit .env with your API key

# Start with Docker Compose
docker-compose up -d
```

### Production Deployment

For comprehensive deployment instructions including:
- Kubernetes deployment
- Google Cloud Platform (Cloud Run, GKE)
- AWS deployment (ECS, EKS)
- Production configuration
- Monitoring and observability

See **[DEPLOYMENT.md](DEPLOYMENT.md)** for detailed guides.

## 🏗️ Architecture

```
┌─────────────────┐    ┌──────────────┐    ┌─────────────────┐
│   Web Interface │───▶│  FastAPI     │───▶│  Gemini 2.5     │
│ Mobile Camera + │    │  Application │    │  Flash API      │
│  File Upload    │    │              │    └─────────────────┘
└─────────────────┘    │              │    ┌─────────────────┐
                       │              │───▶│  Pokemon TCG    │
                       │              │    │  Database       │
                       └──────────────┘    └─────────────────┘
```

### Key Components

- **Image Processor**: Multi-format support (HEIC/JPEG/PNG) with optimization
- **Gemini Service**: AI-powered card identification with structured output
- **TCG Client**: Pokemon card database integration with fuzzy matching
- **Metrics Service**: Real-time performance monitoring and cost tracking
- **Security Middleware**: Rate limiting, security headers, error notifications

## 📊 Performance & Features

| Metric | Value |
|--------|-------|
| Processing Time | 800-1500ms |
| Cost per Scan | $0.003-0.005 |
| Accuracy | >95% for clear images |
| Supported Formats | JPEG, PNG, HEIC, WebP |
| Mobile Camera | ✅ Direct capture |
| Rate Limiting | ✅ Configurable |
| Monitoring | ✅ Prometheus metrics |
| Error Notifications | ✅ Slack/Discord webhooks |

## 🧪 Testing

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src

# Manual testing
uv run python -m src.scanner.main
# Open http://localhost:8000 and upload a card image
```

## 🛠️ Development

### Project Structure

```
pokemon-card-scanner/
├── src/scanner/             # Main application
│   ├── main.py             # FastAPI app with middleware
│   ├── config.py           # Configuration management
│   ├── routes/             # API endpoints
│   ├── services/           # Core business logic
│   ├── middleware/         # Security and rate limiting
│   └── models/             # Data schemas
├── web/                    # Frontend (HTML/CSS/JS)
├── k8s/                    # Kubernetes manifests
├── tests/                  # Test suite
└── DEPLOYMENT.md           # Comprehensive deployment guide
```

### Code Quality

```bash
# Format and lint
uv run black src tests
uv run ruff check src tests
uv run mypy src
```

## 🐛 Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| **Gemini API Error** | Verify `GOOGLE_API_KEY` is set and Generative AI API is enabled |
| **Configuration Error** | Check `.env` file exists and contains required variables |
| **HEIC Not Supported** | Ensure `pillow-heif` is installed (included in dependencies) |
| **Rate Limit Exceeded** | Add `POKEMON_TCG_API_KEY` for higher rate limits |
| **Memory Issues** | Images are auto-resized to 1024px max dimension |

### Monitoring

- **Health Check**: `GET /api/v1/health`
- **Metrics**: `GET /api/v1/metrics` (if enabled)
- **Logs**: Structured JSON logging with request tracing
- **Costs**: Real-time API cost tracking in responses

## 📈 Cost Estimate

| Usage | Monthly Cost |
|-------|-------------|
| 1,000 scans | ~$3 |
| 10,000 scans | ~$30 |
| 100,000 scans | ~$300 |

*Based on current Google Gemini pricing (~$0.003 per scan)*

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Add tests for new functionality
4. Ensure all tests pass (`uv run pytest`)
5. Submit a pull request

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🔗 Links

- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Comprehensive deployment guide
- **[.env.example](.env.example)** - Complete configuration reference
- [Google Gemini API](https://ai.google.dev/) - AI service documentation
- [Pokemon TCG API](https://pokemontcg.io/) - Card database documentation