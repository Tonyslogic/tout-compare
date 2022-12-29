import datetime
import tkinter
from dateutil.relativedelta import relativedelta
import logging
import json
import os
import sys
import sqlite3
from sqlite3 import Error
from numpy import rot90

import pandas as pd
import matplotlib.pyplot as plt
import PySimpleGUI as sg 
from string import Template

import numpy as np
from matplotlib.widgets  import RectangleSelector
import matplotlib.figure as figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk

CONFIG = "C:\\dev\\solar\\"

logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('[%(asctime)s] %(levelname)s [%(filename)s.%(funcName)s:%(lineno)d] %(message)s', datefmt='%a, %d %b %Y %H:%M:%S')
handler.setFormatter(formatter)
logger.addHandler(handler)

def _monthlyLoad(dbFile, ax):
    conn = None
    df = None
    try:
        conn = sqlite3.connect(dbFile)
        df = pd.read_sql_query(""" SELECT YEAR, M, MONTH, LOAD, (YEAR || ',' || MONTH) AS MY FROM (
                        SELECT DISTINCT strftime('%Y', date) AS YEAR, strftime('%m', date) AS MN, strftime('%m', date) as M, 
                        case cast (strftime('%m', date) as integer)
                            when 01 then 'Jan'
                            when 02 then 'Feb'
                            when 03 then 'Mar'
                            when 04 then 'Apr'
                            when 05 then 'May'
                            when 06 then 'Jun'
                            when 07 then 'Jul'
                            when 08 then 'Aug'
                            when 09 then 'Sept'
                            when 10 then 'Oct'
                            when 11 then 'Nov'
                            when 12 then 'Dec'
                            else 'Mar' end as MONTH, 
                        SUM (Load) AS LOAD
                        FROM dailysums GROUP BY M, YEAR ORDER BY M, YEAR ) ORDER BY YEAR, MN """, conn)
        pd.set_option("display.max.columns", None)
        df.head()
        df.plot(kind='bar',x='MY', y='LOAD', ax=ax, ylabel="kWH", title="Monthly load")
        ax.tick_params(labelrotation=45)
        mx = df['LOAD'].max() + 50
        mn = max(df['LOAD'].min() - 100, 0)
        ax.set_ylim([mn, mx])
        conn.close()
    except Error as e:
        print(e)
    return df

def _monthlyGen(dbFile, ax):
    conn = None
    df = None
    try:
        conn = sqlite3.connect(dbFile)
        df = pd.read_sql_query(""" SELECT YEAR, M, MONTH, GEN, (YEAR || ',' || MONTH) AS MY FROM (
                        SELECT DISTINCT strftime('%Y', date) AS YEAR, strftime('%m', date) AS MN, strftime('%m', date) as M, 
                        case cast (strftime('%m', date) as integer)
                            when 01 then 'Jan'
                            when 02 then 'Feb'
                            when 03 then 'Mar'
                            when 04 then 'Apr'
                            when 05 then 'May'
                            when 06 then 'Jun'
                            when 07 then 'Jul'
                            when 08 then 'Aug'
                            when 09 then 'Sept'
                            when 10 then 'Oct'
                            when 11 then 'Nov'
                            when 12 then 'Dec'
                            else 'Mar' end as MONTH, 
                        SUM (PV) AS GEN
                        FROM dailysums GROUP BY M, YEAR ORDER BY M, YEAR ) ORDER BY YEAR, MN """, conn)
        pd.set_option("display.max.columns", None)
        df.head()
        df.plot(kind='bar',x='MY', y='GEN', ax=ax, ylabel="kWH", title="Monthly generation")
        ax.tick_params(labelrotation=45)
        conn.close()
    except Error as e:
        print(e)
    return df

