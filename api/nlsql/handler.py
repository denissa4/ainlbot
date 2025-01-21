import csv
import datetime
import os
import random
from typing import List, Union, Dict
from json.decoder import JSONDecodeError
import requests
from botbuilder.schema import ActionTypes
from .connectors import connectors
import logging

from . import graph
from .nlsql_typing import Buttons, NLSQLAnswer

logging.basicConfig(level=logging.INFO)



async def create_addition_buttons(answer, count='20') -> Union[List[Buttons], None]:
    logging.info(f"Answer: {answer}\n\n")
    logging.info(f"Count: {count}\n\n")
    if type(answer) == list:
        buttons = [{'type': ActionTypes.im_back, 'title': title, 'value': title} for title in answer]
    else:
        title = f'Show next {count} elements'
        buttons = [{'type': ActionTypes.im_back, 'title': title, 'value': answer}]

    if buttons:
        return buttons
    return None


async def create_adaptive_card_attachment(data: list, text, column_names) -> Dict:
    text_block = {
                "type": "TextBlock",
                "size": "Medium",
                "weight": "Bolder",
                "text": text
            }
    # Table title
    columns = []
    async for el in words(column_names):
        column = {
                                    "type": "Column",
                                    "width": "stretch",
                                    "style": "default",
                                    "items": [
                                        {
                                            "type": "TextBlock",
                                            "wrap": True,
                                            "text": el,
                                            "weight": "Bolder"
                                        }
                                    ],
                                    "separator": True
                                }
        columns.append(column)
    column_names_set = {
                            "type": "ColumnSet",
                            "columns": columns,
                            "bleed": True,
                            "separator": True
                        }
    body = [text_block, column_names_set]
    async for row in words(data):
        columns = []
        async for el in words(row):
            column = {
                            "type": "Column",
                            "width": "stretch",
                            "items": [
                                {
                                    "type": "TextBlock",
                                    "text": el,
                                    "wrap": True
                                }
                            ],
                            "separator": True
                        }
            columns.append(column)
        column_set = {
            "type": "ColumnSet",
            "columns": columns,
            "bleed": True,
            "separator": True
        }
        body.append(column_set)
    card_data = {
                    "$schema": "https://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.2",
                    "body": body
                }
    return card_data


async def create_arg_buttons(result, channel, data_type='arg_buttons'):
    buttons = []
    button_all_options = None
    elements: Union[Dict, List] = result[-1]

    if channel == 'msteams':
        postback = ActionTypes.im_back
    else:
        postback = ActionTypes.post_back

    if data_type == 'arg_buttons':
        all_options_value = elements.pop(-1)
        answer_all_options = result[1] + " [{{[all_arg:{}]}}]".format(all_options_value)
        button_all_options = {'type': postback, 'title': "All options", 'value': answer_all_options}

    for word in elements:
        answer = result[1] + " " + word
        button = {'type': postback, 'title': "{}".format(elements.get(word)
                                                         if data_type != 'arg_buttons' else word), 'value': answer}
        buttons.append(button)
    # =====================================================
    if button_all_options:
        buttons.append(button_all_options)
    if buttons:
        return buttons
    return None


async def create_system_buttons(result, channel):
    buttons = []
    word_dict = result[1]
    keys = list(word_dict.keys())
    # [{'type': ActionTypes.open_url, 'title': 'Open Chart', 'value': url}]
    if channel == 'msteams':
        postback = ActionTypes.im_back
    else:
        postback = ActionTypes.post_back
    async for key in words(keys):
        word_list = word_dict.get(key)
        if type(word_list) == list:
            async for i, word in words_for_check(word_list):

                if type(word) != str:
                    word = word[0]
                answer = result[0] + ' [{[' + key + ':' + word
                answer = answer + ']}]'
                button = {'type': postback, 'title': "{}".format(word, key), 'value': answer}
                buttons.append(button)
        else:
            word = word_list
            answer = result[0] + ' [{[' + key + ':' + word
            answer = answer + ']}]'
            button = {'type': postback, 'title': "{}".format(word, key), 'value': answer}
            buttons.append(button)
    if buttons:
        return buttons
    return None


