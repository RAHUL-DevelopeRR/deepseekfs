# DEPRECATED — Web/Server Deployment Only
# =========================================
# This Dockerfile builds the FastAPI web-mode server (run.py + app/main.py).
# It is NOT used for the Windows desktop application (run_desktop.py + PyQt6).
# For desktop use, follow the installer/build instructions in README.md.

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Bind to all interfaces inside the container
ENV API_HOST=0.0.0.0

# Create sample documents
RUN mkdir -p sample_documents && \
    echo "Invoice from last week for Q1 budget analysis" > sample_documents/sample1.txt && \
    echo "Recent Python projects and machine learning notebooks" > sample_documents/sample2.txt && \
    echo "Marketing strategy document with revenue forecasts" > sample_documents/sample3.txt

# Build initial index
RUN python -m app.scripts.initial_index --path /app/sample_documents

# Expose API port
EXPOSE 8000

# Run API with uvicorn, binding to all interfaces
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
