"""Google Cloud Marketplace usage reporting.

The GKE Marketplace listing is priced usage-based on the metric ``requests``
("API Requests", reporting unit ``count``), so Google requires the deployed
application to report its own usage to Service Control. Marketplace supplies the
metering agent (ubbagent) for this; the Helm chart runs it as a sidecar in the
same Pod and this module posts one report per API request to its loopback REST
interface:

    https://github.com/GoogleCloudPlatform/marketplace-k8s-app-tools/blob/master/docs/billing-integration.md

The agent owns everything that makes usage reporting hard - it aggregates over a
buffer window, persists reports to disk across restarts, and retries against
Service Control - so this side is deliberately just a fire-and-forget POST. It
must never be able to break an answer, so every failure is swallowed and logged.

The Service Control reporting key and consumer ID exist only inside the
customer's own cluster, in the Secret the Marketplace deployer creates, which is
why the report has to originate here rather than from the NLSQL SaaS.

This module is inert unless ``UbbAgentEndpoint`` is set, so the same image still
runs unchanged on Azure App Service, on AWS Marketplace and on a developer
laptop.
"""

import datetime
import logging
import os
import uuid

import requests

log = logging.getLogger(__name__)

ENDPOINT_ENV = "UbbAgentEndpoint"
METRIC_ENV = "UsageMetric"

# Producer Portal Metric ID for the usage-based plan. Overridable so the metric
# can be renamed in the portal without rebuilding the image.
DEFAULT_METRIC = "requests"

# The agent is on the loopback interface of our own Pod, so this only has to
# cover the agent being slow to accept, never a network round trip.
TIMEOUT_SECONDS = 2


def report_usage(value=1):
    """Report ``value`` units of API usage to the metering agent.

    Returns quietly when no agent endpoint is configured, which is the case for
    every deployment other than Google Cloud Marketplace.
    """
    endpoint = os.getenv(ENDPOINT_ENV, "").strip().rstrip("/")
    if not endpoint:
        return

    metric = os.getenv(METRIC_ENV, "").strip() or DEFAULT_METRIC
    # A one-shot report covers an instant, so start and end are equal. The id is
    # the agent's deduplication key; every API request is genuinely distinct, so
    # a fresh one each time is what we want.
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    report = {
        "id": str(uuid.uuid4()),
        "name": metric,
        "startTime": now,
        "endTime": now,
        "value": {"int64Value": value},
    }

    try:
        response = requests.post(f"{endpoint}/report", json=report, timeout=TIMEOUT_SECONDS)
        if response.status_code >= 400:
            log.warning(
                "Marketplace metering: agent rejected a %r report: HTTP %s %s",
                metric, response.status_code, response.text[:200],
            )
    except Exception as exc:
        # Usage reporting must never cost the customer an answer. The agent
        # buffers and retries on its own, so a single missed report is survivable
        # - a persistent failure shows up in the sidecar's log and /status.
        log.warning("Marketplace metering: could not report %r usage: %r", metric, exc)
