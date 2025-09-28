FROM webrecorder/browsertrix-crawler:latest

# Install venv support
USER root
RUN apt-get update && apt-get install -y python3-venv && rm -rf /var/lib/apt/lists/*

# Match Kubernetes UID/GID
ARG UID=261440
ARG GID=1132
RUN groupadd -g ${GID} btrix && \
    useradd -r -u ${UID} -g ${GID} btrix

# Prepare directories
RUN mkdir -p /home/btrix /app1/collections /app1/crawls && \
    chown -R btrix:btrix /app1 /tmp /home/btrix

USER btrix
ENV HOME=/home/btrix
WORKDIR /app1

# Copy requirements
COPY requirements.txt .

# Create venv in absolute path
RUN python3 -m venv /app1/venv && \
    /app1/venv/bin/pip install --upgrade pip && \
    /app1/venv/bin/pip install -r requirements.txt

# Copy scripts and data
COPY upload_ia.py .
COPY upload_validator.py .
COPY browsertrix-crawler.py .
COPY data.json .

# Default working dir for crawler output
#WORKDIR /app1/crawls

# Copy ia.ini to default location and fix ownership
RUN mkdir -p /home/btrix/.config
COPY --chown=btrix:btrix ia.ini /home/btrix/.config/ia.ini

# Use absolute venv path
ENTRYPOINT ["/app1/venv/bin/python"]
CMD ["/app1/browsertrix-crawler.py"]

