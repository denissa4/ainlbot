# Flask-API is unmaintained and breaks on modern Werkzeug (it imports
# werkzeug.urls.url_decode_stream, removed in Werkzeug 2.3). Its only uses here
# were the app class and two HTTP status constants, both of which plain Flask
# covers - Flask serialises a returned dict to JSON by itself.
from flask import Flask, request

from .nlsql.handler import parsing_text
from .nlsql.nlsql_typing import NLSQLAnswer

import asyncio
import logging
import os

# AWS Marketplace requires paid container products to verify the buyer's
# subscription at start-up, from inside the application. No-ops unless
# AWS_MARKETPLACE_PRODUCT_CODE is set, so Azure and local runs are unaffected.
from .nlsql.aws_marketplace import verify_entitlement

verify_entitlement()

app = Flask(__name__)


@app.route("/nlsql-analyzer", methods=['POST'])
def post_nlsql():
    if os.getenv('DEBUG', '') == '1':
        logging.info('Get request')
    loop = asyncio.get_event_loop()
    if request.is_json:
        if os.getenv('DEBUG', '') == '1':
            logging.info('This is json request')
        nlsql_answer: NLSQLAnswer = loop.run_until_complete(parsing_text(request.json.get('channel_id', ''),
                                                                         request.json.get('text', '')))

        return nlsql_answer, 200

    return '', 400
