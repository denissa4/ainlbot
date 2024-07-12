import requests
import os
import sys
import asyncio
import pandas as pd
import numpy as np
from scipy.interpolate import UnivariateSpline
from datetime import datetime
import logging

import openai as ai
import markdown

import plotly.graph_objects as go
from io import BytesIO

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

# Add the parent directory of 'nlsql' to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from nlsql.handler import api_post
from nlsql.connectors import connectors


# Email configuration
EMAIL_ADDRESS = os.getenv('EmailAddress', '')
EMAIL_PASSWORD = os.getenv('EmailPassword', '') # User must create app password for gmail/outlook 2FA account
RECIPIENT_EMAIL = os.getenv('RecipientEmail', '')

corridors_mode = int(os.getenv('CorridorsMode', '1')) # Get user's corridors settings, 1 = Standard mode, 2 = Seasonal mode


def get_table_data():
    '''Function to retrieve the users data sources and table data.'''
    try:
        headers = {
            "Authorization": 'Token ' + os.getenv("ApiToken")
        }

        # Request DataSource names
        url = "https://api.nlsql.com/v1/data-source/"
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data_sources = response.json()

        # Append DataSource names to a list
        datasource_names = []
        for data_source in data_sources:
            datasource_names.append(data_source['name'])

    except requests.RequestException as e:
        logging.error(f"Failed to retrieve datasource names: {e}")
        return []
    
    try: 
        base_url = "https://api.nlsql.com/v1/data-source/"

        # Loop DataSource names and request table names, kpi args and filters.
        table_data = {}
        for name in datasource_names:
            response = requests.get(base_url + name, headers=headers)
            response.raise_for_status()
            data = response.json()['tables']
            table_data[name] = []
            for table in data:
                table_data[name].append({
                    'name': table['table_name'], 
                    'kpis': [arg['argument'] for column in table['columns'] for arg in column['column_other_params']['arguments'] if column['column_other_params']['arguments']],
                    'filters': [arg['argument'] for column in table['columns'] for arg in column['column_other_params']['filters'] if column['column_other_params']['filters']]
                })
        return table_data
    
    except requests.RequestException as e:
        logging.error(f"Failed to retrieve table data for {name}: {e}")
        return {}


async def send_nl_prompt(kpi_arg, fltr=''):
    '''Function to get relevant SQL queries from the NLSQL bot
        Returns: 
            - list of SQL queries for trusted data
            - string of SQL query for comparison data'''
    try:
        from_year = int(os.getenv('FromYear'))
        to_year = int(os.getenv('ToYear'))
        override = False # Override for corridors settings if user does not provide enough data for setting 2

        if corridors_mode == 2 and to_year - from_year < 2:
            logging.error("You must have at least 2 full years' of trusted data to use seasonal corridors mode. Defulting to standard mode.")
            override = True

        queries = []
        if corridors_mode == 2 and not override:
            # Gather the NL messages for each year
            year = from_year
            messages = []
            while year <= to_year:
                if fltr:
                    message = f'{kpi_arg} in {year} by month for {fltr}'
                else:
                    message = f'{kpi_arg} in {year} by month'
                messages.append(message)
                logging.info(message)
                year += 1
            # Send messages and gather relevant SQL queries
            responses = await asyncio.gather(*(api_post(msg) for msg in messages))
            if not responses or not responses[0]['sql']:
                logging.error(f'Unable to form SQL query for this KPI: {kpi_arg}')
            logging.info(f'\n\nResponses: \n\n{responses}\n\n\n')

            queries = [response['sql'] for response in responses if 'SUM' in response['sql'] or 'AVG' in response['sql']]

        elif corridors_mode == 1 or override:
            # If corridors_mode == 1
            if fltr:
                message = f'{kpi_arg} between {from_year} and {to_year} by month for {fltr}'
            else:
                message = f'{kpi_arg} between {from_year} and {to_year} by month'
            response = await api_post(message)

            if response and 'sql' in response and ('SUM' in response['sql'] or 'AVG' in response['sql']):
                queries = [response['sql']]
        
        # Get SQL for comparison data
        current_year = datetime.now().year
        from_year = current_year - 1
        if fltr:
            message = f'{kpi_arg} between {from_year} and {current_year} by month for {fltr}'
        else:
            message = f'{kpi_arg} between {from_year} and {current_year} by month'
        response = await api_post(message)
        comparison_query = response['sql']

        logging.info(f'\n\nYEARS:\n\n{current_year}\n\n{from_year}\n\n\n')

        logging.info(f'\n\nNL Message: \n\n{message}\n\n\n')
        logging.info(f"\n\nResponse: \n\n{response['sql']}\n\n\n")

        return queries, comparison_query
    
    except Exception as e:
        logging.error(f'An error occured in send_nl_prompt(): {e}')
        return None, None