# def _monthlyFeed(dbFile, ax):
#     conn = None
#     df = None
#     try:
#         conn = sqlite3.connect(dbFile)
#         df = pd.read_sql_query(""" SELECT YEAR, M, MONTH, FEED, (MONTH || ',' || YEAR) AS MY FROM (
#                         SELECT DISTINCT strftime('%Y', date) AS YEAR, strftime('%m', date) as M, 
#                         case cast (strftime('%m', date) as integer)
#                             when 01 then 'Jan'
#                             when 02 then 'Feb'
#                             when 03 then 'Mar'
#                             when 04 then 'Apr'
#                             when 05 then 'May'
#                             when 06 then 'Jun'
#                             when 07 then 'Jul'
#                             when 08 then 'Aug'
#                             when 09 then 'Sept'
#                             when 10 then 'Oct'
#                             when 11 then 'Nov'
#                             when 12 then 'Dec'
#                             else 'Mar' end as MONTH, 
#                         SUM (FeedIn) AS FEED 
#                         FROM dailysums GROUP BY M, YEAR ORDER BY M, YEAR )""", conn)
#         pd.set_option("display.max.columns", None)
#         df.head()
#         df.plot(kind='bar',x='MY', y='FEED', ax=ax, ylabel="kWH", title="Monthly Feed")
#         ax.tick_params(labelrotation=45)
#         conn.close()
#     except Error as e:
#         print(e)
#     return df



def _totalUseByHour(dbFile, ax):
    conn = None
    df = None
    try:
        conn = sqlite3.connect(dbFile)
        df = pd.read_sql_query("SELECT SUBSTR(_min,1,INSTR(_min,':') -1) As HOUR, SUM (NormalLoad) AS LOAD FROM dailystats GROUP BY SUBSTR(_min,1,INSTR(_min,':') -1) ORDER BY CAST (HOUR AS NUMBER)", conn)
        pd.set_option("display.max.columns", None)
        df.head()
        df.plot(kind='bar',x='HOUR', y='LOAD', ax=ax, ylabel="kWH", title="Usage by hour")
        ax.tick_params(labelrotation=45)
        mx = df['LOAD'].max() + 50
        mn = max(df['LOAD'].min() - 100, 0)
        ax.set_ylim([mn, mx])
        conn.close()
    except Error as e:
        print(e)
    return df

def _totalUseByDay(dbFile, ax):
    conn = None
    df = None
    try:
        conn = sqlite3.connect(dbFile)
        df = pd.read_sql_query("""SELECT DISTINCT strftime('%w', date) as D, 
                        case cast (strftime('%w', date) as integer)
                            when 0 then 'Sun'
                            when 1 then 'Mon'
                            when 2 then 'Tue'
                            when 3 then 'Wed'
                            when 4 then 'Thur'
                            when 5 then 'Fri'
                            else 'Sat' end as DAYOFWEEK, 
                        SUM (NormalLoad) AS LOAD 
                        FROM dailystats GROUP BY D""", conn)
        pd.set_option("display.max.columns", None)
        df.head()
        df.plot(kind='bar',x='DAYOFWEEK', y='LOAD', ax=ax, ylabel="kWH", title="Usage by day")
        ax.tick_params(labelrotation=45)
        mx = df['LOAD'].max() + 50
        mn = max(df['LOAD'].min() - 100, 0)
        ax.set_ylim([mn, mx])
        conn.close()
    except Error as e:
        print(e)
    return df

def _inputDataGraphs(dbFile):
    fig, axs = plt.subplots(nrows =2, ncols=2)
    fig.subplots_adjust(hspace=.45)
    fig.canvas.manager.set_window_title("Load profile and PV data")
    
    totalbyhour = _totalUseByHour(dbFile, axs[0][0])
    totalbydayofweek = _totalUseByDay(dbFile, axs[1][0])
    # feedbymonth = _monthlyFeed(dbFile, axs[0][1])
    loadbymonth = _monthlyLoad(dbFile, axs[0][1])
    generatebymonth = _monthlyGen(dbFile, axs[1][1])

    plt.show()

def _getSavedSimName(dbFile):
    ret = []
    dbKeys = {}
    sql_getNames = "SELECT name, begin, end, id FROM scenarios"
    conn = None
    try:
        conn = sqlite3.connect(dbFile)
        c = conn.cursor()
        c.execute(sql_getNames)
        res = c.fetchall()
        if res is None: ret = []
        else :
            for r in res: 
                title = r[0] + ' (' + r[2] + ' months beginning ' + r[1] + ')'
                dbKeys[title] = (r[0], r[3], r[1], r[2]) # name, id, start, duration
                ret.append(title)
        conn.close()
    except Error as e:
        print("Simulations not found in DB: " + str(e))
    return ret, dbKeys

