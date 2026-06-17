# Multi-stage Dockerfile for production deployment
# Optimized for Linux cloud environments (Railway, Render, AWS, etc.)

FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=5000

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY backend/requirements_production.txt requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install gunicorn for production
RUN pip install --no-cache-dir gunicorn

# Copy application code
COPY backend/ ./backend/
COPY training/outputs/shopping_agent_lora_hf/ ./training/outputs/shopping_agent_lora_hf/

# Create necessary directories
RUN mkdir -p /app/backend /app/training/outputs

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:5000/api/v1/system/health || exit 1

# Run the application with gunicorn
WORKDIR /app/backend
CMD gunicorn --bind 0.0.0.0:$PORT --workers 1 --timeout 120 --access-logfile - --error-logfile - "api_swagger:app"
