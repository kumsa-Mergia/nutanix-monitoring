FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set workdir
WORKDIR /app

# Copy exporter code
COPY nutanix_exporter.py /app/

# Install Python dependencies
RUN pip install --no-cache-dir requests flask

# Expose exporter port
EXPOSE 9100

# Start exporter
CMD ["python", "nutanix_exporter.py"]
