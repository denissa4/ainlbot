# Copyright (c) Microsoft Corporation. 
# Licensed under the MIT License.

import sys
import traceback
from datetime import datetime
from http import HTTPStatus

from aiohttp import web
from aiohttp.web import Request, Response, json_response
from botbuilder.core import TurnContext, BotFrameworkAdapterSettings, BotFrameworkAdapter
from botbuilder.core.integration import aiohttp_error_middleware
from botbuilder.integration.aiohttp import (
    CloudAdapter,
    ConfigurationBotFrameworkAuthentication,
)
from botbuilder.schema import Activity, ActivityTypes

from bots import NLSQLBot
from config import DefaultConfig

CONFIG = DefaultConfig()

settings = BotFrameworkAdapterSettings(CONFIG.MicrosoftAppId, CONFIG.MicrosoftAppPassword)
ADAPTER = BotFrameworkAdapter(settings)


# Error handler
async def on_error(context: TurnContext, error: Exception):
    print(f"\n[on_turn_error] unhandled error: {error}", file=sys.stderr)
    traceback.print_exc()

    # Send user-friendly message
    await context.send_activity("The bot encountered an error or bug.")
    await context.send_activity("Please fix the bot source code to continue.")

    # If using Emulator, send a trace activity
    if context.activity.channel_id == "emulator":
        trace_activity = Activity(
            label="TurnError",
            name="on_turn_error Trace",
            timestamp=datetime.utcnow(),
            type=ActivityTypes.trace,
            value=str(error),
            value_type="https://www.botframework.com/schemas/error",
        )
        await context.send_activity(trace_activity)

ADAPTER.on_turn_error = on_error

# Instantiate your custom bot
BOT = NLSQLBot(
    nl_api_url=CONFIG.NLSQL_API_URL,
    debug=CONFIG.DEBUG,
)

# Bot message endpoint
async def messages(req: web.Request) -> web.Response:
    body = await req.json()
    activity = Activity().deserialize(body)
    
    auth_header = req.headers.get("Authorization", "")

    await ADAPTER.process_activity(activity, auth_header, BOT.on_turn)
    return web.Response(status=200)

# Create the AIOHTTP web app
APP = web.Application(middlewares=[aiohttp_error_middleware])
APP.router.add_post("/api/messages", messages)

if __name__ == "__main__":
    try:
        web.run_app(APP, host="0.0.0.0", port=CONFIG.PORT)
    except Exception as error:
        raise error
