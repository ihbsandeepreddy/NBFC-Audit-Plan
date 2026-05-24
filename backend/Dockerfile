FROM python:3.12-slim

WORKDIR /app

# System dependencies for psycopg2 and polars
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc g++ curl && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create uploads directory
RUN mkdir -p /app/uploads

# Run with uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
