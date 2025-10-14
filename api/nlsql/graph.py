import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import random
import numpy as np
import datetime
import matplotlib.ticker as ticker
import plotly.graph_objects as go
import plotly.io as pio
from itertools import groupby
import plotly.express as px


def save(name='', fmt='png'):
    import os

    pwd = os.getcwd()
    iPath = '/var/www/html/bot/static/'
    if not os.path.exists(iPath):
        os.mkdir(iPath)
    os.chdir(iPath)
    plt.savefig('{}.{}'.format(name, fmt), fmt='png')
    os.chdir(pwd)
    return name


def build(array, title, Oy, Ox):
    x = []
    y = []

    if Ox == 'Date':
        dates = []
        values = []
        fig, ax = plt.subplots()
        if type(array) == dict:
            for key in array:
                dates = []
                values = []
                for i in array.get(key):
                    if isinstance(i[0], datetime.date):
                        dates.append(i[0].strftime("%Y/%m/%d"))
                    else:
                        dates.append(i[0])
                    values.append(i[1])
                ax.plot(dates, values)
                ax.scatter(dates, values, s=10, marker='o', label=u'{}'.format(key))
                # plt.plot(x, y, label=u'{}'.format(i))
            plt.legend(frameon=True)
        else:
            for i in array:
                if isinstance(i[0], datetime.date):
                    dates.append(i[0].strftime("%Y/%m/%d"))
                else:
                    dates.append(i[0])
                values.append(i[1])
            # plt.plot_date(dates, values)
            ax.plot(dates, values)
            ax.scatter(dates, values, color='orange', s=30, marker='o')

        step = len(dates) // 12
        if step == 0:
            step = 1
        targets = np.arange(len(dates), step=step)
        new_dates = ['', ]
        for i in range(len(dates)):
            if i in targets:
                new_dates.append(dates[i])
            # else:
            #     new_dates.append(' ')
        plt.xticks(np.arange(len(dates)), new_dates, rotation=60, horizontalalignment='right', fontsize=12)
        ax.xaxis.set_major_locator(ticker.MultipleLocator(step))
        ax.xaxis.set_minor_locator(ticker.MultipleLocator(1))
        ax.grid(which='major', color='#D7D7D7', linestyle='--')
        ax.set_xlim([0, len(dates)])
    else:
        # for multi-graph {key: list}
        if type(array) == dict:
            for i in array:
                x = []
                y = []
                for j in array.get(i):
                    x.append(j[0])
                    y.append(j[1])
                plt.plot(x, y, label=u'{}'.format(i))

            plt.legend(frameon=True)

        else:
            for i in array:
                x.append(i[0])
                y.append(i[1])
            plt.plot(x, y)

    if Ox == 'Date':
        plt.subplots_adjust(left=0.175, top=0.85, bottom=0.26)
    else:
        plt.subplots_adjust(left=0.175, top=0.85)

    plt.grid(axis='y', linestyle='--', color='#D7D7D7')
    if len(title) > 60:
        import textwrap
        title = textwrap.fill(title, 50)
    plt.title(title)
    plt.ylabel(Oy)
    plt.xlabel(Ox)
    code_name = ''.join([random.choice(list('123456789qwertyuiopasdfghjklzxc'
                                            'vbnmQWERTYUIOPASDFGHJKLZXCVBNM')) for x in range(8)])
    name = save(name='pic_{}'.format(code_name), fmt='png')
    plt.close()
    return name


def build_bar(array, title):
    x = []
    y = []
    array.reverse()
    for i in array[:20]:
        x_value = i[1]
        x.append(x_value)
        y.append(i[0])
    y_pos = np.arange(len(y))
    fig, ax = plt.subplots()
    fig.subplots_adjust(left=0.275, top=0.85)
    ax.barh(y_pos, x, align='center', )
    plt.yticks(y_pos, y)
    ax.xaxis.grid(True, linestyle='--', which='major', color='grey', alpha=.25)
    if len(title) > 60:
        import textwrap
        title = textwrap.fill(title, 50)
    plt.title(title)
    plt.xlabel('Count')
    plt.ylabel('Material Number')
    code_name = ''.join([random.choice(list('123456789qwertyuiopasdfghjklzxc'
                                            'vbnmQWERTYUIOPASDFGHJKLZXCVBNM')) for x in range(8)])
    name = save(name='pic_{}'.format(code_name), fmt='png')
    plt.close()
    return name


