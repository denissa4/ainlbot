import os
import asyncio
import ssl
import struct
from decimal import Decimal
from typing import Dict, List, Union

import snowflake.connector
import redshift_connector
import aioodbc
import aiomysql
import aiopg
from google.cloud import bigquery
from google.oauth2 import service_account
from azure.identity import DefaultAzureCredential

DEBUG = True if os.getenv('DEBUG', '') == '1' else False


async def get_ad_token(kwargs: Dict, url="https://database.windows.net/.default") -> str:
    # Set up Azure Active Directory authentication
    if kwargs['ClientIdOfUserAssignedIdentity']:
        credential = DefaultAzureCredential(
            managed_identity_client_id=kwargs['ClientIdOfUserAssignedIdentity'])  # user-assigned identity
    else:
        if DEBUG:
            print("get credential")
        credential = DefaultAzureCredential()  # system-assigned identity
        if DEBUG:
            print(f"credential={credential}")

    # Get the access token for Azure SQL
    if DEBUG:
        print("get token")
    token = credential.get_token(url)
    if DEBUG:
        print(f"token={token}")
    token = token.token
    return token


async def get_connector(db, **kwargs):
    conn = ''
    if db == 'snowflake':
        conn = snowflake.connector.connect(
            account=kwargs['Account'],
            warehouse=kwargs['Warehouse'],
            database=kwargs['DbName'],
            schema=kwargs['DbSchema'],
            user=kwargs['DbUser'],
            password=kwargs['DbPassword']
        )
    elif db == 'redshift':
        conn = redshift_connector.connect(
            host=kwargs['DataSource'],
            database=kwargs['DbName'],
            user=kwargs['DbUser'],
            password=kwargs['DbPassword'],
            client_protocol_version=1
        )
    elif db == 'mssql':
        driver = "{ODBC Driver 17 for SQL Server}"
        if DEBUG:
            print(f"{kwargs['ActiveDirectoryAuthentication']}")
            print(f"{kwargs['ClientIdOfUserAssignedIdentity']}")
        if kwargs['ActiveDirectoryAuthentication'] or kwargs['ClientIdOfUserAssignedIdentity']:
            token = await get_ad_token(kwargs)
            token = token.encode("UTF-16-LE")
            token_struct = struct.pack(f'<I{len(token)}s', len(token), token)

            # Set up the connection string
            SQL_COPT_SS_ACCESS_TOKEN = 1256
            connection_string = f"DRIVER={driver};SERVER={kwargs['DataSource']};DATABASE={kwargs['DbName']}"
            return await aioodbc.connect(dsn=connection_string, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct})

        conn = await aioodbc.connect(dsn='DRIVER={0};'
                                         'SERVER={1};'
                                         'DATABASE={2};'
                                         'UID={3};'
                                         'PWD={4}'.format(driver,
                                                          kwargs['DataSource'],
                                                          kwargs['DbName'],
                                                          kwargs['DbUser'],
                                                          kwargs['DbPassword']))
    elif db == 'mysql':
        if not kwargs['DbPort']:
            kwargs['DbPort'] = 3306
        if not kwargs['ssl'] or kwargs['ssl'].lower() != 'true':
            ssl_context = False
        else:
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)

        if kwargs['ActiveDirectoryAuthentication'] or kwargs['ClientIdOfUserAssignedIdentity']:
            token = await get_ad_token(kwargs, url="https://ossrdbms-aad.database.windows.net/.default")

            # Connect with the token
            os.environ['LIBMYSQL_ENABLE_CLEARTEXT_PLUGIN'] = '1'

            return await aiomysql.connect(host=kwargs['DataSource'],
                                          user=kwargs['DbUser'],
                                          password=token,
                                          db=kwargs['DbName'],
                                          port=int(kwargs['DbPort']),
                                          ssl=ssl_context)

        conn = await aiomysql.connect(host=kwargs['DataSource'],
                                      user=kwargs['DbUser'],
                                      password=kwargs['DbPassword'],
                                      db=kwargs['DbName'],
                                      port=int(kwargs['DbPort']),
                                      ssl=ssl_context)
    elif db == 'postgresql':
        if not kwargs['DbPort']:
            kwargs['DbPort'] = 5432
        if kwargs['ActiveDirectoryAuthentication'] or kwargs['ClientIdOfUserAssignedIdentity']:
            token = await get_ad_token(kwargs, url="https://ossrdbms-aad.database.windows.net/.default")

            return await aiopg.connect(host=kwargs['DataSource'],
                                       user=kwargs['DbUser'],
                                       password=token,
                                       database=kwargs['DbName'],
                                       port=int(kwargs['DbPort']))

        conn = await aiopg.connect(host=kwargs['DataSource'],
                                   user=kwargs['DbUser'],
                                   password=kwargs['DbPassword'],
                                   database=kwargs['DbName'],
                                   port=int(kwargs['DbPort']))
    elif db == 'bigquery':
        if os.getenv('DEBUG', '') == '1':
            print(kwargs['private_key'])
        info = {
            "client_email": kwargs['client_email'],
            "token_uri": kwargs['token_uri'],
            "private_key": kwargs['private_key'].replace('\\n', '\n')
        }
        if os.getenv('DEBUG', '') == '1':
            print(info)
        credentials = service_account.Credentials.from_service_account_info(info)
        conn = bigquery.Client(credentials=credentials,
                               project=kwargs['project_id'])
    return conn


