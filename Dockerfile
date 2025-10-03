FROM python:3.7-bookworm

RUN apt-get update && \
    apt-get install -y  \
        curl  \
        apt-transport-https \
        gnupg2 && \
    curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - && \
    curl https://packages.microsoft.com/config/debian/11/prod.list > /etc/apt/sources.list.d/mssql-release.list && \
    curl -fsSL https://deb.nodesource.com/setup_16.x | bash - && \
    apt-get update -y && \
    ACCEPT_EULA=Y apt-get install -y \
        msodbcsql17 \
#        mssql-tools \
        unixodbc-dev \
        libgssapi-krb5-2 \
        nodejs \
        supervisor \
        nginx && \
    apt-get autoremove -y && \
        apt-get clean \
        && rm -rf /var/lib/apt/lists && \
    echo 'export PATH="$PATH:/opt/mssql-tools/bin"' >> ~/.bash_profile && \
    echo 'export PATH="$PATH:/opt/mssql-tools/bin"' >> ~/.bashrc

# optional: for bcp and sqlcmd
# optional: for unixODBC development headers
# optional: kerberos library for debian-slim distributions

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
LABEL com.googleapis.cloudmarketplace.product.service.name="services/nlsql"
LABEL com.googleapis.cloudmarketplace.product.id="nlsql"
LABEL com.googleapis.cloudmarketplace.product.version="1.0.0"