def clean_dataframe(df):
    if corridors_mode == 1:
        # Ensure DataFrame has all months, 1 to 12
        all_months = pd.DataFrame({'month': range(1, 13)})
        df = pd.merge(all_months, df, on='month', how='left')
    else:
        df['month'] = df['month'].astype(int)
    df['value'] = df['value'].astype('float') # Ensure the 'value' column is float
    return df


def calculate_corridors(df, window_size=3):
    '''Function to calculate the upper and lower bounds for anomaly detection
       - if corridors_mode == 2 returns a nested list of lower and upper bounds for each month
       - if corridors_mode == 1 returns a list containing lower and upper boundaries'''
    try:
        # Get user's settings
        boundary_sensitivity = float(os.getenv('BoundarySensitivity', '2.0'))

        if corridors_mode == 2:
            # Group by month and calculate the mean and std value
            monthly_stats = df.groupby('month')['value'].agg(['mean', 'std']).reset_index()

            logging.info(f'\n\nmonthly stats df: \n\n {monthly_stats}\n\n\n')

            # Add padding wrap-around for edge cases
            previous_december = monthly_stats.iloc[-1:].copy()
            previous_december['month'] = 0
            next_january = monthly_stats.iloc[:1].copy()
            next_january['month'] = 13
            
            padded_stats = pd.concat([previous_december, monthly_stats, next_january]).reset_index(drop=True)
            
            logging.info(f'\n\npadded stats df: \n\n {padded_stats}\n\n\n')

            # Calculate rolling mean and standard deviation
            padded_stats['rolling_mean'] = padded_stats['mean'].rolling(window=window_size, center=True, min_periods=1).mean()
            padded_stats['rolling_std'] = padded_stats['mean'].rolling(window=window_size, center=True, min_periods=1).std()

            logging.info(f'\n\nrolling stats df: \n\n {padded_stats}\n\n\n')

            padded_stats['lower_bound'] = padded_stats['rolling_mean'] - boundary_sensitivity * padded_stats['rolling_std']
            padded_stats['upper_bound'] = padded_stats['rolling_mean'] + boundary_sensitivity * padded_stats['rolling_std']

            # Smooth the upper and lower bounds using UnivariateSpline
            x = padded_stats['month'].values
            y_lower = padded_stats['lower_bound'].values
            y_upper = padded_stats['upper_bound'].values
            lower_spline = UnivariateSpline(x, y_lower, k=3, s=None)
            upper_spline = UnivariateSpline(x, y_upper, k=3, s=None)

            # Remove padding rows
            padded_stats = padded_stats[(padded_stats['month'] >= 1) & (padded_stats['month'] <= 12)].reset_index(drop=True)

            # Replace the lower and upper bounds with the smoothed values
            padded_stats['lower_bound'] = lower_spline(padded_stats['month'])
            padded_stats['upper_bound'] = upper_spline(padded_stats['month'])

            # Create a nested list with the bounds for each month
            anomaly_bounds = padded_stats[['lower_bound', 'upper_bound']].values.tolist()

            return anomaly_bounds

        # Calculate mean and standard deviation
        mean_value = df['value'].mean()
        std_value = df['value'].std()
        
        # Define corridors as ±boundary_sensitivity (default 2) standard deviations from the mean
        lower_bound = mean_value - boundary_sensitivity * std_value
        upper_bound = mean_value + boundary_sensitivity * std_value
        
        return [lower_bound, upper_bound]
    
    except Exception as e:
        logging.error(f'Failed to calculate corridors: {e}')
        return []


def detect_anomalies(df, corridors):
    try:
        if corridors_mode == 2:
            outliers = []
            for index, row in df.iterrows():
                month = int(row['month']) - 1  # Adjusting month to 0-index for list access
                value = row['value']
                lower_bound, upper_bound = corridors[month]
                if value < lower_bound or value > upper_bound:
                    outliers.append(row)  # Append the entire row to outliers
        
            anomalies = pd.DataFrame(outliers, columns=df.columns)  # Create a DataFrame from outliers list
            return anomalies
        else:
            anomalies = df[(df['value'] < corridors[0]) | (df['value'] > corridors[1])]
            return anomalies
    
    except Exception as e:
        logging.error(f'An error occurred in detect_anomalies: {e}')
        return pd.DataFrame()


