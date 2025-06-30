#!/bin/bash

# Pokemon Card Scanner - Cloud Run Deployment Script
# This script deploys the Pokemon card scanner to Google Cloud Run with Basic Auth

set -euo pipefail

# Configuration
PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-}"
REGION="${CLOUD_RUN_REGION:-us-central1}"
SERVICE_NAME="${CLOUD_RUN_SERVICE:-pokemon-scanner-test}"
IMAGE_NAME="pokemon-card-scanner"
REPOSITORY="${ARTIFACT_REGISTRY_REPO:-pokemon-scanner}"
USE_CLOUD_BUILD=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --use-cloud-build)
            USE_CLOUD_BUILD=true
            shift
            ;;
        --help)
            echo "Usage: $0 [--use-cloud-build] [--help]"
            echo "  --use-cloud-build  Use Google Cloud Build instead of local Docker"
            echo "  --help             Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

echo_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

echo_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

echo_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check prerequisites
check_prerequisites() {
    echo_info "Checking prerequisites..."
    
    if ! command -v gcloud &> /dev/null; then
        echo_error "gcloud CLI is not installed. Please install it first."
        exit 1
    fi
    
    if ! command -v docker &> /dev/null && [[ "$USE_CLOUD_BUILD" == "false" ]]; then
        echo_warning "Docker is not installed. Will use Google Cloud Build instead."
        USE_CLOUD_BUILD=true
    fi
    
    if [[ -z "$PROJECT_ID" ]]; then
        echo_error "GOOGLE_CLOUD_PROJECT environment variable is not set."
        echo_info "Run: export GOOGLE_CLOUD_PROJECT=your-project-id"
        exit 1
    fi
    
    if [[ -z "$GOOGLE_API_KEY" ]]; then
        echo_warning "GOOGLE_API_KEY environment variable is not set."
        echo_info "Make sure to set this as a secret in Cloud Run."
    fi
    
    echo_success "Prerequisites check passed"
}

# Configure gcloud and enable APIs
setup_gcloud() {
    echo_info "Setting up Google Cloud..."
    
    gcloud config set project "$PROJECT_ID"
    
    echo_info "Enabling required APIs..."
    gcloud services enable \
        cloudbuild.googleapis.com \
        run.googleapis.com \
        artifactregistry.googleapis.com
    
    echo_success "Google Cloud setup complete"
}

# Create Artifact Registry repository if it doesn't exist
setup_artifact_registry() {
    echo_info "Setting up Artifact Registry..."
    
    if ! gcloud artifacts repositories describe "$REPOSITORY" --location="$REGION" &> /dev/null; then
        echo_info "Creating Artifact Registry repository..."
        gcloud artifacts repositories create "$REPOSITORY" \
            --repository-format=docker \
            --location="$REGION" \
            --description="Pokemon Card Scanner container images"
    else
        echo_info "Artifact Registry repository already exists"
    fi
    
    # Configure Docker to use gcloud as credential helper
    gcloud auth configure-docker "${REGION}-docker.pkg.dev"
    
    echo_success "Artifact Registry setup complete"
}

# Build with Google Cloud Build
build_with_cloud_build() {
    echo_info "Building Docker image with Google Cloud Build..."
    
    IMAGE_TAG="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${IMAGE_NAME}:latest"
    
    # Submit build to Cloud Build
    gcloud builds submit \
        --config=/dev/stdin \
        --substitutions="_REGION=${REGION},_REPOSITORY=${REPOSITORY},_IMAGE_NAME=${IMAGE_NAME}" \
        . <<EOF
steps:
  - name: 'gcr.io/cloud-builders/docker'
    args: 
      - 'build'
      - '-f'
      - 'Dockerfile.cloudrun'
      - '-t'
      - '\${_REGION}-docker.pkg.dev/\$PROJECT_ID/\${_REPOSITORY}/\${_IMAGE_NAME}:latest'
      - '.'
  - name: 'gcr.io/cloud-builders/docker'
    args:
      - 'push'
      - '\${_REGION}-docker.pkg.dev/\$PROJECT_ID/\${_REPOSITORY}/\${_IMAGE_NAME}:latest'
timeout: '1200s'
EOF
    
    echo_success "Image built and pushed with Cloud Build: $IMAGE_TAG"
}