def _buySellByDay(dbFile, sim, ax):
    conn = None
    df = None
    sql = Template("""SELECT DISTINCT case cast (DayOfWeek as integer)
                when 0 then 'Sunday'
                when 1 then 'Monday'
                when 2 then 'Tuesday'
                when 3 then 'Wednesday'
                when 4 then 'Thursday'
                when 5 then 'Friday'
                else 'Saturday' end as DAYOFWEEK,  
                SUM (Buy) AS BUY,
                SUM (Feed) AS SELL 
                FROM 
                (
                    SELECT DayOfWeek, Feed, Buy
                    FROM scenariodata, scenarios WHERE name = '$SIM' AND scenarios.id = scenariodata.scenarioID
                )
                GROUP BY DayOfWeek""")
    try:
        conn = sqlite3.connect(dbFile)
        df = pd.read_sql_query(sql.substitute({"SIM": sim}), conn)
        pd.set_option("display.max.columns", None)
        df.head()
        df.plot(kind='bar',x='DAYOFWEEK', ax=ax, ylabel="kWH", title="Buy&Sell by day")
        ax.tick_params(labelrotation=45)
        conn.close()
    except Error as e:
        print(e)
    return df

def _buySellByMonth(dbFile, sim, ax):
    conn = None
    df = None
    sql = Template(""" SELECT DISTINCT Y, M, case cast (M as integer)
                when 01 then 'January'
                when 02 then 'February'
                when 03 then 'March'
                when 04 then 'April'
                when 05 then 'May'
                when 06 then 'June'
                when 07 then 'July'
                when 08 then 'August'
                when 09 then 'September'
                when 10 then 'October'
                when 11 then 'November'
                when 12 then 'December'
                else 'March' end as MONTH, 
                SUM (Buy) AS BUY,
                SUM ("Feed") AS SELL 
                FROM (
                    SELECT  strftime('%Y', Date) as Y, strftime('%m', Date) as M, Feed, Buy
                    FROM scenariodata, scenarios WHERE name = '$SIM' AND scenarios.id = scenariodata.scenarioID
                ) GROUP BY M""")
    try:
        conn = sqlite3.connect(dbFile)
        df = pd.read_sql_query(sql.substitute({"SIM": sim}), conn)
        pd.set_option("display.max.columns", None)
        df.head()
        df.plot(kind='bar',x='MONTH', ax=ax, ylabel="kWH", title="Buy&Sell by month")
        ax.tick_params(labelrotation=45)
        conn.close()
    except Error as e:
        print(e)
    return df

def _buySellByHour(dbFile, sim, ax):
    conn = None
    df = None
    sql = Template(""" SELECT hour As HOUR,  
            SUM (Buy) AS BUY,
            SUM (Feed) AS SELL 
            FROM 
            (
                SELECT MinuteOfDay/60 AS hour, Feed, Buy
                FROM scenariodata, scenarios WHERE name = '$SIM' AND scenarios.id = scenariodata.scenarioID
            )
            GROUP BY HOUR ORDER BY CAST (HOUR AS NUMBER)""")
    try:
        conn = sqlite3.connect(dbFile)
        df = pd.read_sql_query(sql.substitute({"SIM": sim}), conn)
        pd.set_option("display.max.columns", None)
        df.head()
        df.plot(kind='bar',x='HOUR', ax=ax, ylabel="kWH", title="Buy&Sell by hour")
        ax.tick_params(labelrotation=45)
        conn.close()
    except Error as e:
        print(e)
    return df