def calculate_monthly_averages(df):
    '''Function to calculate the average 'value' for each month'''
    try:
        # Ensure 'month' column is present and correctly formatted
        if 'month' not in df.columns:
            df['month'] = df.index.month
        # Calculate the average 'value' for each month (1 to 12)
        monthly_averages = df.groupby('month')['value'].mean().reset_index()
        # Rename columns for clarity
        monthly_averages.columns = ['month', 'value']
        return monthly_averages
    
    except Exception as e:
        logging.info(f'Failed to calculate monthly averages: {e}')
        return pd.DataFrame()  # Return an empty DataFrame in case of error


async def get_response_openai(system_message, messages):
    try:
        ai.api_key = os.getenv('OpenAiAPI')
        ai.api_base = os.getenv('OpenAiBase')
        ai.api_type = os.getenv('OpenAiType')
        ai.api_version = os.getenv('OpenAiVersion')
        deployment_name = os.getenv('OpenAiName')
        
        response = await ai.ChatCompletion.acreate(
            engine=deployment_name,
            messages=create_prompt_openai(system_message, messages),
            temperature=0.5,
            max_tokens=800,
            top_p=0.95,
            frequency_penalty=0,
            presence_penalty=0,
            stop=None
        )
        return response
    except:
        logging.error("There was a problem with OpenAI")
        return "There was a problem generating OpenAI analysis."


def create_prompt_openai(system_content, user_content):
    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_content}
    ]
    return messages


def generate_graph(trusted_df, comparison_df, anomalies, corridors, kpi, fltr=''):
    try:
        to_year = int(os.getenv('ToYear'))
        from_year = int(os.getenv('FromYear'))

        # Interpolate missing values in DataFrames
        trusted_df = trusted_df.interpolate(method='linear')
        comparison_df = comparison_df.interpolate(method='linear')

        # Generate a graph reflecting trusted data and anomalous data
        x = trusted_df['month'].tolist()
        x_rev = x[::-1]

        y1 = trusted_df['value'].tolist()
        y2 = comparison_df['value'].tolist()
        anomaly_points = comparison_df[comparison_df['value'].isin(anomalies['value'])]

        if corridors_mode == 2:
            lower_bound_list = [bound[0] for bound in corridors]
            upper_bound_list = [bound[1] for bound in corridors]
        else:
            lower_bound_list = [corridors[0]] * len(x)
            upper_bound_list = [corridors[1]] * len(x)
        lower_bound_rev = lower_bound_list[::-1]

        fig = go.Figure()

        # Shaded area for trusted corridors
        fig.add_trace(go.Scatter(
            x=x + x_rev, y=upper_bound_list + lower_bound_rev,
            fill='toself',
            fillcolor='rgba(48, 110, 134, 0.2)',
            line_color='rgba(255,255,255,0)',
            name='Upper & lower bounds',
        ))

        # Trusted line
        fig.add_trace(go.Scatter(
            x=x, y=y1,
            line_color='rgb(0,100,80)',
            name=f'{kpi} ({from_year} - {to_year})',
            mode='lines',
            line={'dash': 'dash'}
        ))

        # Comparison line
        fig.add_trace(go.Scatter(
            x=x, y=y2,
            line_color='rgb(0,176,246)',
            name=f"{kpi} ({datetime.now().year - 1} - Present)",
        ))

        # Anomaly points
        fig.add_trace(go.Scatter(
            x=anomaly_points['month'], y=anomaly_points['value'],
            mode='markers',
            marker=dict(color='red', size=10),
            name='Anomalies',
        ))

        timeframe = datetime.now().year - 1

        fig.update_layout(
            title = f"{kpi.title()} from {timeframe} to Present" if not fltr else f"{kpi.title()} filtered by {fltr}, from {timeframe} to Present",
            xaxis_title="Month",
            yaxis_title="Value",
            legend_title="Legend",
            template="plotly_white"
        )

        img_buf = BytesIO()
        fig.write_image(img_buf, format='png')
        img_buf.seek(0)

        try:
            # Save the figure as an HTML file
            app_name = os.getenv('StaticEndPoint')
            file_name = f"pio_{kpi}_{datetime.now().strftime('%Y%m%d%H%M%S')}.html"
            file_path = '/var/www/html/bot/static/{}'.format(file_name)
            fig.write_html(file_path)

            url = '{}/bot/static/{}'.format(app_name, file_name)
            return img_buf, url
        
        except Exception as e:
            logging.error(f"Failed to generate URL: {e}")
            return img_buf, None
    
    except Exception as e:
        logging.error(f"Error in generate_graph: {e}")
        return None, None


