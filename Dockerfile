FROM debian:trixie-20250929-slim

# Install Python 3.7 manually
RUN apt-get update && \
    apt-get install -y wget build-essential libssl-dev zlib1g-dev \
    libncurses5-dev libffi-dev libsqlite3-dev libreadline-dev libbz2-dev && \
    wget https://www.python.org/ftp/python/3.7.17/Python-3.7.17.tgz && \
    tar -xvf Python-3.7.17.tgz && \
    cd Python-3.7.17 && \
    ./configure && \
    make -j"$(nproc)" && make altinstall && \
    cd .. && rm -rf Python-3.7.17* && \
    apt-get remove -y build-essential wget && apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

# Make python3.7 the default
RUN ln -s /usr/local/bin/python3.7 /usr/local/bin/python && \
    ln -s /usr/local/bin/pip3.7 /usr/local/bin/pip

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
    curl -fsSL https://deb.nodesource.com/setup_16.x | bash - && \
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

RUN pip install -r /app/api/requirements.txt && \
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
