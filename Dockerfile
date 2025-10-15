# -------------------------------
# Stage 1: Build Bot (Python 3.11)
# -------------------------------
FROM python:3.11-slim AS bot-build

WORKDIR /app
COPY bot /app/bot
RUN pip install --no-cache-dir -r /app/bot/requirements.txt

# -------------------------------
# Stage 2: Build API (Python 3.9)
# -------------------------------
FROM debian:trixie-20250929-slim AS api-build

RUN apt-get update && \
    apt-get install -y wget build-essential libssl-dev zlib1g-dev liblzma-dev \
    libncurses5-dev libffi-dev libsqlite3-dev libreadline-dev libbz2-dev && \
    wget https://www.python.org/ftp/python/3.9.19/Python-3.9.19.tgz && \
    tar -xvf Python-3.9.19.tgz && \
    cd Python-3.9.19 && \
    ./configure --enable-optimizations && \
    make -j"$(nproc)" && make altinstall && \
    cd .. && rm -rf Python-3.9.19* && \
    apt-get remove -y build-essential wget && apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*


# Make Python 3.9 default for this stage
RUN ln -s /usr/local/bin/python3.9 /usr/local/bin/python && \
    ln -s /usr/local/bin/pip3.9 /usr/local/bin/pip

WORKDIR /app
COPY api /app/api
RUN pip install --no-cache-dir -r /app/api/requirements.txt

# -------------------------------
# Stage 3: Final runtime image
# -------------------------------
FROM debian:trixie-20250929-slim AS final

# Install system dependencies
RUN apt-get update && \
    apt-get install -y \
        curl \
        apt-transport-https \
        gnupg2 \
        supervisor \
        nginx \
        unixodbc-dev \
        libgssapi-krb5-2 && \
    mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /etc/apt/keyrings/microsoft.gpg && \
    echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/microsoft.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" > /etc/apt/sources.list.d/mssql-release.list && \
    apt-get update && \
    ACCEPT_EULA=Y apt-get install -y msodbcsql17 mssql-tools18 && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy both Python installations
COPY --from=bot-build /usr/local/ /usr/local/python311/
COPY --from=api-build /usr/local/ /usr/local/python39/

# Add both to PATH
ENV PATH="/usr/local/python39/bin:/usr/local/python311/bin:${PATH}"

# Copy app code
WORKDIR /app
COPY . /app/

# Setup directories
RUN mkdir -p /var/www/html/bot/static && \
    cp /app/nginx/nginx.conf /etc/nginx/nginx.conf

# Copy supervisord configuration
COPY supervisord.conf /app/supervisord.conf

# Supervisor launch
CMD ["/usr/bin/supervisord", "-c", "/app/supervisord.conf"]

# Marketplace labels
LABEL com.googleapis.cloudmarketplace.product.service.name="services/nlsql.endpoints.nlsql-public.cloud.goog"
LABEL com.googleapis.cloudmarketplace.product.id="nlsql"
LABEL com.googleapis.cloudmarketplace.product.version="latest"