async def generate_button(result, key: str, word: str, buttons: List, postback):
    answer = result[0] + ' [[[' + key + ':' + word + ']]]'
    button = {'type': postback, 'title': f"{word} | {key}", 'value': answer}
    buttons.append(button)


async def generate_like_button(result, key: str, word: str, buttons: List, postback):
    answer = result[0] + ' [%[' + key + ':' + word + ']%]'
    button = {'type': postback, 'title': f"All options from  {key}", 'value': answer}
    buttons.append(button)


async def create_complex_buttons(result: List[Union[str, Dict]], channel):
    buttons = []
    word_dict = result[-1]
    keys = list(word_dict.keys())
    if channel == 'msteams':
        postback = ActionTypes.im_back
    else:
        postback = ActionTypes.post_back
    async for key in words(keys):
        word_list: Union[str, Dict, List] = word_dict.get(key)
        if isinstance(word_list, list):
            async for i, word in words_for_check(word_list):
                if type(word) != str:
                    word = word[0]
                await generate_button(result, key, word, buttons, postback)
        elif isinstance(word_list, dict):
            button_values: str = word_list.get('value', '')
            async for i, word in words_for_check(button_values):
                if type(word) != str:
                    word = word[0]
                await generate_button(result, key, word, buttons, postback)
            button_like: str = word_list.get('SQL_LIKE', '')
            if button_like:
                await generate_like_button(result, key, button_like, buttons, postback)
        else:
            word: str = word_list
            await generate_button(result, key, word, buttons, postback)

    if buttons:
        # Purge potential duplicates
        for button in buttons:
            q = button['value'].split('[[[')[0]
            v = button['value'].split(':')[1].replace(']]]', '')
            if v in q:
                button['value'] = button['value'].replace(v, '', 1)
        return buttons
    return None