def build_html_chart(array, title, Oy, Ox, mode='lines+markers', bubbles=False):
    """
    :param mode: available 'lines+markers' or 'markers'
    """
    x = []
    y = []
    fig = go.Figure()
    if Ox == 'Months':
        month = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
        if type(array) == dict:
            for i in array:
                data_year = array.get(i)
                x = []
                y = []
                if len(data_year) == 12:
                    for number in data_year:
                        x.append(number[0])
                        y.append(number[1])
                else:
                    counter = 0
                    for number in month:
                        try:
                            if number == data_year[counter][0]:
                                x.append(data_year[counter][0])
                                y.append(data_year[counter][1])
                                counter += 1
                            else:
                                x.append(number)
                                y.append(0)
                        except Exception:
                            x.append(number)
                            y.append(0)

                x = np.array(x)
                y = np.array(y)
                if bubbles:
                    fig.add_trace(go.Scatter(x=x, y=y, mode=mode, name=i,
                                             marker=dict(size=y, sizemode='area', sizeref=2. * max(y) / (40. ** 2),
                                                         sizemin=4)
                                             ))
                else:
                    fig.add_trace(go.Scatter(x=x, y=y, mode=mode, name=i))
        else:
            if len(array) == 12:
                for number in array:
                    x.append(number[0])
                    y.append(number[1])

            else:
                counter = 0
                for number in month:
                    try:
                        if number == array[counter][0]:
                            x.append(array[counter][0])
                            y.append(array[counter][1])
                            counter += 1
                        else:
                            x.append(number)
                            y.append(0)
                    except:
                        x.append(number)
                        y.append(0)
            x = np.array(x)
            y = np.array(y)
            if bubbles:
                fig.add_trace(go.Scatter(x=x, y=y, mode=mode, name='',
                                         marker=dict(size=y, sizemode='area', sizeref=2. * max(y) / (40. ** 2),
                                                     sizemin=4)
                                         ))
            else:
                fig.add_trace(go.Scatter(x=x, y=y, mode=mode, name=''))
    elif Ox == 'Date-Delta':
        dates = []
        values = []
        fig, ax = plt.subplots()
        if type(array) == dict:
            for key in array:
                dates = []
                values = []
                for i in array.get(key):
                    if isinstance(i[0], datetime.date):
                        dates.append(i[0].strftime("%Y/%m/%d"))
                    else:
                        dates.append(i[0])
                    values.append(int(i[1]))
                x = np.array(dates)
                y = np.array(values)
                if bubbles:
                    fig.add_trace(go.Scatter(x=x, y=y, mode=mode, name=key,
                                             marker=dict(size=y, sizemode='area', sizeref=2.*max(y)/(40.**2),
                                                         sizemin=4)
                                             ))
                else:
                    fig.add_trace(go.Scatter(x=x, y=y, mode=mode, name=key))
        else:
            for i in array:
                if isinstance(i[0], datetime.date):
                    dates.append(i[0].strftime("%Y/%m/%d"))
                else:
                    dates.append(i[0])
                values.append(int(i[1]))
            # plt.plot_date(dates, values)
            x = np.array(dates)
            y = np.array(values)
            if bubbles:
                fig.add_trace(go.Scatter(x=x, y=y, mode=mode, name='',
                                         marker=dict(size=y, sizemode='area', sizeref=2. * max(y) / (40. ** 2),
                                                     sizemin=4)
                                         ))
            else:
                fig.add_trace(go.Scatter(x=x, y=y, mode=mode, name=''))
    else:
        # for multi-graph {key: list}
        if type(array) == dict:
            for i in array:
                x = []
                y = []
                for j in array.get(i):
                    x.append(j[0])
                    y.append(j[1])
                x = np.array(x)
                y = np.array(y)
                if bubbles:
                    fig.add_trace(go.Scatter(x=x, y=y, mode=mode, name=i,
                                             marker=dict(size=y, sizemode='area', sizeref=2. * max(y) / (40. ** 2),
                                                         sizemin=4)
                                             ))
                else:
                    fig.add_trace(go.Scatter(x=x, y=y, mode=mode, name=i))

        else:
            for i in array:
                x.append(i[0])
                y.append(i[1])
            x = np.array(x)
            y = np.array(y)
            if bubbles:
                fig.add_trace(go.Scatter(x=x, y=y, mode=mode, name='',
                                         marker=dict(size=y, sizemode='area', sizeref=2. * max(y) / (40. ** 2),
                                                     sizemin=4)
                                         ))
            else:
                fig.add_trace(go.Scatter(x=x, y=y, mode=mode, name=''))

    fig.update_layout(title=title,
                      xaxis_title=Ox,
                      yaxis_title=Oy)
    file_name = ''.join([random.choice(list('123456789qwertyuiopasdfghjklzxc'
                                            'vbnmQWERTYUIOPASDFGHJKLZXCVBNM')) for x in range(10)])
    name_html = 'pio_{}.html'.format(file_name)
    name_jpg = 'pio_{}.jpg'.format(file_name)
    file_path = '/var/www/html/bot/static/{}'.format(name_html)
    file_path_jpg = '/var/www/html/bot/static/{}'.format(name_jpg)
    pio.write_html(fig, file=file_path, auto_open=False)
    fig.write_image(file_path_jpg, engine="kaleido")
    return name_html, name_jpg


