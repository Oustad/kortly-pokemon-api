#!/bin/bash

# Google Cloud Run Deployment Script for Pokemon Card Scanner
# Deploys with medium CPU/memory configuration

set -e

# Configuration
PROJECT_ID=${GOOGLE_CLOUD_PROJECT:-"your-project-id"}
SERVICE_NAME="pokemon-card-scanner"
REGION=${CLOUD_RUN_REGION:-"us-central1"}
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Deploying Pokemon Card Scanner to Google Cloud Run${NC}"

# Check required environment variables
if [ -z "$GOOGLE_API_KEY" ]; then
    echo -e "${RED}❌ Error: GOOGLE_API_KEY environment variable is required${NC}"
    exit 1
fi

if [ -z "$POKEMON_TCG_API_KEY" ]; then
    echo -e "${RED}❌ Error: POKEMON_TCG_API_KEY environment variable is required${NC}"
    exit 1
fi

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}❌ Error: gcloud CLI is not installed${NC}"
    echo "Please install it from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check if docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Error: Docker is not installed${NC}"
    exit 1
fi

# Set project
echo -e "${YELLOW}📋 Setting Google Cloud project: ${PROJECT_ID}${NC}"
gcloud config set project $PROJECT_ID

# Enable required APIs
echo -e "${YELLOW}🔧 Enabling required Google Cloud APIs...${NC}"
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com

# Build and push image
echo -e "${YELLOW}🔨 Building Docker image...${NC}"
docker build -t $IMAGE_NAME .

echo -e "${YELLOW}📤 Pushing image to Google Container Registry...${NC}"
docker push $IMAGE_NAME

# Deploy to Cloud Run (Internal microservice - no public access)
echo -e "${YELLOW}🚀 Deploying to Cloud Run (internal access only)...${NC}"
gcloud run deploy $SERVICE_NAME \
    --image $IMAGE_NAME \
    --platform managed \
    --region $REGION \
    --no-allow-unauthenticated \
    --ingress internal \
    --port 8000 \
    --cpu 2 \
    --memory 2Gi \
    --concurrency 100 \
    --max-instances 10 \
    --min-instances 0 \
    --timeout 60s \
    --set-env-vars "GOOGLE_API_KEY=${GOOGLE_API_KEY}" \
    --set-env-vars "POKEMON_TCG_API_KEY=${POKEMON_TCG_API_KEY}" \
    --set-env-vars "ENVIRONMENT=production" \
    --set-env-vars "LOG_LEVEL=INFO" \
    --set-env-vars "ENABLE_API_DOCS=false" \
    --set-env-vars "CORS_ORIGINS=" \
    --set-env-vars "ERROR_WEBHOOK_ENABLED=${ERROR_WEBHOOK_ENABLED:-false}" \
    --set-env-vars "ERROR_WEBHOOK_URL=${ERROR_WEBHOOK_URL:-}" \
    --labels app=pokemon-card-scanner,environment=production,access=internal

# Get the service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --platform managed --region $REGION --format 'value(status.url)')

echo -e "${GREEN}✅ Deployment completed successfully!${NC}"
echo -e "${GREEN}🔒 Internal Service URL: ${SERVICE_URL}${NC}"
echo -e "${YELLOW}⚠️  Note: Service is INTERNAL ONLY - not accessible from public internet${NC}"
echo -e "${GREEN}📊 Health Check: ${SERVICE_URL}/api/v1/health${NC}"
echo -e "${GREEN}📊 Metrics: ${SERVICE_URL}/api/v1/metrics${NC}"

echo -e "${YELLOW}🔧 To access this service, you need:${NC}"
echo -e "   • Another Cloud Run service in the same project"
echo -e "   • Compute Engine VM with proper IAM roles"
echo -e "   • Cloud Functions in the same project"
echo -e "   • VPC connector if calling from external GCP services"

echo -e "${YELLOW}📝 Required IAM permissions for calling services:${NC}"
echo -e "   • roles/run.invoker"

echo -e "${YELLOW}🧪 Testing deployment (requires internal access)...${NC}"
echo -e "${YELLOW}   Cannot test from this machine - service is internal only${NC}"
echo -e "${YELLOW}   Check deployment status with:${NC}"
echo -e "   gcloud run services describe ${SERVICE_NAME} --region=${REGION}"

echo -e "${GREEN}🔒 Pokemon Card Scanner microservice deployed securely (internal access only)${NC}"