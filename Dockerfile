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
    /venv/bin/pip install --no-cache-dir --upgrade 'setuptools>=78.1.1' && \
    mkdir -p /var/www/html/bot/static && \
    cp /app/nginx/nginx.conf /etc/nginx/nginx.conf

RUN cd /app/bot && \
    npm install && \
    npm run build && \
    npm prune --omit=dev && \
    npm cache clean --force

# Remove the build toolchain. It is only needed to compile Python wheels and the
# TypeScript bot; leaving it in the published image adds a large vulnerability
# surface (python3-dev pulls in linux-libc-dev, which alone accounts for dozens
# of high-severity findings) that AWS Marketplace scans and rejects.
RUN apt-get purge -y --auto-remove \
        build-essential python3-dev libexpat1-dev unixodbc-dev \
        gnupg2 apt-transport-https python3-setuptools-whl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /root/.cache /tmp/*

# The npm CLI is build-time only - supervisord runs the compiled bot with node
# directly. npm bundles its own copies of tar, minimatch, pacote, sigstore and
# others, which account for most of the remaining high-severity findings, so
# removing it removes them.
RUN rm -rf /usr/lib/node_modules/npm /usr/bin/npm /usr/bin/npx /root/.npm

# pip is build-time only too. It vendors its own copies of msgpack and
# setuptools and declares them in pip/_vendor/vendor.txt, which scanners read as
# installed packages even though the real installs are newer. Removing pip drops
# those false findings and leaves no package manager in the runtime image.
RUN rm -rf /venv/lib/python3.13/site-packages/pip \
           /venv/lib/python3.13/site-packages/pip-*.dist-info \
           /venv/bin/pip /venv/bin/pip3 /venv/bin/pip3.13

# Ensure the supervisord configuration is copied
COPY supervisord.conf /app/supervisord.conf

# ---------------------------------------------------------------------------
# AWS Marketplace requirements (this branch only; master stays as Azure needs it)
#
# AWS: "Container images should be configured to run with non-root privileges by
# default." Azure App Service expects the container on port 80 and runs it as
# root, so both changes live here rather than on master.
#
# nginx.conf itself is left byte-identical to master and patched with sed, so
# merging master into this branch never conflicts on it.
# ---------------------------------------------------------------------------
ARG NGINX_PORT=8080
RUN sed -i "s/listen\s*80;/listen ${NGINX_PORT};/" /etc/nginx/nginx.conf && \
    sed -i "s#^error_log /dev/stdout;#error_log /dev/stdout;\npid /run/nginx/nginx.pid;#" /etc/nginx/nginx.conf && \
    grep -qE "listen\s+${NGINX_PORT};" /etc/nginx/nginx.conf

# A non-root user, plus write access to exactly the paths that are written at
# runtime: nginx's temp dirs and pid, the graph output directory, and the
# anomaly handler's logs. Pre-creating and chowning these means nginx never needs
# CHOWN at startup - the capability that had to be granted back on the GCP chart.
RUN groupadd -r nlsql && \
    useradd -r -g nlsql -u 10001 -d /app -s /usr/sbin/nologin nlsql && \
    mkdir -p /var/lib/nginx/body /var/lib/nginx/proxy /var/lib/nginx/fastcgi \
             /var/lib/nginx/uwsgi /var/lib/nginx/scgi /var/log/nginx /run/nginx \
             /var/www/html/bot/static && \
    touch /var/log/anomaly_handler.log /var/log/anomaly_handler_err.log && \
    chown -R nlsql:nlsql /var/lib/nginx /var/log/nginx /run/nginx /var/www/html \
                         /var/log/anomaly_handler.log /var/log/anomaly_handler_err.log \
                         /app /venv

USER nlsql

CMD ["/usr/bin/supervisord", "-c", "/app/supervisord.conf"]

# Marketplace annotations
LABEL com.googleapis.cloudmarketplace.product.service.name="services/nlsql.endpoints.nlsql-public.cloud.goog"
LABEL com.googleapis.cloudmarketplace.product.id="nlsql"
LABEL com.googleapis.cloudmarketplace.product.version="latest"
