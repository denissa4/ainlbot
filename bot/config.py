import os

class DefaultConfig:
    PORT = int(os.environ.get("BOT_PORT", 3978))
    APP_ID = os.environ.get("MicrosoftAppId", "")
    APP_PASSWORD = os.environ.get("MicrosoftAppPassword", "")
    APP_TYPE = os.environ.get("MicrosoftAppType", "SingleTenant")
    APP_TENANTID = os.environ.get("MicrosoftAppTenantId", "")
    NLSQL_API_URL = os.environ.get("NLSQL_API_URL", "http://localhost:8000/nlsql-analyzer")
    DEBUG = os.environ.get("DEBUG", "false").lower() == "true"
