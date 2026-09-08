"""AWS Marketplace entitlement check.

The AWS Marketplace listing uses fixed monthly pricing, and AWS requires that
model to verify the buyer's subscription with the Metering Service `RegisterUsage`
API at container start-up:

    "For hourly and fixed monthly pricing models, use the RegisterUsage API
     operation."

AWS is explicit that this belongs inside the application rather than in an
ENTRYPOINT wrapper, because a buyer who can add image layers could otherwise
override the call.

This module is inert unless ``AWS_MARKETPLACE_PRODUCT_CODE`` is set, so the same
image still runs unchanged on Azure App Service and on a developer laptop.
"""

import json
import logging
import os
import sys
import urllib.request
import uuid

log = logging.getLogger(__name__)

PRODUCT_CODE_ENV = "AWS_MARKETPLACE_PRODUCT_CODE"

# AWS Marketplace issues a public key version alongside the product code. It has
# been 1 for every container product to date; override only if AWS tells you to.
PUBLIC_KEY_VERSION = int(os.getenv("AWS_MARKETPLACE_PUBLIC_KEY_VERSION", "1"))

_checked = False


def _region_from_ecs_metadata():
    """Derive the region from the ECS task metadata endpoint.

    AWS requires the Region to be resolved at runtime rather than configured, or
    RegisterUsage raises InvalidRegionException. boto3 normally works this out on
    its own; this is the documented fallback for when it cannot, and it reads the
    region out of the task ARN.
    """
    uri = os.getenv("ECS_CONTAINER_METADATA_URI_V4") or os.getenv("ECS_CONTAINER_METADATA_URI")
    if not uri:
        return None
    try:
        with urllib.request.urlopen(f"{uri}/task", timeout=2) as resp:
            task_arn = json.load(resp).get("TaskARN", "")
        # arn:aws:ecs:<region>:<account>:task/<cluster>/<id>
        parts = task_arn.split(":")
        return parts[3] if len(parts) > 3 and parts[3] else None
    except Exception as exc:  # metadata endpoint is best-effort
        log.debug("AWS Marketplace: could not read ECS task metadata: %r", exc)
        return None


def verify_entitlement():
    """Verify the caller is entitled to run this product.

    Exits the process when the customer is not subscribed. Returns quietly when
    no product code is configured, or when running somewhere the Metering Service
    does not support (local development), so non-AWS deployments are unaffected.
    """
    global _checked
    if _checked:
        return
    _checked = True

    product_code = os.getenv(PRODUCT_CODE_ENV, "").strip()
    if not product_code:
        log.info(
            "AWS Marketplace: %s is not set, skipping the entitlement check. "
            "This is expected outside AWS Marketplace deployments.",
            PRODUCT_CODE_ENV,
        )
        return

    try:
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError
    except ImportError:
        log.error("AWS Marketplace: boto3 is required for the entitlement check.")
        sys.exit(1)

    # Whether we are actually running on AWS decides how a failed check is
    # treated. On AWS a failure is fatal; anywhere else (a developer laptop, or
    # Azure with the variable set by mistake) it is only a warning, so the same
    # image stays runnable. ECS and EKS both expose one of these.
    on_aws = any(os.getenv(v) for v in (
        "ECS_CONTAINER_METADATA_URI_V4",
        "ECS_CONTAINER_METADATA_URI",
        "AWS_EXECUTION_ENV",
        "AWS_WEB_IDENTITY_TOKEN_FILE",
    ))

    def _fail(message):
        if on_aws:
            log.error("AWS Marketplace: %s", message)
            sys.exit(1)
        log.warning(
            "AWS Marketplace: %s. Not running on ECS or EKS, so continuing "
            "without an entitlement check.", message,
        )

    # Never pin a Region here - it must come from the runtime environment, or
    # RegisterUsage raises InvalidRegionException.
    region = _region_from_ecs_metadata()

    try:
        client = boto3.client("meteringmarketplace", region_name=region) if region \
            else boto3.client("meteringmarketplace")
        client.register_usage(
            ProductCode=product_code,
            PublicKeyVersion=PUBLIC_KEY_VERSION,
            Nonce=str(uuid.uuid4()),
        )
        log.info("AWS Marketplace: entitlement verified for product %s.", product_code)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")

        if code == "PlatformNotSupportedException":
            # Returned outside ECS/EKS/Fargate - i.e. local development. AWS
            # documents this as expected, so it must not stop the container.
            log.warning(
                "AWS Marketplace: platform does not support metering, "
                "continuing without an entitlement check."
            )
            return

        if code == "CustomerNotEntitledException":
            log.error(
                "AWS Marketplace: this AWS account is not subscribed to NLSQL. "
                "Subscribe on AWS Marketplace, then start the task again."
            )
            sys.exit(1)

        # InvalidProductCodeException, InvalidRegionException,
        # InvalidPublicKeyVersionException and friends are all deployment faults
        # that will not fix themselves.
        _fail(f"entitlement check failed ({code}): {exc}")
    except BotoCoreError as exc:
        # NoRegionError, NoCredentialsError, EndpointConnectionError - the SDK
        # could not reach the Metering Service at all. On ECS the task role
        # supplies credentials and the Region, so this means misconfiguration.
        _fail(f"could not call the Metering Service ({type(exc).__name__}): {exc}")
