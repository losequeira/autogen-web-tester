# Cloud Run Deployment Guide

This guide explains how to deploy AutoGen Web Tester to Google Cloud Run.

## Important Notes

### Feature Availability
- ✅ **AI-Driven Test Creation**: Fully supported in Cloud Run
- ❌ **Playwright Codegen Recording**: NOT supported (requires local environment)

The Playwright codegen recording feature requires a GUI display and interactive browser, which is not available in containerized cloud environments. When deployed to Cloud Run, the "Record" button will be disabled with a clear message.

**For production use:** Use the AI-driven test creation workflow, which works perfectly in cloud environments.

## Prerequisites

1. **Google Cloud Account** with billing enabled
2. **gcloud CLI** installed and configured
3. **Docker** installed locally (for testing)
4. **OpenAI API Key** for the AI agent

## Deployment Steps

### 1. Set Your Project ID
```bash
export PROJECT_ID="your-gcp-project-id"
gcloud config set project $PROJECT_ID
```

### 2. Enable Required APIs
```bash
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com
```

### 3. Create config.py with Secrets
Create a `config.py` file (or use environment variables in Cloud Run):

```python
# config.py
import os

OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', 'your-key-here')
MODEL_NAME = os.environ.get('MODEL_NAME', 'gpt-4')
TIMEOUT = int(os.environ.get('TIMEOUT', '60000'))
```

### 4. Build and Deploy to Cloud Run

#### Option A: Direct Deploy (Recommended)
```bash
gcloud run deploy autogen-web-tester \
  --source . \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars OPENAI_API_KEY=your-openai-api-key \
  --set-env-vars MODEL_NAME=gpt-4 \
  --set-env-vars TIMEOUT=60000 \
  --memory 1Gi \
  --cpu 1 \
  --timeout 3600 \
  --max-instances 10
```

#### Option B: Build Docker Image First
```bash
# Build the image
gcloud builds submit --tag gcr.io/$PROJECT_ID/autogen-web-tester

# Deploy to Cloud Run
gcloud run deploy autogen-web-tester \
  --image gcr.io/$PROJECT_ID/autogen-web-tester \
  --region us-central1 \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars OPENAI_API_KEY=your-openai-api-key \
  --memory 1Gi \
  --cpu 1 \
  --timeout 3600
```

### 5. Test Local Docker Build (Optional)
```bash
# Build locally
docker build -t autogen-web-tester .

# Run locally
docker run -p 8080:8080 \
  -e OPENAI_API_KEY=your-key \
  -e MODEL_NAME=gpt-4 \
  autogen-web-tester
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | - | Your OpenAI API key |
| `MODEL_NAME` | No | `gpt-4` | OpenAI model to use |
| `TIMEOUT` | No | `60000` | Browser timeout in ms |
| `PORT` | No | `8080` | Server port (set by Cloud Run) |

## Security Best Practices

### Using Secret Manager (Recommended)
Instead of passing API keys as environment variables:

```bash
# Create secret
echo -n "your-openai-api-key" | gcloud secrets create openai-api-key --data-file=-

# Grant access to Cloud Run service account
gcloud secrets add-iam-policy-binding openai-api-key \
  --member=serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com \
  --role=roles/secretmanager.secretAccessor

# Deploy with secret
gcloud run deploy autogen-web-tester \
  --source . \
  --region us-central1 \
  --set-secrets=OPENAI_API_KEY=openai-api-key:latest \
  --allow-unauthenticated
```

## Persistent Storage

Cloud Run is **stateless** - saved tests will be lost on container restart. For production:

### Option 1: Cloud Storage (Recommended)
Modify `web_ui.py` to use Cloud Storage for `saved_tests/`:

```python
from google.cloud import storage

# Save to Cloud Storage instead of local filesystem
```

### Option 2: Cloud Firestore
Use Firestore for test storage:

```python
from google.cloud import firestore

db = firestore.Client()
```

### Option 3: Accept Statelessness
For development/demo purposes, accept that tests reset on each deployment.

## Monitoring and Logs

### View Logs
```bash
gcloud run services logs read autogen-web-tester --region us-central1
```

### View in Console
Go to: https://console.cloud.google.com/run

## Cost Optimization

Cloud Run pricing is based on:
- **Requests**: $0.40 per million requests
- **CPU**: $0.00002400 per vCPU-second
- **Memory**: $0.00000250 per GiB-second

### Tips:
1. Set `--max-instances` to control scaling
2. Use `--min-instances 0` to scale to zero when idle
3. Set `--cpu-throttling` to reduce costs during idle
4. Monitor usage in Cloud Console

## Troubleshooting

### Issue: Service won't start
**Solution**: Check logs for missing environment variables
```bash
gcloud run services logs read autogen-web-tester --region us-central1 | grep ERROR
```

### Issue: OpenAI API errors
**Solution**: Verify API key is set correctly
```bash
gcloud run services describe autogen-web-tester --region us-central1 --format="value(spec.template.spec.containers[0].env)"
```

### Issue: Timeout errors
**Solution**: Increase timeout (max 3600s):
```bash
gcloud run services update autogen-web-tester --timeout 3600 --region us-central1
```

### Issue: Out of memory
**Solution**: Increase memory allocation:
```bash
gcloud run services update autogen-web-tester --memory 2Gi --region us-central1
```

## Update Deployment

To deploy updates:
```bash
gcloud run deploy autogen-web-tester \
  --source . \
  --region us-central1
```

## Delete Service

To remove the deployment:
```bash
gcloud run services delete autogen-web-tester --region us-central1
```

## Custom Domain

To use a custom domain:
```bash
gcloud run domain-mappings create --service autogen-web-tester --domain your-domain.com --region us-central1
```

Then configure DNS:
- Type: `CNAME`
- Name: `your-subdomain` or `@`
- Value: `ghs.googlehosted.com`

## CI/CD with GitHub Actions

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Cloud Run

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - uses: google-github-actions/auth@v1
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}

      - name: Deploy to Cloud Run
        run: |
          gcloud run deploy autogen-web-tester \
            --source . \
            --region us-central1 \
            --set-env-vars OPENAI_API_KEY=${{ secrets.OPENAI_API_KEY }}
```

## Architecture Notes

### WebSocket Support
Cloud Run fully supports WebSockets for real-time browser streaming.

### Headless Browser
The AI-driven tests use Playwright in **headless mode**, which works perfectly in Cloud Run's containerized environment.

### Stateless Design
Each request is isolated. Browser sessions are created and destroyed per test run.

## Support

For issues specific to Cloud Run deployment:
- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Cloud Run Pricing](https://cloud.google.com/run/pricing)

For application issues:
- Check application logs
- Review `web_ui.py` error handling
