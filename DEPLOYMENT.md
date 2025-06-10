# Pokemon Card Scanner - Deployment Guide

This guide provides comprehensive deployment instructions for the Pokemon Card Scanner across multiple platforms and environments.

## Table of Contents

1. [Quick Start (Local Development)](#quick-start-local-development)
2. [Docker Deployment](#docker-deployment)
3. [Docker Compose](#docker-compose)
4. [Kubernetes Deployment](#kubernetes-deployment)
5. [Google Cloud Platform](#google-cloud-platform)
6. [AWS Deployment](#aws-deployment)
7. [Production Considerations](#production-considerations)
8. [Configuration Reference](#configuration-reference)
9. [Troubleshooting](#troubleshooting)

## Quick Start (Local Development)

### Prerequisites
- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- Google Gemini API key

### Setup

1. **Clone and setup**:
   ```bash
   git clone <repository-url>
   cd pokemon-card-scanner
   cp .env.example .env
   ```

2. **Configure environment**:
   ```bash
   # Edit .env file
   GOOGLE_API_KEY=your-gemini-api-key-here
   ENVIRONMENT=development
   DEBUG=true
   ```

3. **Install dependencies**:
   ```bash
   # Using uv (recommended)
   uv sync

   # Or using pip
   pip install -e .
   ```

4. **Run the application**:
   ```bash
   # Using uv
   uv run python -m src.scanner.main

   # Or using installed package
   python -m src.scanner.main
   ```

5. **Access the application**:
   - Web interface: http://localhost:8000
   - API docs: http://localhost:8000/docs

## Docker Deployment

### Simple Docker Build

1. **Build the image**:
   ```bash
   docker build -t pokemon-card-scanner .
   ```

2. **Run the container**:
   ```bash
   docker run -d \
     --name pokemon-scanner \
     -p 8000:8000 \
     -e GOOGLE_API_KEY=your-api-key \
     -e ENVIRONMENT=production \
     pokemon-card-scanner
   ```

### Multi-stage Production Build

The Dockerfile includes optimizations for production:

- Multi-stage build to reduce image size
- Non-root user for security
- Health checks for container orchestration
- Optimized layer caching

**Build production image**:
```bash
docker build -t pokemon-card-scanner:prod \
  --target production .
```

### Docker Build Arguments

Customize the build with build args:

```bash
docker build \
  --build-arg PYTHON_VERSION=3.12 \
  --build-arg UV_VERSION=0.4.18 \
  -t pokemon-card-scanner .
```

## Docker Compose

### Basic Docker Compose

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  pokemon-scanner:
    build: .
    ports:
      - "8000:8000"
    environment:
      - GOOGLE_API_KEY=${GOOGLE_API_KEY}
      - ENVIRONMENT=production
      - DEBUG=false
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

**Deploy**:
```bash
export GOOGLE_API_KEY=your-api-key
docker-compose up -d
```

### Docker Compose with Nginx

For production with reverse proxy:

```yaml
version: '3.8'

services:
  pokemon-scanner:
    build: .
    environment:
      - GOOGLE_API_KEY=${GOOGLE_API_KEY}
      - ENVIRONMENT=production
      - HOST=0.0.0.0
      - PORT=8000
      - SERVE_STATIC_FILES=false
    restart: unless-stopped
    networks:
      - app-network

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
      - ./web:/usr/share/nginx/html:ro
    depends_on:
      - pokemon-scanner
    restart: unless-stopped
    networks:
      - app-network

networks:
  app-network:
    driver: bridge
```

### API-Only Deployment

For headless API-only deployment:

```yaml
version: '3.8'

services:
  pokemon-scanner-api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - GOOGLE_API_KEY=${GOOGLE_API_KEY}
      - ENVIRONMENT=production
      - SERVE_STATIC_FILES=false
      - ENABLE_API_DOCS=true
    restart: unless-stopped
```

## Kubernetes Deployment

### Basic Kubernetes Manifests

**Namespace**:
```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: pokemon-scanner
```

**Secret**:
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: pokemon-scanner-secrets
  namespace: pokemon-scanner
type: Opaque
stringData:
  GOOGLE_API_KEY: "your-api-key-here"
```

**ConfigMap**:
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: pokemon-scanner-config
  namespace: pokemon-scanner
data:
  ENVIRONMENT: "production"
  DEBUG: "false"
  LOG_LEVEL: "INFO"
  GEMINI_MODEL: "models/gemini-2.5-flash-preview-05-20"
  IMAGE_MAX_DIMENSION: "1024"
  CACHE_ENABLED: "true"
  RATE_LIMIT_PER_MINUTE: "60"
```

**Deployment**:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: pokemon-scanner
  namespace: pokemon-scanner
spec:
  replicas: 3
  selector:
    matchLabels:
      app: pokemon-scanner
  template:
    metadata:
      labels:
        app: pokemon-scanner
    spec:
      containers:
      - name: pokemon-scanner
        image: pokemon-card-scanner:latest
        ports:
        - containerPort: 8000
        env:
        - name: GOOGLE_API_KEY
          valueFrom:
            secretKeyRef:
              name: pokemon-scanner-secrets
              key: GOOGLE_API_KEY
        envFrom:
        - configMapRef:
            name: pokemon-scanner-config
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /api/v1/health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /api/v1/health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
```

**Service**:
```yaml
apiVersion: v1
kind: Service
metadata:
  name: pokemon-scanner-service
  namespace: pokemon-scanner
spec:
  selector:
    app: pokemon-scanner
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: ClusterIP
```

**Ingress**:
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: pokemon-scanner-ingress
  namespace: pokemon-scanner
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
  - hosts:
    - pokemon-scanner.yourdomain.com
    secretName: pokemon-scanner-tls
  rules:
  - host: pokemon-scanner.yourdomain.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: pokemon-scanner-service
            port:
              number: 80
```

**Deploy to Kubernetes**:
```bash
kubectl apply -f k8s/
```

### Horizontal Pod Autoscaler

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: pokemon-scanner-hpa
  namespace: pokemon-scanner
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: pokemon-scanner
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

## Google Cloud Platform

### Cloud Run (Serverless)

**Ideal for**: Low to medium traffic, cost optimization, minimal ops overhead.

1. **Build and push image**:
   ```bash
   # Enable required APIs
   gcloud services enable run.googleapis.com
   gcloud services enable cloudbuild.googleapis.com

   # Build and push to Container Registry
   gcloud builds submit --tag gcr.io/PROJECT_ID/pokemon-scanner

   # Or use Artifact Registry
   gcloud builds submit --tag us-central1-docker.pkg.dev/PROJECT_ID/images/pokemon-scanner
   ```

2. **Deploy to Cloud Run**:
   ```bash
   gcloud run deploy pokemon-scanner \
     --image gcr.io/PROJECT_ID/pokemon-scanner \
     --platform managed \
     --region us-central1 \
     --allow-unauthenticated \
     --memory 1Gi \
     --cpu 1 \
     --min-instances 0 \
     --max-instances 10 \
     --set-env-vars ENVIRONMENT=production \
     --set-env-vars GOOGLE_API_KEY=your-api-key
   ```

3. **Cloud Run YAML deployment**:
   ```yaml
   apiVersion: serving.knative.dev/v1
   kind: Service
   metadata:
     name: pokemon-scanner
     annotations:
       run.googleapis.com/ingress: all
   spec:
     template:
       metadata:
         annotations:
           autoscaling.knative.dev/minScale: "0"
           autoscaling.knative.dev/maxScale: "10"
           run.googleapis.com/cpu-throttling: "false"
       spec:
         containerConcurrency: 100
         containers:
         - image: gcr.io/PROJECT_ID/pokemon-scanner
           resources:
             limits:
               cpu: 1000m
               memory: 1Gi
           env:
           - name: ENVIRONMENT
             value: "production"
           - name: GOOGLE_API_KEY
             valueFrom:
               secretKeyRef:
                 name: pokemon-secrets
                 key: api-key
   ```

### Google Kubernetes Engine (GKE)

**Ideal for**: High traffic, enterprise deployment, full control.

1. **Create GKE cluster**:
   ```bash
   gcloud container clusters create pokemon-scanner-cluster \
     --num-nodes 3 \
     --machine-type e2-standard-2 \
     --zone us-central1-a \
     --enable-autoscaling \
     --min-nodes 1 \
     --max-nodes 10
   ```

2. **Get credentials**:
   ```bash
   gcloud container clusters get-credentials pokemon-scanner-cluster \
     --zone us-central1-a
   ```

3. **Deploy using Kubernetes manifests** (see Kubernetes section above)

### Compute Engine (VM)

**Ideal for**: Simple deployment, full control, predictable costs.

1. **Create VM instance**:
   ```bash
   gcloud compute instances create pokemon-scanner-vm \
     --image-family ubuntu-2204-lts \
     --image-project ubuntu-os-cloud \
     --machine-type e2-standard-2 \
     --zone us-central1-a \
     --tags http-server,https-server
   ```

2. **SSH and setup**:
   ```bash
   gcloud compute ssh pokemon-scanner-vm --zone us-central1-a

   # Install Docker
   curl -fsSL https://get.docker.com -o get-docker.sh
   sudo sh get-docker.sh
   sudo usermod -aG docker $USER

   # Deploy using Docker Compose
   git clone <repository-url>
   cd pokemon-card-scanner
   cp .env.example .env
   # Edit .env with your configuration
   docker-compose up -d
   ```

### App Engine

**Ideal for**: Managed platform, automatic scaling.

Create `app.yaml`:
```yaml
runtime: python312
service: pokemon-scanner

env_variables:
  ENVIRONMENT: production
  GOOGLE_API_KEY: your-api-key

resources:
  cpu: 1
  memory_gb: 1
  disk_size_gb: 10

automatic_scaling:
  min_instances: 0
  max_instances: 10
  target_cpu_utilization: 0.6
```

**Deploy**:
```bash
gcloud app deploy
```

## AWS Deployment

### ECS/Fargate

**Ideal for**: Serverless containers, managed infrastructure.

1. **Create task definition**:
   ```json
   {
     "family": "pokemon-scanner",
     "networkMode": "awsvpc",
     "requiresCompatibilities": ["FARGATE"],
     "cpu": "512",
     "memory": "1024",
     "executionRoleArn": "arn:aws:iam::ACCOUNT:role/ecsTaskExecutionRole",
     "containerDefinitions": [
       {
         "name": "pokemon-scanner",
         "image": "pokemon-card-scanner:latest",
         "portMappings": [
           {
             "containerPort": 8000,
             "protocol": "tcp"
           }
         ],
         "environment": [
           {
             "name": "ENVIRONMENT",
             "value": "production"
           }
         ],
         "secrets": [
           {
             "name": "GOOGLE_API_KEY",
             "valueFrom": "arn:aws:secretsmanager:us-east-1:ACCOUNT:secret:pokemon-scanner/api-key"
           }
         ],
         "logConfiguration": {
           "logDriver": "awslogs",
           "options": {
             "awslogs-group": "/ecs/pokemon-scanner",
             "awslogs-region": "us-east-1",
             "awslogs-stream-prefix": "ecs"
           }
         }
       }
     ]
   }
   ```

2. **Create ECS service**:
   ```bash
   aws ecs create-service \
     --cluster pokemon-scanner-cluster \
     --service-name pokemon-scanner \
     --task-definition pokemon-scanner:1 \
     --desired-count 2 \
     --launch-type FARGATE \
     --network-configuration "awsvpcConfiguration={subnets=[subnet-12345],securityGroups=[sg-12345],assignPublicIp=ENABLED}"
   ```

### Elastic Kubernetes Service (EKS)

Use the Kubernetes manifests from the Kubernetes section with EKS-specific configurations.

### EC2 Deployment

Similar to Compute Engine - create EC2 instances and deploy using Docker or directly.

## Production Considerations

### Load Balancing

**Application Load Balancer (AWS)**:
```yaml
# ALB Ingress for EKS
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: pokemon-scanner-alb
  annotations:
    kubernetes.io/ingress.class: alb
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/target-type: ip
spec:
  rules:
  - host: pokemon-scanner.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: pokemon-scanner-service
            port:
              number: 80
```

**Google Load Balancer**:
```yaml
# GKE Ingress
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: pokemon-scanner-ingress
  annotations:
    kubernetes.io/ingress.global-static-ip-name: pokemon-scanner-ip
    networking.gke.io/managed-certificates: pokemon-scanner-ssl
spec:
  rules:
  - host: pokemon-scanner.example.com
    http:
      paths:
      - path: /*
        pathType: ImplementationSpecific
        backend:
          service:
            name: pokemon-scanner-service
            port:
              number: 80
```

### SSL/TLS Setup

**Let's Encrypt with cert-manager**:
```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: your-email@example.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: nginx
```

### Monitoring and Logging

**Prometheus & Grafana**:
```yaml
# ServiceMonitor for Prometheus
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: pokemon-scanner-metrics
spec:
  selector:
    matchLabels:
      app: pokemon-scanner
  endpoints:
  - port: metrics
    path: /metrics
```

**Centralized Logging**:
```yaml
# Fluentd DaemonSet for log collection
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: fluentd
spec:
  selector:
    matchLabels:
      name: fluentd
  template:
    spec:
      containers:
      - name: fluentd
        image: fluent/fluentd-kubernetes-daemonset:v1-debian-elasticsearch
        env:
        - name: FLUENT_ELASTICSEARCH_HOST
          value: "elasticsearch.logging.svc.cluster.local"
```

### Backup Strategies

**Configuration Backup**:
```bash
# Backup Kubernetes resources
kubectl get all,configmap,secret -n pokemon-scanner -o yaml > backup.yaml

# Backup environment files
tar -czf config-backup-$(date +%Y%m%d).tar.gz .env* docker-compose.yml
```

**Automated Backups**:
```yaml
# CronJob for periodic backups
apiVersion: batch/v1
kind: CronJob
metadata:
  name: backup-job
spec:
  schedule: "0 2 * * *"  # Daily at 2 AM
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: backup
            image: alpine/kubectl
            command:
            - /bin/sh
            - -c
            - kubectl get all -o yaml > /backup/backup-$(date +%Y%m%d).yaml
          restartPolicy: OnFailure
```

## Configuration Reference

### Environment Variables

See [.env.example](.env.example) for the complete list of configuration options.

**Critical Production Settings**:
```bash
# Required
GOOGLE_API_KEY=your-gemini-api-key

# Environment
ENVIRONMENT=production
DEBUG=false

# Security
CORS_ORIGINS=https://yourdomain.com,https://api.yourdomain.com
ALLOWED_HOSTS=yourdomain.com,api.yourdomain.com

# Performance
GEMINI_MAX_TOKENS=2000
IMAGE_MAX_DIMENSION=1024
CACHE_ENABLED=true
RATE_LIMIT_PER_MINUTE=60

# Monitoring
LOG_LEVEL=INFO
ENABLE_METRICS=true
ERROR_WEBHOOK_ENABLED=true
ERROR_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK
```

### Resource Requirements

**Minimum Requirements**:
- CPU: 0.5 cores
- Memory: 512 MB
- Storage: 1 GB

**Recommended Production**:
- CPU: 1-2 cores
- Memory: 1-2 GB
- Storage: 10 GB (for logs and processed images)

**High Traffic**:
- CPU: 2-4 cores
- Memory: 2-4 GB
- Storage: 50 GB
- Load balancer with multiple replicas

## Troubleshooting

### Common Issues

**1. Container fails to start**:
```bash
# Check logs
docker logs pokemon-scanner

# Common causes:
# - Missing GOOGLE_API_KEY
# - Invalid configuration values
# - Port conflicts
```

**2. High memory usage**:
```bash
# Monitor memory
docker stats pokemon-scanner

# Solutions:
# - Reduce IMAGE_MAX_DIMENSION
# - Limit concurrent requests
# - Add memory limits
```

**3. Slow response times**:
```bash
# Check Gemini API quotas
# Monitor rate limits
# Optimize image processing settings
```

**4. Camera not working on mobile**:
- Ensure HTTPS is enabled
- Check browser permissions
- Verify camera hardware support

### Health Checks

**API Health Check**:
```bash
curl -f http://localhost:8000/api/v1/health
```

**Kubernetes Health Check**:
```bash
kubectl get pods -n pokemon-scanner
kubectl describe pod <pod-name> -n pokemon-scanner
kubectl logs <pod-name> -n pokemon-scanner
```

### Performance Tuning

**Optimize for Speed**:
```bash
OPTIMIZE_FOR_SPEED=true
IMAGE_MAX_DIMENSION=800
GEMINI_TEMPERATURE=0.1
CACHE_ENABLED=true
```

**Optimize for Quality**:
```bash
OPTIMIZE_FOR_SPEED=false
IMAGE_MAX_DIMENSION=1024
GEMINI_MAX_TOKENS=4000
IMAGE_JPEG_QUALITY=95
```

### Logs Analysis

**Key Log Patterns**:
```bash
# Successful scans
grep "✅ Scan completed" /var/log/pokemon-scanner.log

# Errors
grep "❌" /var/log/pokemon-scanner.log

# Performance metrics
grep "processing_time_ms" /var/log/pokemon-scanner.log
```

## Security Best Practices

1. **Never commit API keys** to version control
2. **Use HTTPS** in production
3. **Implement rate limiting** to prevent abuse
4. **Regular security updates** for base images
5. **Least privilege** for service accounts
6. **Network policies** in Kubernetes
7. **Secret management** (HashiCorp Vault, AWS Secrets Manager)

## Support

For additional help:
- Check the [README.md](README.md) for basic setup
- Review the [API documentation](http://localhost:8000/docs)
- Open an issue on the repository
- Check application logs for detailed error messages

---

This deployment guide covers the most common deployment scenarios. Choose the deployment method that best fits your requirements, traffic patterns, and operational preferences.