async def gather_anomaly_data(data_source, table, kpi, fltr, trusted_sql, comparison_sql, db, conn):
    '''Function to gather all anomaly data, response messages and graphs'''
    try:

        if corridors_mode == 2:
            trusted_results = []
            for query in trusted_sql:
                result = await connectors.do_query(db, conn, query)
                trusted_results.extend(result)
        else:
            logging.info(f'Trusted SQL (Indexed):\n\n{trusted_sql[0]}')
            trusted_results = await connectors.do_query(db, conn, trusted_sql[0])
        comparison_results = await connectors.do_query(db, conn, comparison_sql)

        logging.info(f'\n\nTrusted Results: \n\n{trusted_results}\n\n\n Comparison Results: \n\n{comparison_results}\n\n\n')

        # Create trusted and comparison dataframes
        trusted_df = pd.DataFrame(trusted_results, columns=["value", "month"])
        comparison_df = pd.DataFrame(comparison_results, columns=["value", "month"])

        # Clean data in DataFrames
        trusted_df = clean_dataframe(trusted_df)
        comparison_df = clean_dataframe(comparison_df)

        logging.info(f'\n\nTrusted DF: \n\n{trusted_df}\n\n\n Comparison DF: \n\n{comparison_df}\n\n\n')

        # Calculate the corridors using trusted dataframe
        corridors = calculate_corridors(trusted_df)
        if not corridors:
            logging.error('calculate_corridors() has returned a null value')
            return None
        
        logging.info(f'\n\nCorridors: \n\n{corridors}\n\n\n')

        if corridors_mode == 2:
            trusted_df = calculate_monthly_averages(trusted_df)

        # Look for anomalies in comparison data
        anomalies = detect_anomalies(comparison_df, corridors)
        if anomalies.empty:
            logging.error('detect_anomalies() has returned a null value')
            return None
        
        logging.info(f'\n\nAnomalies: \n\n{anomalies}\n\n\n')

        # Generate prompt and send to GPT
        system_message = os.getenv('SystemMessage', 'You are an intelligent data analyzer who will be given trusted data and comparison data. You must give potential reasons to why anomalies are detected in the data based on their KPI names.')
        if fltr:
            user_message = f"KPI: {kpi}, Filtered by: {fltr}, Trusted Data: {trusted_df}, Comparison Data: {comparison_df}, Anomalies Detected: {anomalies}, Sensetivity: {os.getenv('BoundarySensetivity' '2.0')}"
        else:
            user_message = f"KPI: {kpi}, Trusted Data: {trusted_df}, Comparison Data: {comparison_df}, Anomalies Detected: {anomalies}, Sensetivity: {os.getenv('BoundarySensetivity' '2.0')}"

        # Get GPT response message
        response = await get_response_openai(system_message, user_message)
        gpt_message = response['choices'][0]['message']['content']

        # Generate graph image and URL
        graph, url = generate_graph(trusted_df, comparison_df, anomalies, corridors, kpi, fltr)
        if graph:
            if url:
                logging.info('Graph and URL successfully generated.')
            else:
                logging.info('Graph has been successfully generated but there was a problem generating the URL.')

        # Create hearder message for anomaly report
        if fltr:
            header_message = f'There are anomalies with <b>{kpi}</b>, filtered by <b>{fltr}</b> in the table <b>{table["name"]}</b>. DataSource: <b>{data_source}</b>'
        else:
            header_message = f'There are anomalies with <b>{kpi}</b> in the table <b>{table["name"]}</b>. DataSource: <b>{data_source}</b>'

        # Return all anomaly data (Header message, GPT response, Graph, URL)
        anomaly_data = (header_message,
                        gpt_message,
                        graph,
                        url)
        return anomaly_data

    except Exception as e:
        logging.error(f'An error occured in gather_anomaly_data(): {e}')
        return None               


