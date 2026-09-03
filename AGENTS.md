
        # Project Tree
        ```
        /
    .env
    .idea/
        .gitignore
        ainlbot.iml
        inspectionProfiles/
            Project_Default.xml
            profiles_settings.xml
        misc.xml
        modules.xml
        vcs.xml
        workspace.xml
    Dockerfile
    README.md
    api/
        __init__.py
        nlsql/
            __init__.py
            anomaly_handler.py
            connectors/
                __init__.py
                connectors.py
            graph.py
            handler.py
            nlsql_typing.py
        requirements.txt
    bot/
        .gitignore
        Dockerfile
        README.md
        deploymentScripts/
            linux/
                .deployment
                deploy.sh
            webConfigPrep.js
        deploymentTemplates/
            linux/
                template.json
            new-rg-parameters.json
            preexisting-rg-parameters.json
            template-with-new-rg.json
            template-with-preexisting-rg.json
        docker-compose.yml
        package.json
        src/
            bot.ts
            index.ts
        tsconfig.json
        tslint.json
    nginx/
        Dockerfile
        nginx.conf
    supervisord.conf
        ```
        # NLSQL Analyzer - Project Summary

## Overview
**NLSQL Analyzer** is a natural language SQL bot system that provides anomaly detection on database data. It connects to various database types, performs statistical analysis (corridor-based anomaly detection), and communicates results via a Microsoft Bot Framework chatbot. It integrates with OpenAI for generating informative emails about detected anomalies.

## Architecture

The project consists of three main components orchestrated via Docker Compose and Supervisord:

### 1. API Server (Python/Flask)
- **Location:** `/api/`
- **Language:** Python 3.7
- **Framework:** Flask with Gunicorn
- **Purpose:** Core analytics engine - connects to databases, performs anomaly detection using statistical corridors (standard or seasonal mode), generates visualizations (matplotlib, plotly), and sends email alerts
- **Endpoint:** `POST /nlsql-analyzer` with JSON body `{"channel_id": str, "text": str}`
- **Supported databases:** MySQL, MSSQL, Snowflake, Redshift, PostgreSQL, BigQuery

### 2. Bot (TypeScript/Node.js)
- **Location:** `/bot/`
- **Language:** TypeScript
- **Framework:** Microsoft Bot Framework (botbuilder ~4.15.0) with Restify
- **Purpose:** Chat interface that forwards user messages to the API server
- **Endpoint:** Receives messages at `/api/messages` (proxied via Nginx)

### 3. Nginx (Reverse Proxy / Static File Server)
- **Location:** `/nginx/`
- **Purpose:** Serves static files (graphs, exports) and proxies bot messages to the Node.js bot service

### Process Management
- **Supervisord** manages all three services in a single container (main Dockerfile)

## Build & Run Commands

### Single Container (All-in-one):
```bash
docker build -f Dockerfile -t nlsql-api-server .
docker run --rm -p 8080:80 --env-file .env nlsql-api-server
```

### Multi-Container (Docker Compose):
```bash
cd bot
docker-compose up
```

### Bot Only:
```bash
cd bot
docker build -t nodejs-bot .
```

## Key Configuration (Environment Variables)
- **Database:** `DatabaseType`, `DataSource`, `DbName`, `DbUser`, `DbPassword`, `DbPort`, `Warehouse`, `DbSchema`
- **API Auth:** `ApiEndPoint`, `ApiToken`, `AppId`, `AppPassword`, `AuthTenantID`
- **Anomaly Detection:** `FromYear`, `ToYear`, `CorridorsMode` (1=standard, 2=seasonal), `WindowSize`, `BoundarySensitivity`
- **Email Alerts:** `EmailAddress`, `EmailPassword`, `RecipientEmail`
- **OpenAI Integration:** `OpenAiAPI`, `OpenAiBase`, `OpenAiType`, `OpenAiVersion`, `OpenAiName`, `SystemMessage`
- **Scheduling:** `Frequency` (days between anomaly detection runs)
- **BigQuery-specific:** `client_email`, `token_uri`, `private_key`, `project_id`

## Notable Observations
- Uses Python 3.7 (compiled from source on Debian Trixie) - quite outdated
- Dependencies are pinned to older versions (e.g., openai==0.28.0, Flask==2.1.3)
- Has Google Cloud Marketplace labels, suggesting it's distributed as a marketplace product
- The anomaly detection uses mean ± (sensitivity × standard deviation) for boundary calculation
- Static files (graphs) are stored at `/var/www/html/bot/static` and served by Nginx
- The `AzureAppName` env var indicates deployment on Azure App Service
        