# Build and push Docker image (with fallback to Cloud Build)
build_and_push() {
    IMAGE_TAG="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${IMAGE_NAME}:latest"
    
    if [[ "$USE_CLOUD_BUILD" == "true" ]]; then
        echo_info "Using Google Cloud Build (--use-cloud-build specified)..."
        build_with_cloud_build
        return
    fi
    
    echo_info "Attempting local Docker build..."
    
    # Try local Docker build first
    if docker build -f Dockerfile.cloudrun -t "$IMAGE_TAG" . 2>&1 | tee /tmp/docker_build.log; then
        echo_info "Pushing image to Artifact Registry..."
        if docker push "$IMAGE_TAG"; then
            echo_success "Image built and pushed locally: $IMAGE_TAG"
            return
        else
            echo_warning "Local push failed, falling back to Cloud Build..."
        fi
    else
        # Check if it's a networking error
        if grep -q "failed to set up container networking\|operation not supported\|network bridge" /tmp/docker_build.log; then
            echo_warning "Docker networking issue detected, falling back to Cloud Build..."
        else
            echo_warning "Local Docker build failed, falling back to Cloud Build..."
        fi
    fi
    
    # Fallback to Cloud Build
    echo_info "Retrying with Google Cloud Build..."
    build_with_cloud_build
    
    # Clean up log file
    rm -f /tmp/docker_build.log
}

# Deploy to Cloud Run
deploy_to_cloud_run() {
    echo_info "Deploying to Cloud Run..."
    
    IMAGE_TAG="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${IMAGE_NAME}:latest"
    
    gcloud run deploy "$SERVICE_NAME" \
        --image="$IMAGE_TAG" \
        --platform=managed \
        --region="$REGION" \
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
    
    # Get the service URL
    SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" --region="$REGION" --format="value(status.url)")
    
    echo_success "Deployment complete!"
    echo_info "Service URL: $SERVICE_URL"
    echo_info "Test credentials:"
    echo_info "  Username: test"
    echo_info "  Password: pokemon123"
}

# Create secrets if they don't exist
setup_secrets() {
    echo_info "Setting up secrets..."
    
    if [[ -n "${GOOGLE_API_KEY:-}" ]]; then
        echo "$GOOGLE_API_KEY" | gcloud secrets create GOOGLE_API_KEY --data-file=- || \
        echo "$GOOGLE_API_KEY" | gcloud secrets versions add GOOGLE_API_KEY --data-file=-
        echo_info "GOOGLE_API_KEY secret updated"
    fi
    
    if [[ -n "${POKEMON_TCG_API_KEY:-}" ]]; then
        echo "$POKEMON_TCG_API_KEY" | gcloud secrets create POKEMON_TCG_API_KEY --data-file=- || \
        echo "$POKEMON_TCG_API_KEY" | gcloud secrets versions add POKEMON_TCG_API_KEY --data-file=-
        echo_info "POKEMON_TCG_API_KEY secret updated"
    fi
    
    echo_success "Secrets setup complete"
}

# Main deployment flow
main() {
    echo_info "🚀 Starting Pokemon Card Scanner deployment to Cloud Run..."
    echo_info "Project: $PROJECT_ID"
    echo_info "Region: $REGION"
    echo_info "Service: $SERVICE_NAME"
    if [[ "$USE_CLOUD_BUILD" == "true" ]]; then
        echo_info "Build method: Google Cloud Build (forced)"
    else
        echo_info "Build method: Local Docker (with Cloud Build fallback)"
    fi
    echo ""
    
    check_prerequisites
    setup_gcloud
    setup_artifact_registry
    setup_secrets
    build_and_push
    deploy_to_cloud_run
    
    echo ""
    echo_success "🎉 Deployment completed successfully!"
    echo_info "Your Pokemon Card Scanner is now running on Cloud Run"
    echo_info "Access it at the URL above with the test credentials"
}

# Run main function
main "$@"