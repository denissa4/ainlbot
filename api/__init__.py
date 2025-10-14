from flask_api import FlaskAPI, status
from flask import request

from .nlsql.handler import parsing_text
from .nlsql.nlsql_typing import NLSQLAnswer

import asyncio
import logging
import os

app = FlaskAPI(__name__)


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

        return nlsql_answer, status.HTTP_200_OK

    return '', status.HTTP_400_BAD_REQUEST