def _pvDistributionByMonth(dbFile, sim, ax):
    conn = None
    df = None
    sql = Template(""" SELECT DISTINCT case cast (M as integer)
                when 01 then 'January'
                when 02 then 'February'
                when 03 then 'March'
                when 04 then 'April'
                when 05 then 'May'
                when 06 then 'June'
                when 07 then 'July'
                when 08 then 'August'
                when 09 then 'September'
                when 10 then 'October'
                when 11 then 'November'
                when 12 then 'December'
                else 'March' end as MONTH, 
                SUM (pvToCharge) AS TO_BATTERY,
                SUM (pvToLoad) AS TO_LOAD,
                SUM (Feed) AS TO_GRID,
                SUM (kWHDivToEV) AS TO_EV,
                SUM (kWHDivToWater) AS TO_WATER
                FROM (
                    SELECT  strftime('%Y', Date) as Y, strftime('%m', Date) as M, Feed, pvToCharge, pvToLoad, pv, kWHDivToEV, kWHDivToWater
                    FROM scenariodata, scenarios WHERE name = '$SIM' AND scenarios.id = scenariodata.scenarioID
                ) GROUP BY M ORDER BY Y, M""")
    try:
        conn = sqlite3.connect(dbFile)
        df = pd.read_sql_query(sql.substitute({"SIM": sim}), conn)
        pd.set_option("display.max.columns", None)
        df.head()
        df.plot(kind='bar',stacked=True, x='MONTH', ax=ax, ylabel="kWH", title="Monthly PV distribution")
        ax.tick_params(labelrotation=45)
        conn.close()
    except Error as e:
        print(e)
    return df

def _simDetails(dbFile, sim, title):
    fig, axs = plt.subplots(nrows =2, ncols=2)
    fig.subplots_adjust(hspace=.45)
    fig.canvas.manager.set_window_title(title)
    
    _buySellByHour(dbFile, sim, axs[0][0])
    _buySellByDay(dbFile, sim, axs[1][0])
    _buySellByMonth(dbFile, sim, axs[0][1])
    _pvDistributionByMonth(dbFile, sim, axs[1][1])

    plt.show()