# List of elements global variable to store additional elements for addition button presses
list_of_elements = []
previous_add_btn = ''
# main function to parse request
async def parsing_text(channel_id: str, text: str) -> NLSQLAnswer:
    global list_of_elements
    global previous_add_btn

    if channel_id == 'msteams':
        text = text.replace('\u200b', '')
    try:
        api_response = await api_post(text)
    except JSONDecodeError:
        answer = "Google API usage limit reached. The bot encountered an error. " \
                 "Please, try again later or contact the support."
        return {'answer': answer,
                'answer_type': 'text',
                'addition_buttons': None,
                'unaccounted': None,
                'images': None,
                'card_data': None,
                'buttons': None
                }
    logging.info(f"Channel ID: {channel_id}")
    logging.info(f"API Response: {api_response}\n\n")
    logging.info(f"List of Elements: {list_of_elements}\n\n")
    logging.info(f"Text: {text}\n\n")
    data_type = api_response.get('data_type', '')
    sql = api_response.get('sql', '')
    message = api_response.get('message', '')
    unaccounted = api_response.get('unaccounted', None)
    if not unaccounted:
        unaccounted = None
    system_buttons = api_response.get('system_buttons', '')
    indicator = api_response.get('indicator', '')
    if type(sql) == dict:
        graph_range: int = sql.get("range", 5)
    else:
        graph_range = 0
    addition_buttons = api_response.get('addition_buttons', None)
    if not addition_buttons:
        addition_buttons = None
    logging.info(f"Addition Buttons: {addition_buttons}")
    logging.info(f"Previous addition buttons: {previous_add_btn}")
    # Check db connection params
    db_type = os.getenv('DatabaseType', 'mysql')
    if db_type:
        # make case-insensitive db-type input
        db_type = db_type.lower()
    snowflake_db_attr = ('Account', 'Warehouse', 'DbName', 'DbSchema', 'DbUser', 'DbPassword')
    bigquery_db_attr = ('client_email', 'token_uri', 'private_key', 'project_id')
    other_db_attr = ('DataSource', 'DbName', 'DbPassword', 'DbUser')
    db_attr = {'snowflake': snowflake_db_attr, 'bigquery': bigquery_db_attr, 'other': other_db_attr}
    not_exist_db_attr = []
    async for el in words(db_attr.get(db_type, db_attr["other"])):
        if not os.getenv(el):
            not_exist_db_attr.append(f"<{el}>")

    if not_exist_db_attr:
        answer = "Can't connect to DataBase: {} attribute(s) is(are) not specified. " \
                 "Please contact your system administrator".format(", ".join(not_exist_db_attr))
        return {'answer': answer,
                'answer_type': 'text',
                'addition_buttons': None,
                'unaccounted': unaccounted,
                'images': None,
                'card_data': None,
                'buttons': None
                }
    try:
        db_param = await connectors.get_db_param(db_type)
        conn = await connectors.get_connector(db_type, **db_param)

    except Exception as e:
        answer = "Can't connect to DataBase: {}. " \
                 "Please contact your system administrator".format(e)
        return {'answer': answer,
                'answer_type': 'text',
                'addition_buttons': None,
                'unaccounted': unaccounted,
                'images': None,
                'card_data': None,
                'buttons': None
                }
    else:
        if data_type == "message":
            result_el_1 = ''
            result_el_2 = ''
            if sql:
                result = await connectors.do_query_formatting(db_type, conn, sql)
                # Close db connection
                if db_type in ['mssql', 'postgresql']:
                    await conn.close()
                else:
                    conn.close()
            else:
                # hint message
                return {'answer': message,
                        'answer_type': 'text',
                        'addition_buttons': None,
                        'unaccounted': unaccounted,
                        'images': None,
                        'card_data': None,
                        'buttons': None
                        }

            if not result or None in result[0] or 0 in result[0]:
                answer = message.get('fail', '')

                return {'answer': answer,
                        'answer_type': 'text',
                        'addition_buttons': None,
                        'unaccounted': unaccounted,
                        'images': None,
                        'card_data': None,
                        'buttons': None
                        }

            else:
                report_and_hint = message.get('report_and_hint', None)
                message = message.get('success', '')
                if len(result) == 1 and not ('{result_el_1}' in message and '{result_el_2}' in message):
                    result = result[0]

                if type(result[0]) == datetime.date:
                    result = str(result[0])
                elif '{result_el_1}' in message and '{result_el_2}' in message:
                    if len(result) > 50:
                        result = result[:50]
                        message = "First 50 " + message
                    result_el_1 = [str(i[0]) for i in result]
                    result_el_2 = [str(round(i[1], 2)) for i in result]
                    result_el_1 = ", ".join(result_el_1)
                    result_el_2 = ", ".join(result_el_2)
                elif len(result) > 1:
                    if len(result) > 50:
                        result = result[:50]
                        message = "First 50 " + message
                    if '*{result_el}*' not in message:
                        # '*{result_el}*' means that each answer comes with a corresponding argument
                        result = ", ".join(str(i[0]) if type(i) == list or type(i) == tuple else str(i) for i in result)

                elif type(result[0]) == str:
                    result = result[0]
                else:
                    result = str(round(result[0], 2))

                if result_el_1 and result_el_2:
                    answer = message.replace('{result_el_1}', result_el_1).replace('{result_el_2}', result_el_2)
                else:
                    if '*{result_el}*' in message:
                        async for el in words(result):
                            if type(el) == list or type(el) == tuple:
                                res_el = str(el[0])
                            else:
                                res_el = str(el)
                            message = message.replace('{result_el}', res_el, 1)
                    else:
                        message = message.replace('{result}', result)
                    answer = message
                if report_and_hint:
                    report_and_hint = await create_addition_buttons(report_and_hint["buttons"], '0')
                return {'answer': answer,
                        'answer_type': 'text',
                        'addition_buttons': report_and_hint,
                        'unaccounted': unaccounted,
                        'images': None,
                        'card_data': None,
                        'buttons': None
                        }

        elif data_type in ["graph", "map", "bar", "bubble", "pie", "graph-complex", "bar-stacked", "bar-grouped",
                           "scatter", "scatter-complex", "bubble-complex"]:
            map_mode = True if data_type == "map" else False
            stacked_bar_mod = True if data_type in ["bar-stacked", "bar-grouped"] else False

            if data_type in ["graph-complex", "scatter-complex", "bubble-complex"]:
                # Check message is for next graph or empty the elements list.
                if text.replace(" ", "") != previous_add_btn.replace(" ", "") and list_of_elements:
                    list_of_elements = []
                # Populate list of elements if it doesn't already contain elements
                if not list_of_elements:
                    list_of_elements = await connectors.do_query(db_type, conn, sql.get('sql-get-elements'))
                if not list_of_elements or (type(list_of_elements) != dict and None in list_of_elements[0]):
                    result = []
                else:
                    result = {}
                    sql = sql.get('sql-final')
                    if db_type == "mssql":
                        escape_rule = "'"
                    else:
                        escape_rule = "\\"
                    _special_chars_map = {i: escape_rule + chr(i) for i in b"'"}
                    if data_type in ["graph-complex", "scatter-complex", "bubble-complex"]:
                        # Get first 10 elements from list
                        filtered_elements = list_of_elements[graph_range-10:graph_range]
                        # filtered_elements = list_of_elements[:graph_range]
                        # # Remove first 10 elements from list
                        # list_of_elements = list_of_elements[graph_range:]
                        # logging.info(f"Elements List: {list_of_elements}\n\n")
                        logging.info(f"Filtered List: {filtered_elements}\n\n")
                    else:
                        filtered_elements = list_of_elements
                        list_of_elements = []
                    for el in filtered_elements:
                        escaping_el = str(el[0]).translate(_special_chars_map)
                        result_element = await connectors.do_query(db_type, conn, sql.format(escaping_el),
                                                                   map_mode=map_mode)
                        if result_element and None not in result_element[0]:
                            result.update(dict({el[0]: result_element}))
            else:
                if type(sql) == dict:
                    result = {}
                    for i in sql:
                        result_element = await connectors.do_query(db_type, conn, sql.get(i), map_mode=map_mode)
                        if result_element and None not in result_element[0]:
                            result.update(dict({i: result_element}))
                else:
                    result = await connectors.do_query(db_type, conn, sql,
                                                       map_mode=map_mode, stacked_bar_mod=stacked_bar_mod)

            # Close db connection
            if db_type in ['mssql', 'postgresql']:
                await conn.close()
            else:
                conn.close()
            if not result or (type(result) != dict and None in result[0]):
                answer = message.get('fail', '')
                return {'answer': answer,
                        'answer_type': 'text',
                        'addition_buttons': None,
                        'unaccounted': unaccounted,
                        'images': None,
                        'card_data': None,
                        'buttons': None
                        }
            else:
                if addition_buttons:
                    # if data_type in ["graph-complex", "scatter-complex", "bubble-complex"] and list_of_elements:
                    #     if len(list_of_elements) > 10:
                    #         previous_add_btn = addition_buttons
                    #         n = 10
                    #     else:
                    #         n = len(list_of_elements)
                    #         previous_add_btn = addition_buttons
                    #     addition_buttons = await create_addition_buttons(addition_buttons, n)
                    if data_type in ["graph-complex", "scatter-complex", "bubble-complex"] and len(list_of_elements) > graph_range:
                        logging.info(f"Data-Type: {data_type}, Graph Range: {graph_range}\n\n")
                        addition_buttons = await create_addition_buttons(addition_buttons, '10')
                    elif (len(result) >= 20 and db_type not in ["bar-stacked", "bar-grouped"]) \
                            or (db_type in ["bar-stacked", "bar-grouped"]
                                and len(result.get('column2')) >= 20):
                        addition_buttons = await create_addition_buttons(addition_buttons)
                    else:
                        addition_buttons = None
                else:
                    addition_buttons = None

                if data_type in ["graph", "map", "graph-complex", "scatter-complex", "scatter", "bubble-complex",
                                 "bubble"]:
                    if data_type == "map":
                        name_html, name_jpg = graph.build_html_map(result, message.get('title', ''),
                                                                   colorbar_title=message.get('Oy', ''),
                                                                   locationmode=message.get('format', 'country names'))
                    elif data_type in ["scatter-complex", "scatter"]:
                        name_html, name_jpg = graph.build_html_chart(result, message.get('title', ''),
                                                                     Oy=message.get('Oy', ''),
                                                                     Ox=message.get('Ox', ''), mode="markers")
                    elif data_type in ["bubble-complex", "bubble"]:
                        name_html, name_jpg = graph.build_html_chart(result, message.get('title', ''),
                                                                     Oy=message.get('Oy', ''),
                                                                     Ox=message.get('Ox', ''), mode="markers",
                                                                     bubbles=True)
                    else:
                        name_html, name_jpg = graph.build_html_chart(result, message.get('title', ''),
                                                                     Oy=message.get('Oy', ''), Ox='Date')
                    url = '{}/bot/static/{}'.format(os.getenv('StaticEndPoint'), name_html)
                    img_url = '{}/bot/static/{}'.format(os.getenv('StaticEndPoint'), name_jpg)
                    return {'answer': 'Your chart',
                            'answer_type': 'hero_card',
                            'buttons': [{'type': ActionTypes.open_url, 'title': 'Open Chart', 'value': url}],
                            'images': [{'img_url': img_url}],
                            'addition_buttons': addition_buttons,
                            'card_data': None,
                            'unaccounted': unaccounted
                            }
                elif data_type == 'pie':
                    name_html, name_jpg = graph.build_html_pie(result, message.get('title', ''))
                    url = '{}/bot/static/{}'.format(os.getenv('StaticEndPoint'), name_html)
                    img_url = '{}/bot/static/{}'.format(os.getenv('StaticEndPoint'), name_jpg)
                    return {'answer': 'Your chart',
                            'answer_type': 'hero_card',
                            'buttons': [{'type': ActionTypes.open_url, 'title': 'Open Chart', 'value': url}],
                            'images': [{'img_url': img_url}],
                            'addition_buttons': addition_buttons,
                            'card_data': None,
                            'unaccounted': unaccounted
                            }
                else:
                    # data_type is 'bar' or 'bar-stacked' or "bar-grouped"
                    barmode = {"bar-stacked": "relative", "bar-grouped": "group"}
                    name_html, name_jpg = graph.build_html_bar(result, message.get('title', ''),
                                                               Oy=message.get('Oy', ''), Ox=message.get('Ox', ''),
                                                               barmode=barmode.get(data_type, False))
                    url = '{}/bot/static/{}'.format(os.getenv('StaticEndPoint'), name_html)
                    img_url = '{}/bot/static/{}'.format(os.getenv('StaticEndPoint'), name_jpg)
                    return {'answer': 'Your chart',
                            'answer_type': 'hero_card',
                            'buttons': [{'type': ActionTypes.open_url, 'title': 'Open Chart', 'value': url}],
                            'images': [{'img_url': img_url}],
                            'addition_buttons': addition_buttons,
                            'card_data': None,
                            'unaccounted': unaccounted
                            }

        elif data_type == 'buttons':
            if system_buttons:
                answer = system_buttons[2]
                buttons = await create_system_buttons(system_buttons, channel_id)
                return {'answer': answer,
                        'answer_type': 'hero_card',
                        'buttons': buttons,
                        'images': None,
                        'addition_buttons': None,
                        'card_data': None,
                        'unaccounted': unaccounted
                        }

            else:
                buttons = await create_complex_buttons(message, channel_id)
                return {'answer': 'A few options are found, please choose what you need',
                        'answer_type': 'hero_card',
                        'buttons': buttons,
                        'images': None,
                        'addition_buttons': None,
                        'card_data': None,
                        'unaccounted': unaccounted
                        }
        elif data_type in ['arg_buttons', 'column_name_buttons']:
            buttons = await create_arg_buttons(message, channel_id, data_type=data_type)
            return {'answer': 'A few options are found, please choose what you need',
                    'answer_type': 'hero_card',
                    'buttons': buttons,
                    'images': None,
                    'addition_buttons': None,
                    'card_data': None,
                    'unaccounted': unaccounted
                    }
        elif data_type == 'report':
            result = await connectors.do_query_formatting(db_type, conn, sql)
            # Close db connection
            if db_type in ['mssql', 'postgresql']:
                await conn.close()
            else:
                conn.close()
            if result:
                if message:
                    msg_success = message.get('success', '')
                else:
                    msg_success = ''
                # Send table in message for not bulk result, else send csv
                if len(result) < 10 and len(result[0]) <= 5:
                    indicator = indicator.get('columns', '')
                    card_data = await create_adaptive_card_attachment(result, msg_success, indicator)

                    return {'answer_type': 'adaptive_card',
                            'answer': msg_success,
                            'card_data': card_data,
                            'unaccounted': unaccounted,
                            'images': None,
                            'addition_buttons': None,
                            'buttons': None
                            }
                else:
                    # if not indicator.get('columns', ''), than get columns name - select pg_get_cols('tablename');
                    # get table name from indicator.get('table', '')
                    msg_success = msg_success if msg_success else 'Your file'
                    if not indicator.get('columns', ''):
                        indicator = ''
                    else:
                        indicator = indicator.get('columns', '')
                    file_name = 'file_' + ''.join([random.choice(list('123456789qwertyuiopasdfghjklzxc'
                                                                      'vbnmQWERTYUIOPASDFGHJKLZXCVBNM')) for x in
                                                   range(8)])
                    iPath = '/var/www/html/bot/static/{}.csv'.format(file_name)

                    await write_csv(result, iPath, 'a', indicator)
                    url = '{}/bot/static/{}.csv'.format(os.getenv('StaticEndPoint'), file_name)
                    return {'answer': msg_success,
                            'answer_type': 'hero_card',
                            'buttons': [{'type': ActionTypes.open_url, 'title': 'Open', 'value': url}],
                            'addition_buttons': None,
                            'images': None,
                            'card_data': None,
                            'unaccounted': unaccounted
                            }
            else:
                answer = message.get('fail', 'Can\'t get any answer')
                return {'answer': answer,
                        'answer_type': 'text',
                        'addition_buttons': None,
                        'unaccounted': unaccounted,
                        'images': None,
                        'card_data': None,
                        'buttons': None
                        }
        else:
            # Error message

            return {'answer': message,
                    'answer_type': 'text',
                    'addition_buttons': None,
                    'unaccounted': unaccounted,
                    'images': None,
                    'card_data': None,
                    'buttons': None
                    }


# NLSQL-API connection
async def api_post(message):
    url = os.getenv('ApiEndPoint')
    payload = {"message": message}
    # nlsql api token
    headers = {'Authorization': 'Token ' + os.getenv('ApiToken'),
               "Content-Type": "application/json"}
    result = requests.post(url, headers=headers, json=payload).json()
    return result


# for async cycle enumerate
async def words_for_check(word):
    for i in range(len(word)):
        yield i, word[i]


# for async cycle
async def words(word):
    for i in range(len(word)):
        yield word[i]


async def write_csv(data, path, mod, indicator=None):
    if mod == 'add':
        use_mod = 'a'
    else:
        use_mod = 'w'

    with open(path, use_mod, newline='') as f:
        writer0 = csv.writer(f, delimiter=',')
        if indicator:
            writer0.writerow((indicator))
        async for i in words(data):
            writer0.writerow((i))
