import os

class DefaultConfig:
    PORT = 3978
    MicrosoftAppId = os.environ.get("MicrosoftAppId", "")
    MicrosoftAppPassword = os.environ.get("MicrosoftAppPassword", "")
    MicrosoftAppTenantId = os.environ.get("MicrosoftAppTenantId", "")
    MicrosoftAppType = os.environ.get('MicrosoftAppType', 'SingleTenant')
    NLSQL_API_URL = os.environ.get("NLSQL_API_URL", "http://localhost:8000/nlsql-analyzer")
    DEBUG = os.environ.get("DEBUG", "false").lower() == "true"
