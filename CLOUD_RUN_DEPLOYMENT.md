# Pokemon Card Scanner - Cloud Run Deployment Guide

This guide walks you through deploying the Pokemon Card Scanner to Google Cloud Run with HTTP Basic Authentication for testing purposes.

## 🚀 Quick Start

### Prerequisites

1. **Google Cloud Project** with billing enabled
2. **gcloud CLI** installed and authenticated
3. **Docker** installed
4. **Required API Keys**:
   - Google API Key (for Gemini)
   - Pokemon TCG API Key (optional)

### One-Click Deployment

```bash
# Set your project ID
export GOOGLE_CLOUD_PROJECT="your-project-id"

# Set your API keys
export GOOGLE_API_KEY="your-gemini-api-key"
export POKEMON_TCG_API_KEY="your-tcg-api-key"  # Optional

# Deploy! (automatically handles Docker issues)
./deploy-to-cloud-run.sh

# Or force Cloud Build if you have Docker networking issues:
./deploy-to-cloud-run.sh --use-cloud-build
```

## 📋 Detailed Setup

### 1. Install Prerequisites

```bash
# Install gcloud CLI (if not already installed)
curl https://sdk.cloud.google.com | bash
gcloud init

# Install Docker (if not already installed)
# Follow instructions at: https://docs.docker.com/get-docker/
```

### 2. Set Up Environment Variables

```bash
# Required
export GOOGLE_CLOUD_PROJECT="your-project-id"
export GOOGLE_API_KEY="your-gemini-api-key"

# Optional
export POKEMON_TCG_API_KEY="your-tcg-api-key"
export CLOUD_RUN_REGION="us-central1"  # Default: us-central1
export CLOUD_RUN_SERVICE="pokemon-scanner-test"  # Default: pokemon-scanner-test
export ARTIFACT_REGISTRY_REPO="pokemon-scanner"  # Default: pokemon-scanner
```

### 3. Deploy

```bash
./deploy-to-cloud-run.sh
```

The script will:
- ✅ Check prerequisites
- ✅ Enable required Google Cloud APIs
- ✅ Create Artifact Registry repository
- ✅ Set up secrets in Secret Manager
- ✅ Build and push Docker image
- ✅ Deploy to Cloud Run

## 🔐 Authentication

The deployment includes HTTP Basic Authentication:

- **Username**: `test`
- **Password**: `pokemon123`

Users will be prompted for these credentials when accessing the application.

## 🌐 Accessing Your Deployment

After deployment, you'll get a URL like:
```
https://pokemon-scanner-test-abc123-uc.a.run.app
```

When you visit this URL:
1. Your browser will prompt for username/password
2. Enter the test credentials above
3. You'll have full access to the Pokemon Card Scanner

## ⚙️ Configuration

### Environment Variables

The deployment sets these environment variables:

```bash
ENVIRONMENT=test
DEBUG=false
LOG_LEVEL=INFO
SERVE_STATIC_FILES=true
ENABLE_API_DOCS=true
GEMINI_MODEL=models/gemini-2.0-flash
```

### Resource Limits

- **Memory**: 1 GB
- **CPU**: 1 vCPU
- **Timeout**: 300 seconds
- **Concurrency**: 10 requests per instance
- **Auto-scaling**: 0-3 instances

### Rate Limiting

- **API endpoints**: 30 requests/minute per IP
- **General requests**: 60 requests/minute per IP

## 🔧 Manual Deployment Steps

If you prefer manual deployment:

### 1. Build and Push Image

```bash
# Configure Docker for Artifact Registry
gcloud auth configure-docker us-central1-docker.pkg.dev

# Build image
docker build -f Dockerfile.cloudrun -t us-central1-docker.pkg.dev/$PROJECT_ID/pokemon-scanner/pokemon-card-scanner:latest .

# Push image
docker push us-central1-docker.pkg.dev/$PROJECT_ID/pokemon-scanner/pokemon-card-scanner:latest
```

### 2. Create Secrets

```bash
# Create secrets in Secret Manager
echo "$GOOGLE_API_KEY" | gcloud secrets create GOOGLE_API_KEY --data-file=-
echo "$POKEMON_TCG_API_KEY" | gcloud secrets create POKEMON_TCG_API_KEY --data-file=-
```

### 3. Deploy to Cloud Run

