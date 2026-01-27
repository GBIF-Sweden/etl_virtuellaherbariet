# Use Python slim image for smaller size
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies (if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .
COPY pipeline.py .
COPY config/ ./config/
COPY extraction/ ./extraction/
COPY loading/ ./loading/
COPY transformation/ ./transformation/
COPY utils/ ./utils/

# Create directories for mounting
RUN mkdir -p /app/configs /app/data/verbatim /app/data/processed \
    && groupadd --system appgroup \
    && useradd --system --gid appgroup --create-home --home-dir /home/appuser appuser \
    && chown -R appuser:appgroup /app

# Set Python to run in unbuffered mode for better logging
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH="${PYTHONPATH}:/app"

# Drop root privileges
USER appuser

# Default command (can be overridden in docker-compose)
ENTRYPOINT ["python", "main.py"]
CMD ["--help"]
