### API-server

Example local build cmd:

```bash
docker build -f Dockerfile -t nlsql-api-server .
```

Example local run cmd:

```bash
docker run --rm -p 8080:80 --env-file .env nlsql-api-server
```

Docker env params:

-   DatabaseType (_Options: 'mysql', 'mssql', 'snowflake', 'redshift', 'postgresql', 'bigquery'_)
-   DataSource (_For 'snowflake' analogue of the 'Account' db parameter_)
-   Warehouse (_Used when DataSource='snowflake'_)
-   DbSchema (_Used when DataSource='snowflake'_)
-   DbName
-   DbUser
-   DbPassword
-   DbPort (_Used when DataSource is 'mysql' or 'postgresql'_)
-   ApiEndPoint
-   ApiToken
-   UbbAgentEndpoint (_Google Cloud Marketplace only; the ubbagent sidecar's REST interface, e.g. `http://127.0.0.1:4567`. Usage reporting is disabled when unset_)
-   UsageMetric (_Google Cloud Marketplace only; Producer Portal Metric ID, default `requests`_)
-   AppId
-   AuthTenantID (_Optional_)
-   AppPassword
-   StaticEndPoint
-   client_email (\_Used when DataSource='bigquery'\*)
-   token_uri (\_Used when DataSource='bigquery'\*)
-   private_key (\_Used when DataSource='bigquery'\*)
-   project_id (\_Used when DataSource='bigquery'\*)
-   FromYear (_Starting year from which to measure trusted data_)
-   ToYear (_The final year up to which trusted data is measured (inclusive)_)
-   CorridorsMode (_1 = standard mode (flat corridors over given time period, minimum 1 year of data); 2 = seasonal mode (monthly calculated corridors, minimum 2 years' of data)_)
-   WindowSize (_Size of the rolling window when using seasonal corridors mode (default = 5)_)
-   BoundarySensitivity (_Sensitivity for the lower and upper bounds for anomaly detection (mean +- BoundarySensitivity \* standard deviation)_)
-   EmailAddress (_Email address for sending anomaly detection email_)
-   EmailPassword (_Password for senders email (app password may need to be used for gmail and outlook accounts)_)
-   RecipientEmail (_Email addresses of recipients (seperated by comma (no space))_)
-   AzureAppName (_Azure app name where interactive graph files are stored_)
-   OpenAiAPI (_API key for OpenAI integration (informative emails)_)
-   OpenAiBase (_Base URL for OpenAI integration_)
-   OpenAiType (_Type of OpenAI service, (e.g. azure)_)
-   OpenAiVersion (_Open AI version_)
-   OpenAiName (_Name of OpenAI model to be used_)
-   SystemMessage (_System Message for OpenAI for initial context and instructions given to OpenAI model_)
-   Frequency (_Frequency (in days) for which the anomaly detection should take place_)

API endpoint: `/nlsql-analyzer`

Method: `POST`

JSON: `{"channel_id": str, "text": str}`

### Nginx

location `~* \.(jpg|jpeg|gif|png|css|zip|tgz|gz|rar|bz2|doc|xls|exe|pdf|ppt|tar|mid|midi|wav|bmp|rtf|js|swf|docx|xlsx|svg|csv|html)$`
to `root /var/www/html`

location `/api/messages`
to `proxy_pass http://localhost:8000`
