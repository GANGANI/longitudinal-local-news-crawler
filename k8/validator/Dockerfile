# Use lightweight Python image
FROM python:3.11-slim

# Install required packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl unzip && \
    rm -rf /var/lib/apt/lists/*

# Install python dependencies
RUN pip install --no-cache-dir internetarchive

# Set workdir
WORKDIR /app1

# Copy requirements
COPY requirements.txt .

# Create venv in absolute path
RUN python3 -m venv /app1/venv && \
    /app1/venv/bin/pip install --upgrade pip && \
    /app1/venv/bin/pip install -r requirements.txt
    
# Copy your script
COPY upload_validator.py .

RUN mkdir -p /root/.config
COPY ia.ini /root/.config/ia.ini

# Run script by default
CMD ["python", "/app1/upload_validator.py"]

