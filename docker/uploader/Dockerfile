# ===============================
# Dockerfile for Daily Uploader
# ===============================
FROM python:3.11-slim

# --- System setup ---
# Create required directories and set ownership
RUN mkdir -p /app1 /home/crawler && \
    groupadd -g 1132 crawlergrp && \
    useradd -u 261440 -g 1132 -d /home/crawler -s /bin/bash crawler && \
    chown -R crawler:crawlergrp /app1 /home/crawler

ENV HOME=/home/crawler
WORKDIR /app1

# --- Dependencies ---
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    internetarchive \
    requests \
    python-dotenv

# --- Application ---
# Copy uploader script
COPY uploader.py /app1/uploader.py

# Copy Internet Archive credentials (ia.ini)
RUN mkdir -p /home/crawler/.config
COPY --chown=crawler:crawlergrp ia.ini /home/crawler/.config/ia.ini

# Make sure logs directory exists
RUN mkdir -p /var/log/uploader && chown -R crawler:crawlergrp /var/log/uploader

# Switch to non-root user for better security
USER crawler

# --- Runtime ---
# Default command (arguments can be overridden in K8s YAML)
ENTRYPOINT ["python", "/app1/uploader.py"]

