FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    default-libmysqlclient-dev \
    pkg-config \
    curl \
    git \
    dos2unix \
    && rm -rf /var/lib/apt/lists/*

# Copy and install python dependencies first for layer caching
COPY requirements.txt ./
RUN pip install --no-cache-dir -U pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Ensure data and logs directories exist
RUN mkdir -p /app/data/chromadb /app/logs /app/uploads

EXPOSE 8080

# Default command for FastAPI microservice (support live reload in dev)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--reload"]
