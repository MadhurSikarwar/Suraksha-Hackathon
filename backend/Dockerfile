FROM python:3.11-slim

# Security: Run as non-root user
RUN groupadd -r suraksha && useradd -r -g suraksha suraksha

WORKDIR /app

# Install system dependencies for OpenCV (libGL) and glib
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       libgl1-mesa-glx \
       libglib2.0-0 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Create required runtime directories with correct ownership
RUN mkdir -p static/heatmaps temp_uploads \
    && chown -R suraksha:suraksha /app

# Switch to non-root user
USER suraksha

EXPOSE 8000

# BUGFIX: Was --host 0.0.0 (invalid IP, container would fail to bind)
# Correct is --host 0.0.0.0
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
