FROM debian:trixie-20260824-slim

# Python comes from Debian (3.13.x on trixie), not built from source. The old
# image compiled CPython 3.7 by hand, which is now End-of-Life - AWS Marketplace
# rejects images containing EoL software, and it never received security updates.
# Using the distro package means python is patched by `apt-get upgrade` like
# everything else, and it cuts several minutes off the build.
#
# Debian marks the system python as externally managed (PEP 668), so application
# dependencies live in a virtualenv at /venv rather than in site-packages.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3 \
        python3-venv \
        python3-dev \
        build-essential \
        unixodbc-dev && \
    python3 -m venv /venv && \
    /venv/bin/pip install --no-cache-dir --upgrade pip && \
    rm -rf /var/lib/apt/lists/*

ENV PATH="/venv/bin:$PATH"

# Verify installation
RUN python --version && pip --version

RUN apt-get update && \
    apt-get install -y \
        curl \
        apt-transport-https \
        gnupg2 && \
    mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /etc/apt/keyrings/microsoft.gpg && \
    echo "deb [arch=amd64 signed-by=/etc/apt/keyrings/microsoft.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" > /etc/apt/sources.list.d/mssql-release.list && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get update -y && \
    ACCEPT_EULA=Y apt-get install -y \
        msodbcsql17 \
        unixodbc-dev \
        libgssapi-krb5-2 \
        nodejs \
        supervisor \
        nginx && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    echo 'export PATH="$PATH:/opt/mssql-tools/bin"' >> ~/.bash_profile && \
    echo 'export PATH="$PATH:/opt/mssql-tools/bin"' >> ~/.bashrc

# Pull security updates for everything installed above. The base image is a
# point-in-time snapshot, so without this openssl/libssl3 and gnutls28 stay at
# the versions baked into it and fail the Cloud Marketplace vulnerability scan.
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

ARG DataSource
ENV DataSource=${DataSource}
ARG DbUser
ENV DbUser=${DbUser}
ARG DbPassword
ENV DbPassword=${DbPassword}
ARG DbName
ENV DbName=${DbName}
ARG DbPort
ENV DbPort=${DbPort}
ARG ApiEndPoint
ENV ApiEndPoint=${ApiEndPoint}
ARG ApiToken
ENV ApiToken=${ApiToken}
ARG StaticEndPoint
ENV StaticEndPoint=${StaticEndPoint}

ARG FromYear
ENV FromYear=${FromYear}
ARG ToYear
ENV ToYear=${ToYear}
ARG CorridorsMode
ENV CorridorsMode=${CorridorsMode}
ARG BoundrySensetivity
ENV BoundrySensetivity=${BoundrySensetivity}

ARG EmailAddress
ENV EmailAddress=${EmailAddress}
ARG EmailPassword
ENV EmailPassword=${EmailPassword}
ARG RecipientEmail
ENV RecipientEmail=${RecipientEmail}

ARG AzureAppName
ENV AzureAppName=${AzureAppName}

ARG OpenAiAPI
ENV OpenAiAPI=${OpenAiAPI}
ARG OpenAiBase
ENV OpenAiBase=${OpenAiBase}
ARG OpenAiType
ENV OpenAiType=${OpenAiType}
ARG OpenAiVersion
ENV OpenAiVersion=${OpenAiVersion}
ARG OpenAiName
ENV OpenAiName=${OpenAiName}
ARG SystemMessage
ENV SystemMessage=${SystemMessage}

ARG Frequency
ENV Frequency=${Frequency}

WORKDIR /app
COPY . /app/

RUN /venv/bin/pip install --no-cache-dir -r /app/api/requirements.txt && \
    mkdir -p /var/www/html/bot/static && \
    cp /app/nginx/nginx.conf /etc/nginx/nginx.conf

RUN cd /app/bot && \
    npm install && \
    npm run build

# Ensure the supervisord configuration is copied
COPY supervisord.conf /app/supervisord.conf

CMD ["/usr/bin/supervisord", "-c", "/app/supervisord.conf"]

# Marketplace annotations
LABEL com.googleapis.cloudmarketplace.product.service.name="services/nlsql.endpoints.nlsql-public.cloud.goog"
LABEL com.googleapis.cloudmarketplace.product.id="nlsql"
LABEL com.googleapis.cloudmarketplace.product.version="latest"