async def perform_anomaly_check():
    '''Function to loop all tables, KPIs and filters and gather anomaly data'''
    try:
        # Get data for checks (datasources, table names, KPI args and filters)
        table_data = get_table_data()

        # Create a connection to the user's database
        db = os.getenv('DatabaseType', 'postgresql').lower()
        db_params = await connectors.get_db_param(db)
        conn = await connectors.get_connector(db, **db_params)
        if conn:
            logging.info("Successfully connected to database.")

        # Loop through the KPI arguments
        anomaly_messages = []
        searched_tables = []
        for data_source, tables in table_data.items():
            for table in tables:
                for kpi in table['kpis']:
                    # Collect the SQL queries for trusted and comparison data
                    trusted_sql, comparison_sql = await send_nl_prompt(kpi)
                    if not trusted_sql or not comparison_sql:
                        continue
                    logging.info(f'\n\nTrusted SQL:\n\n{trusted_sql}')
                    logging.info(f'\n\nComparison SQL:\n\n{comparison_sql}')
                    # Query databases, perform checks and gather responses
                    responses = await gather_anomaly_data(data_source, table, kpi, None, trusted_sql, comparison_sql, db, conn)
                    anomaly_messages.append(responses)
                    if table['filters']:
                        for fltr in table['filters']:
                            trusted_sql, comparison_sql = await send_nl_prompt(kpi, fltr)
                            if not trusted_sql or not comparison_sql:
                                continue
                            logging.info(f'\n\nTrusted SQL:\n\n{trusted_sql}')
                            logging.info(f'\n\nComparison SQL:\n\n{comparison_sql}')
                            responses = await gather_anomaly_data(data_source, table, kpi, fltr, trusted_sql, comparison_sql, db, conn)
                            anomaly_messages.append(responses)

                if table['name'] not in searched_tables:
                    searched_tables.append(table['name'])
        
        # Send email to user
        if EMAIL_ADDRESS and EMAIL_PASSWORD and RECIPIENT_EMAIL:
            send_email(anomaly_messages, searched_tables)
        else:
            logging.warning("Email credentials missing")
        return

    except Exception as e:
        logging.error(f'Failed to perform anomaly check: {e}')
        return
    
    finally:
        if conn:
            conn.close()    


def send_email(anomaly_messages, tables):
    '''Function to prepare message and send email to user'''
    logging.info(f"Anomaly messages: {anomaly_messages}, Tables: {tables}")
    try:
        msg = MIMEMultipart()
        msg['Subject'] = "Anomaly Detection Report"
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = RECIPIENT_EMAIL

        if all(msg is None for msg in anomaly_messages):
            html_content = "<h1>Everything looks good,</h1>"
            html_content += "<h2>an anomaly check has been conducted and no anomalies were found.</h2>"
        else:
            n = 1 # n - for giving a unique name to graph images
            html_content = "<h1>Anomaly Detection Report</h1>"
            for message in anomaly_messages:
                if message is None:
                    continue
                # Add image to email
                img_data = message[2].getvalue()
                img = MIMEImage(img_data, 'png')
                img.add_header('Content-ID', f'<anomaly_graph_{n}>')  # Content-ID for inline images
                img.add_header('Content-Disposition', 'inline', filename=f'anomaly_graph_{n}.png')
                msg.attach(img)
                html_content += f"<img src='cid:anomaly_graph_{n}'><br>"
                html_content += f"<a href='{message[3]}'>Open Interactive Graph</a><br>"
                # Add text to email
                html_content += "<h2>"
                html_content += f"{message[0]}"
                html_content += "</h2><br>"
                html_content += "<p>"
                html_content += f"{markdown.markdown(message[1])}"
                html_content += "</p><br>"
                n += 1

        html_content += "<ul>Tables Searched:"
        for table in tables:
            html_content += f"<li>{table}</li>"
        html_content += "</ul>"

        # Add HTML content to email
        msg.attach(MIMEText(html_content, 'html'))

        # Send email using SMTP
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            smtp.send_message(msg)
            logging.info("Email successfully sent")

    except Exception as e:
        logging.error(f"Failed to send email: {e}")


async def main():
    # Script will run in background with asyncio and repeat as per user's "Frequency" (in days) environment variable (86400 = 1 day) 
    while True:
        days = int(os.getenv('Frequency', '1'))
        try:
            await perform_anomaly_check()
            await asyncio.sleep(86400 * days) # Repeat every n days
        except asyncio.CancelledError:
            break
        except Exception as e:
            logging.error(f"Error in main loop: {e}")
            await asyncio.sleep(86400 * days)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())