async def get_db_param(db: str) -> Dict:
    params = {}
    if db == 'snowflake':
        params = {
            'Account': os.getenv('DataSource', '') if os.getenv('DataSource', '') else os.getenv('Account', ''),
            'Warehouse': os.getenv('Warehouse', ''),
            'DbName': os.getenv('DbName', ''),
            'DbSchema': os.getenv('DbSchema', ''),
            'DbUser': os.getenv('DbUser', ''),
            'DbPassword': os.getenv('DbPassword', ''),
                  }
    elif db == 'redshift':
        params = {
            'DataSource': os.getenv('DataSource', ''),
            'DbName': os.getenv('DbName', ''),
            'DbUser': os.getenv('DbUser', ''),
            'DbPassword': os.getenv('DbPassword', '')
        }
    elif db == 'mssql':
        ActiveDirectoryAuthentication = os.getenv('ActiveDirectoryAuthentication', '')
        params = {
            'DataSource': os.getenv('DataSource', ''),
            'DbName': os.getenv('DbName', ''),
            'DbUser': os.getenv('DbUser', ''),
            'DbPassword': os.getenv('DbPassword', ''),
            'ActiveDirectoryAuthentication': True if ActiveDirectoryAuthentication in
                                                     (True, "true", "True", 1, "1",) else "",
            'ClientIdOfUserAssignedIdentity': os.getenv('ClientIdOfUserAssignedIdentity', ''),
        }
    elif db == 'mysql':
        ActiveDirectoryAuthentication = os.getenv('ActiveDirectoryAuthentication', '')
        params = {
            'DataSource': os.getenv('DataSource', ''),
            'DbName': os.getenv('DbName', ''),
            'DbUser': os.getenv('DbUser', ''),
            'DbPassword': os.getenv('DbPassword', ''),
            'DbPort': os.getenv('DbPort', 3306),
            'ssl': os.getenv('ssl', False),
            'ActiveDirectoryAuthentication': True if ActiveDirectoryAuthentication in
                                                     (True, "true", "True", 1, "1",) else "",
            'ClientIdOfUserAssignedIdentity': os.getenv('ClientIdOfUserAssignedIdentity', ''),
        }
    elif db == 'postgresql':
        ActiveDirectoryAuthentication = os.getenv('ActiveDirectoryAuthentication', '')
        params = {
            'DataSource': os.getenv('DataSource', ''),
            'DbName': os.getenv('DbName', ''),
            'DbUser': os.getenv('DbUser', ''),
            'DbPassword': os.getenv('DbPassword', ''),
            'DbPort': os.getenv('DbPort', 5432),
            'ActiveDirectoryAuthentication': True if ActiveDirectoryAuthentication in
                                                     (True, "true", "True", 1, "1",) else "",
            'ClientIdOfUserAssignedIdentity': os.getenv('ClientIdOfUserAssignedIdentity', ''),
        }
    elif db == 'bigquery':
        if os.getenv('DEBUG', '') == '1':
            print(os.getenv('private_key', ''))
        params = {
            'client_email': os.getenv('client_email', ''),
            'token_uri': os.getenv('token_uri', ''),
            'private_key': os.getenv('private_key', ''),
            'project_id': os.getenv('project_id', '')
        }
    return params