def _simDetailExplore(dbFile, sim, title):
    # sim: name, id, start, duration
    sql_line = Template("""SELECT Date || ' ' || substr('00'|| CAST(MinuteOfDay / 60 AS TEXT), -2, 2) || ':' ||  substr('00'|| CAST(MinuteOfDay % 60 AS TEXT), -2, 2) AS idx, Buy, Feed, SOC, pvToCharge, pvToLoad, pv, batToLoad, DirectEVcharge, waterTemp, kWHDivToWater, kWHDivToEV, Load, immersionLoad FROM scenariodata, (SELECT Date as D, MinuteOfDay as M, NormalLoad as Load FROM dailystats) AS DS WHERE scenarioID = $ID AND Date IN ('$PREV', '$DAY', '$NEXT') AND DS.D = Date AND DS.M = MinuteOfDay """)
    sql_bar = Template("""
        SELECT substr('00'|| CAST(MinuteOfDay / 60 AS TEXT), -2, 2) AS HOUR, SUM(Buy) AS BUY, SUM(Feed) AS SELL, SUM(pvToCharge) AS PV2B, SUM(pvToLoad) AS PV2L, 
            SUM(batToLoad) AS B2L, SUM(DirectEVcharge) AS EVC, SUM(kWHDivToWater) AS HWD, SUM(kWHDivToEV) AS EVD, SUM(Load) AS LOAD, SUM(pv) AS PV, sum(immersionLoad) AS HWL
        FROM scenariodata, (SELECT Date as D, MinuteOfDay as M, NormalLoad as Load FROM dailystats) AS DS 
        WHERE scenarioID = $ID AND Date IN ('$DAY') 
        AND DS.D = Date AND DS.M = MinuteOfDay	
        GROUP BY HOUR  """)
    
    # instantiate matplotlib figure
    fig = figure.Figure()
    ax = fig.add_subplot(211)
    ax2 = ax.twinx()
    ax3 = ax.twinx()
    ax4 = fig.add_subplot(212)
    DPI = fig.get_dpi()
    fig.set_size_inches(900 * 2 / float(DPI), 707 / float(DPI))

    # ------------------------------- This is to include a matplotlib figure in a Tkinter canvas
    def draw_figure_w_toolbar(canvas, fig, canvas_toolbar):
        if canvas.children:
            for child in canvas.winfo_children():
                child.destroy()
        if canvas_toolbar.children:
            for child in canvas_toolbar.winfo_children():
                child.destroy()
        figure_canvas_agg = FigureCanvasTkAgg(fig, master=canvas)
        figure_canvas_agg.draw()
        toolbar = Toolbar(figure_canvas_agg, canvas_toolbar)
        toolbar.update()
        # figure_canvas_agg.get_tk_widget().pack(side='right', fill='both', expand=1)
        figure_canvas_agg.get_tk_widget().pack(side="top",fill='both',expand=True)
        canvas.pack(side="top",fill='both',expand=True)
    
    class Toolbar(NavigationToolbar2Tk):
        def __init__(self, *args, **kwargs):
            super(Toolbar, self).__init__(*args, **kwargs)


    # ------------------------------- PySimpleGUI CODE
    def _renderGraph(df, df_bars, values, day):
        legnd = []
        lines = []
        if df is None: return
        df['idx'] = pd.to_datetime(df['idx'])
        df.set_index('idx', inplace=True)
        df_bars.set_index('HOUR', inplace=True)
        barList = []
        barColours = []
        if values['-SHOW_BUY-']: 
            lines.append(ax.fill_between(df.index, 0, df['Buy'], color='blue', alpha=0.5))
            legnd.append("BUY")
            barList.append("BUY")
            barColours.append("blue")
        if values['-SHOW_SELL-']: 
            lines.append(ax.fill_between(df.index, 0, df['Feed'], color='yellow', alpha=0.5))
            legnd.append("SELL")
            barList.append("SELL")
            barColours.append("yellow")
        if values['-SHOW_PV-']: 
            lines.append(ax.fill_between(df.index, 0, df['pv'], color='orange', alpha=0.5))
            legnd.append("PV")
            barList.append("PV")
            barColours.append("orange")
        if values['-SHOW_PV2B-']: 
            lines.append(ax.fill_between(df.index, 0, df['pvToCharge'], color='indigo', alpha=0.5))
            legnd.append("PV2B")
            barList.append("PV2B")
            barColours.append("indigo")
        if values['-SHOW_PV2L-']: 
            lines.append(ax.fill_between(df.index, 0, df['pvToLoad'], color='green', alpha=0.5))
            legnd.append("PV2L")
            barList.append("PV2L")
            barColours.append("green")
        if values['-SHOW_B2L-']: 
            lines.append(ax.fill_between(df.index, 0, df['batToLoad'], color='violet', alpha=0.5))
            legnd.append("B2L")
            barList.append("B2L")
            barColours.append("violet")
        if values['-SHOW_EVC-']: 
            lines.append(ax.fill_between(df.index, 0, df['DirectEVcharge'], color='purple', alpha=0.5))
            legnd.append("EVC")
            barList.append("EVC")
            barColours.append("purple")
        if values['-SHOW_EVD-']: 
            lines.append(ax.fill_between(df.index, 0, df['kWHDivToEV'], color='magenta', alpha=0.5))
            legnd.append("EVD")
            barList.append("EVD")
            barColours.append("magenta")
        if values['-SHOW_HWD-']: 
            lines.append(ax.fill_between(df.index, 0, df['kWHDivToWater'], color='brown', alpha=0.5))
            legnd.append("HWD")
            barList.append("HWD")
            barColours.append("brown")
        if values['-SHOW_HWL-']: 
            lines.append(ax.fill_between(df.index, 0, df['immersionLoad'], color='deeppink', alpha=0.5))
            legnd.append("HWL")
            barList.append("HWL")
            barColours.append("deeppink")
        if values['-SHOW_LOAD-']: 
            lines.append(ax.fill_between(df.index, 0, df['Load'], color='cyan', alpha=0.5))
            legnd.append("Load")
            barList.append("LOAD")
            barColours.append("cyan")
        if values['-SHOW_SOC-']: 
            lines.append(ax2.fill_between(df.index, 0, df['SOC'], color='red', alpha=0.5))
            for tl in ax2.get_yticklabels():
                tl.set_color('r')
            ax2.set_ylim(0,6)
            ax2.set_ylabel('SOC (kWh)', color='red')
            ax2.spines['right'].set_position(('outward', 40))
            ax2.spines['right'].set_color('red')
            legnd.append("SOC")
        if values['-SHOW_HWT-']:
            lines.append(ax3.fill_between(df.index, 0, df['waterTemp'], color='black', alpha=0.5))
            for tl in ax3.get_yticklabels():
                tl.set_color('black')
            ax3.set_ylim(0,80)
            ax3.set_ylabel('Water (C)', color='black')
            ax3.spines['right'].set_position(('outward', 80))
            legnd.append("HWT")
        ax.set_ylabel('kWh (in 5min intervals)')
        ax.legend(lines, legnd, loc=0)

        df_show_bars = df_bars[barList].copy()
        try: df_show_bars.plot.bar(color=barColours, ax=ax4, xlabel=("Hourly sums for " + day))
        except: pass
        ax4.set_ylabel('kWh (per hour)')

        draw_figure_w_toolbar(window['fig_cv'].TKCanvas, fig, window['controls_cv'].TKCanvas)

    start = datetime.datetime.strptime(sim[2], '%Y-%m-%d')
    ve = start + relativedelta(months=int(sim[3]))
    valid_end = datetime.datetime.strftime(ve, '%Y-%m-%d')
    layout = [
        [sg.Text('View date (valid dates from ' + sim[2] + ' to ' + valid_end + ')', size=(24,2)), 
                sg.In(size=(25,1), enable_events=True ,key='-CAL-', default_text=sim[2], disabled=True), 
                sg.CalendarButton('Change date', size=(25,1), target='-CAL-', pad=None, key='-CAL1-', format=('%Y-%m-%d'), default_date_m_d_y=(start.month, start.day, start.year)),
                sg.Checkbox('Three days', size=(12,1), default=True, key='-DAYCOUNT-', enable_events=True),
                sg.Button('<',size=(2,1), key='-PREV-', enable_events=True),
                sg.Button('>',size=(2,1), key='-NEXT-', enable_events=True),
            ],
        [
            sg.Text('Show Items:', size=(15,1)),
            sg.Checkbox('PV', size=(6,1), default=False, key='-SHOW_PV-', enable_events=True),
            sg.Checkbox('Load', size=(6,1), default=True, key='-SHOW_LOAD-', enable_events=True),
            sg.Checkbox('Buy', size=(6,1), default=True, key='-SHOW_BUY-', enable_events=True),
            sg.Checkbox('Sell', size=(6,1), default=False, key='-SHOW_SELL-', enable_events=True),
            sg.Checkbox('SOC', size=(6,1), default=False, key='-SHOW_SOC-', enable_events=True),
            sg.Checkbox('PV2B', size=(6,1), default=True, key='-SHOW_PV2B-', enable_events=True),
            sg.Checkbox('PV2L', size=(6,1), default=True, key='-SHOW_PV2L-', enable_events=True),
            sg.Checkbox('B2L', size=(6,1), default=True, key='-SHOW_B2L-', enable_events=True),
            sg.Checkbox('EVC', size=(6,1), default=False, key='-SHOW_EVC-', enable_events=True),
            sg.Checkbox('WTemp', size=(6,1), default=False, key='-SHOW_HWT-', enable_events=True),
            sg.Checkbox('HWD', size=(6,1), default=False, key='-SHOW_HWD-', enable_events=True),
            sg.Checkbox('HWL', size=(6,1), default=False, key='-SHOW_HWL-', enable_events=True),
            sg.Checkbox('EVD', size=(6,1), default=False, key='-SHOW_EVD-', enable_events=True),
            ],
        [sg.Column(
            layout=[
                [sg.Canvas(key='fig_cv',
                        # it's important that you set this size
                        size=(500 * 2, 700)
                        )]
            ],
            background_color='#DAE0E6',
            pad=(0, 0)
        )],
        [sg.Canvas(key='controls_cv')],
    ]

    window = sg.Window(title, layout, resizable=True)
    window.finalize()
    window.bind("<Configure>", "_onsize")
    df = None
    df_bars = None

    while True:
        event, values = window.read()
        # print(event, values)
        if event == sg.WIN_CLOSED:
            break
        if event == '_onsize':
            # print(window.size)
            pass
        if event == '-NEXT-':
            day = values['-CAL-']
            dt_day = datetime.datetime.strptime(day, '%Y-%m-%d')
            dt_day = dt_day + relativedelta(days=+1)
            day = datetime.datetime.strftime(dt_day, '%Y-%m-%d')
            window['-CAL-'].update(value=day)
            _clearAxes(ax, ax2, ax3, ax4)
            df, df_bars = _reloadData(dbFile, sim, sql_line, sql_bar, start, ve, values, day, dt_day)
            _renderGraph(df, df_bars, values, day)
        if event == '-PREV-':
            day = values['-CAL-']
            dt_day = datetime.datetime.strptime(day, '%Y-%m-%d')
            dt_day = dt_day + relativedelta(days=-1)
            day = datetime.datetime.strftime(dt_day, '%Y-%m-%d')
            window['-CAL-'].update(value=day)
            _clearAxes(ax, ax2, ax3, ax4)
            df, df_bars = _reloadData(dbFile, sim, sql_line, sql_bar, start, ve, values, day, dt_day)
            _renderGraph(df, df_bars, values, day)
        elif event == '-CAL-' or event == '-DAYCOUNT-' or str(event).startswith('-SHOW'):
            day = values['-CAL-']
            dt_day = datetime.datetime.strptime(day, '%Y-%m-%d')
            _clearAxes(ax, ax2, ax3, ax4)
            df, df_bars = _reloadData(dbFile, sim, sql_line, sql_bar, start, ve, values, day, dt_day)
            _renderGraph(df, df_bars, values, day)

    window.close()

