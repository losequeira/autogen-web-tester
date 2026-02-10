# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories for saved tests and temp recordings
RUN mkdir -p saved_tests temp_recordings

# Expose port (Cloud Run will set PORT env var)
ENV PORT=8080

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the application with gunicorn for production
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 --worker-class eventlet -w 1 web_ui:app