```bash
gcloud run deploy pokemon-scanner-test \
  --image=us-central1-docker.pkg.dev/$PROJECT_ID/pokemon-scanner/pokemon-card-scanner:latest \
  --platform=managed \
  --region=us-central1 \
  --allow-unauthenticated \
  --port=80 \
  --memory=1Gi \
  --cpu=1 \
  --timeout=300 \
  --concurrency=10 \
  --min-instances=0 \
  --max-instances=3 \
  --set-env-vars="ENVIRONMENT=test,DEBUG=false,LOG_LEVEL=INFO,SERVE_STATIC_FILES=true,ENABLE_API_DOCS=true" \
  --set-secrets="GOOGLE_API_KEY=GOOGLE_API_KEY:latest,POKEMON_TCG_API_KEY=POKEMON_TCG_API_KEY:latest"
```

## 🚨 Automated Deployments with Cloud Build

For continuous deployment, set up Cloud Build:

### 1. Connect Repository

```bash
# Connect your GitHub repository to Cloud Build
gcloud builds triggers create github \
  --repo-name=pokemon-card-scanner \
  --repo-owner=your-github-username \
  --branch-pattern="^main$" \
  --build-config=cloudbuild.yaml
```

### 2. Grant Cloud Build Permissions

```bash
# Get the Cloud Build service account
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
CLOUD_BUILD_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"

# Grant required roles
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${CLOUD_BUILD_SA}" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${CLOUD_BUILD_SA}" \
  --role="roles/secretmanager.secretAccessor"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:${CLOUD_BUILD_SA}" \
  --role="roles/artifactregistry.writer"
```

Now every push to the `main` branch will trigger an automatic deployment!

## 💰 Cost Optimization

For testing, this setup is very cost-effective:

- **Cloud Run**: Pay only when requests are processed
- **Artifact Registry**: ~$0.10/GB/month for image storage
- **Secret Manager**: $0.06 per 10,000 secret access operations
- **Estimated monthly cost**: <$5 for light testing usage

### Cost-Saving Tips

1. **Set min-instances to 0** (already configured)
2. **Use smaller memory/CPU** if performance allows
3. **Delete unused image versions** in Artifact Registry
4. **Set up budget alerts** in Google Cloud Console

## 🛠️ Troubleshooting

### Common Issues

**Build fails with "permission denied"**
```bash
# Ensure Docker is running and you're authenticated
docker info
gcloud auth list
```

**Deployment fails with "secrets not found"**
```bash
# Check if secrets exist
gcloud secrets list
# Recreate if missing
echo "$GOOGLE_API_KEY" | gcloud secrets create GOOGLE_API_KEY --data-file=-
```

**Authentication not working**
- Check that `.htpasswd` file was correctly included in the image
- Verify nginx configuration is using the correct auth file path

**Docker networking issues** (like "failed to set up container networking")
```bash
# Option 1: Use Cloud Build instead (recommended)
./deploy-to-cloud-run.sh --use-cloud-build

# Option 2: Try restarting Docker
sudo systemctl restart docker
docker system prune -f

# Option 3: WSL2 specific fix
sudo service docker stop && sudo service docker start
```

**Service not responding**
```bash
# Check Cloud Run logs
gcloud run logs tail pokemon-scanner-test --region=us-central1
```

### Debug Deployment

```bash
# Test the container locally
docker run -p 8080:80 \
  -e GOOGLE_API_KEY="$GOOGLE_API_KEY" \
  us-central1-docker.pkg.dev/$PROJECT_ID/pokemon-scanner/pokemon-card-scanner:latest

# Access at http://localhost:8080
```

## 🔄 Updates and Maintenance

### Update the Application

```bash
# Redeploy with latest changes
./deploy-to-cloud-run.sh
```

### Change Authentication

To update the username/password:

1. Generate new `.htpasswd` entry:
   ```bash
   htpasswd -n username
   ```

2. Update `.htpasswd` file and redeploy

### Monitor the Service

```bash
# View logs
gcloud run logs tail pokemon-scanner-test --region=us-central1

# Check service status
gcloud run services describe pokemon-scanner-test --region=us-central1
```

## 🔒 Security Notes

- This setup uses HTTP Basic Auth which is suitable for testing
- For production, consider:
  - Google Identity-Aware Proxy (IAP)
  - OAuth 2.0 / OpenID Connect
  - API keys for API access
  - SSL/TLS certificates

## 📞 Support

If you encounter issues:

1. Check the [Troubleshooting](#troubleshooting) section
2. Review Cloud Run logs for error details
3. Ensure all prerequisites are properly installed
4. Verify environment variables are set correctly

---

**Happy testing!** 🎴✨