def _clearAxes(ax, ax2, ax3, ax4):
    ax.clear()
    ax2.clear()
    ax3.clear()
    ax4.clear()

def _reloadData(dbFile, sim, sql_line, sql_bar, start, ve, values, day, dt_day):
    df = None
    df_bars = None
    if values['-DAYCOUNT-']:
        dt_prev = dt_day + relativedelta(days=-1)
        dt_nxt = dt_day + relativedelta(days=+1)
        prev = datetime.datetime.strftime(dt_prev, '%Y-%m-%d')
        nxt = datetime.datetime.strftime(dt_nxt, '%Y-%m-%d')
    else:  
        prev = day
        nxt = day
    if dt_day > start and dt_day < ve:
        try:
            conn = sqlite3.connect(dbFile)
            df = pd.read_sql_query(sql_line.substitute({"ID": sim[1], "PREV": prev, "DAY": day, "NEXT": nxt}), conn)
            df_bars = pd.read_sql_query(sql_bar.substitute({"ID": sim[1], "DAY": day}), conn)
            conn.close()
        except Error as e:
            print(e)
    return df, df_bars

def display(config):
    global CONFIG
    CONFIG = config
    env = {}
    with open(os.path.join(CONFIG, "EnvProperties.json"), 'r') as f:
        env = json.load(f)
    dbFile = os.path.join(env["StorageFolder"], env["DBFileName"])

    # savedSims = ["As-is", "As-is (no battery)"]
    savedSims, dbKeys = _getSavedSimName(dbFile)

    left_col = [
            [sg.Button('Load profile & PV data graphs', key='-LOAD_PROFILE-', size=(25,1))],
            [sg.Text('=====================================================================================================', size=(60,1))],
            [sg.Text('Pick a saved simulation and then select the type of graphs to see', size=(60,1))],
            [sg.Combo(savedSims, size=(60,1), readonly=True, key="-SIM-")],
            [sg.Button('Simulation results graphs', key='-SIM_GRAPHS-', size=(25,1))],
            [sg.Button('Simulation detail exploration', key='-PV_DIV-', size=(25,1))],
            [sg.Text('=====================================================================================================', size=(60,1))],
            [sg.Button('Close', key='-CLOSE-', size=(25,1))]
    ]
    layout = [[sg.Column(left_col, element_justification='l')]]    
    nav_window = sg.Window('Data visualization', layout,resizable=True)
    nav_window.finalize()

    while True:
        event, values = nav_window.read()
        if event in (sg.WIN_CLOSED, 'Exit'): break
        if event == '-LOAD_PROFILE-': _inputDataGraphs(dbFile)
        if event == '-SIM_GRAPHS-': 
            if values["-SIM-"]:
                print (dbKeys[values["-SIM-"]][0])
                _simDetails(dbFile, dbKeys[values["-SIM-"]][0], values["-SIM-"])
        if event == '-PV_DIV-': 
            if values["-SIM-"]:
                 _simDetailExplore(dbFile, dbKeys[values["-SIM-"]], values["-SIM-"])
        if event == '-CLOSE-': break
    nav_window.close()

def main():
    display(CONFIG)

if __name__ == "__main__":
    try:
        CONFIG = sys.argv[1]
    except:
        pass
    print(CONFIG)
    main()