def build_html_pie(array, title):
    x = []
    y = []
    # Can't build pie with negative values. If all values negative change it to absolute.
    is_negative = [1 if el[0] <= 0 else 0 for el in array]
    g = groupby(is_negative)
    is_negative = next(g, True) and not next(g, False)
    for el in array:
        x.append(el[1])
        if el[0] is None:
            y.append(0)
        else:
            if is_negative:
                # Get absolute value of the given number.
                y.append(abs(el[0]))
            else:
                y.append(el[0])

    if all(i == 0 for i in y):
        return "No data"
    else:
        trace = go.Pie(labels=x, values=y)
        data = [trace]
        fig = go.Figure(data=data)
        fig.update_layout(title=title)
        fig.update_traces(textposition='inside', textinfo='label+percent', textfont_size=20,)
        file_name = ''.join([random.choice(list('123456789qwertyuiopasdfghjklzxc'
                                                'vbnmQWERTYUIOPASDFGHJKLZXCVBNM')) for x in range(10)])
        name_html = 'pio_{}.html'.format(file_name)
        name_jpg = 'pio_{}.jpg'.format(file_name)
        file_path = '/var/www/html/bot/static/{}'.format(name_html)
        file_path_jpg = '/var/www/html/bot/static/{}'.format(name_jpg)
        pio.write_html(fig, file=file_path, auto_open=False)
        fig.write_image(file_path_jpg, engine="kaleido")
        return name_html, name_jpg


def build_html_bar(array, title, Ox, Oy, barmode=False):
    """

    :param array:
    :param title:
    :param Ox:
    :param Oy:
    :param barmode: False. available: relative(stacked), group, overlay, False
    :return:
    """
    def parse_array(inner_array):
        _x, _y = [], []
        inner_array.reverse()
        for i in inner_array[:20]:
            if type(i[0]) == str:
                x_value = i[0]
                _x.append(x_value)
                _y.append(round(i[1], 2))
            else:
                try:
                    x_value = i[1]
                except IndexError:
                    x_value = ''
                _x.append(x_value)
                _y.append(round(i[0], 2))
        return _x, _y

    if barmode:
        array["column3"] = [str(el) for el in array["column3"]]
        fig = px.bar(array, x="column2", y="column1", color="column3",  barmode=barmode)
    else:
        parsed_array = {}
        x, y = [], []

        if type(array) == dict:
            for key in array:
                x, y = parse_array(array.get(key))
                parsed_array.update({key: {'x': x, 'y': y}})
        else:
            x, y = parse_array(array)
        layout = go.Layout(yaxis=dict(tickformat=",d"), )
        if parsed_array:     # for stacked bar
            bar_list = []
            for key in parsed_array:
                x_y = parsed_array.get(key)
                bar_list.append(go.Bar(name=key, x=x_y.get('x'), y=x_y.get('y')))
            fig = go.Figure(data=bar_list, layout=layout)
        else:   # for simple bar
            fig = go.Figure(go.Bar(x=x, y=y), layout=layout)

    fig.update_layout(title=title,
                      xaxis_title=Ox,
                      yaxis_title=Oy)
    file_name = ''.join([random.choice(list('123456789qwertyuiopasdfghjklzxc'
                                            'vbnmQWERTYUIOPASDFGHJKLZXCVBNM')) for x in range(10)])
    name_html = 'pio_{}.html'.format(file_name)
    name_jpg = 'pio_{}.jpg'.format(file_name)
    file_path = '/var/www/html/bot/static/{}'.format(name_html)
    file_path_jpg = '/var/www/html/bot/static/{}'.format(name_jpg)
    pio.write_html(fig, file=file_path, auto_open=False)
    fig.write_image(file_path_jpg, engine="kaleido")

    return name_html, name_jpg


def build_html_map(df, title, colorbar_title, locationmode='country names'):
    fig = go.Figure(data=go.Choropleth(
        locations=df['country'],
        locationmode=locationmode,
        z=df['value'],
        text=df['country'],
        colorscale='Blues',
        autocolorscale=False,
        reversescale=False,
        marker_line_color='darkgray',
        marker_line_width=0.5,
        colorbar_tickprefix='$',
        colorbar_title=colorbar_title,
    ))

    fig.update_layout(
        title_text=title,
        geo=dict(
            showframe=False,
            showcoastlines=False,
            projection_type='equirectangular'
        ),
    )

    file_name = ''.join([random.choice(list('123456789qwertyuiopasdfghjklzxc'
                                            'vbnmQWERTYUIOPASDFGHJKLZXCVBNM')) for x in range(10)])
    name_html = 'pio_{}.html'.format(file_name)
    name_jpg = 'pio_{}.jpg'.format(file_name)
    file_path = '/var/www/html/bot/static/{}'.format(name_html)
    file_path_jpg = '/var/www/html/bot/static/{}'.format(name_jpg)
    pio.write_html(fig, file=file_path, auto_open=False)
    fig.write_image(file_path_jpg, engine="kaleido")

    return name_html, name_jpg