async def do_query(db, conn, sql, map_mode=False, stacked_bar_mod=False):

    if map_mode:
        result = {"country": [], "value": []}
    elif stacked_bar_mod:
        result = {}
    else:
        result = []

    if db in ['snowflake', 'redshift']:
        cursor = conn.cursor()
        cursor.execute(sql)
        value: list = cursor.fetchall()
        if stacked_bar_mod:
            async for ind in async_range(0, len(value[0])):
                result.update({f'column{ind + 1}': []})
        async for i in _words(value):
            if map_mode:
                result["country"].append(i[0])
                result["value"].append(i[1])
            elif stacked_bar_mod:
                async for ind in async_range(0, len(i)):
                    try:
                        result[f"column{ind + 1}"].append(i[ind])
                    except KeyError:
                        result.update({f'column{ind + 1}': []})
                        result[f"column{ind + 1}"].append(i[ind])
            else:
                result.append(i)
        cursor.close()
    elif db == 'bigquery':
        query_job = conn.query(sql)
        value: bigquery.table.RowIterator = query_job.result()
        if stacked_bar_mod:
            async for ind in async_range(0, len(value[0])):
                result.update({f'column{ind + 1}': []})
        for i in value:
            if map_mode:
                result["country"].append(i.values()[0])
                result["value"].append(i.values()[1])
            elif stacked_bar_mod:
                async for ind in async_range(0, len(i)):
                    try:
                        result[f"column{ind + 1}"].append(i[ind])
                    except KeyError:
                        result.update({f'column{ind + 1}': []})
                        result[f"column{ind + 1}"].append(i[ind])
            else:
                result.append(i.values())
    else:
        async with conn.cursor() as cursor:
            await cursor.execute(sql)
            value = await cursor.fetchall()
            if stacked_bar_mod:
                async for ind in async_range(0, len(value[0])):
                    result.update({f'column{ind + 1}': []})
            async for i in _words(value):
                if map_mode:
                    result["country"].append(i[0])
                    result["value"].append(i[1])
                elif stacked_bar_mod:
                    async for ind in async_range(0, len(i)):
                        try:
                            result[f"column{ind+1}"].append(i[ind])
                        except KeyError:
                            result.update({f'column{ind + 1}': []})
                            result[f"column{ind + 1}"].append(i[ind])
                else:
                    result.append(i)
            if db in ['postgresql']:
                cursor.close()
            elif db != 'mssql':
                await cursor.close()

    return result


# round to 2 numbers after . and finally convert response to a single format tuple str like: 1,000.02
async def do_query_formatting(db, conn, sql):
    if db in ['snowflake', 'redshift']:
        cursor = conn.cursor()
        cursor.execute(sql)
        value: List = cursor.fetchall()
        result = await _parse_cursor_response(value)
        cursor.close()
    elif db == 'bigquery':
        query_job = conn.query(sql)
        value: bigquery.table.RowIterator = query_job.result()
        result = await _parse_cursor_response(value)
    else:
        async with conn.cursor() as cursor:
            await cursor.execute(sql)
            value: List = await cursor.fetchall()
            result = await _parse_cursor_response(value)
            if db in ['postgresql']:
                cursor.close()
            elif db != 'mssql':
                await cursor.close()

    return result


# subfunction for do_query_formatting
async def _parse_cursor_response(value: Union[List, bigquery.table.RowIterator]) -> List:
    result = []
    if isinstance(value, bigquery.table.RowIterator):
        for i in value:
            await _parse_cursor_response_conditional(i, result)
        return result

    async for i in _words(value):
        await _parse_cursor_response_conditional(i, result)
    return result


# subfunction for _parse_cursor_response
async def _parse_cursor_response_conditional(i, result: List) -> List:
    if type(i) == tuple or type(i) == list or isinstance(i, bigquery.table.Row):
        result.append(tuple([await _formatting_number(el) async for el in _words(i)]))
    else:
        result.append(await _formatting_number(i))

    return result


async def _words(word):
    for i in range(len(word)):
        yield word[i]


async def async_range(start, length):
    for i in range(start, length):
        yield i


# input number and formating it like 1,000.02
async def _formatting_number(el):
    if type(el) == str and el.replace('.', '').isdigit():
        return f'{float(el):,.2f}'
    if type(el) == int or type(el) == float or type(el) == Decimal:
        return f'{el:,.2f}'
    return el
