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
    sql_getNames = "SELECT name, begin, end FROM scenarios"
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
                dbKeys[title] = r[0]
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

def _pvDiversion(dbFile, sim):
    print("Did diversion work? " + sim)

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
            [sg.Text('======================================================', size=(25,1))],
            [sg.Text('Pick a saved simulation and then select the type of graphs to see', size=(25,2))],
            [sg.Combo(savedSims, size=(25,1), readonly=True, key="-SIM-")],
            [sg.Button('Simulation results graphs', key='-SIM_GRAPHS-', size=(25,1))],
            [sg.Button('Diverter sim results graphs', key='-PV_DIV-', size=(25,1), disabled=True)],
            [sg.Text('======================================================', size=(25,1))],
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
                _simDetails(dbFile, dbKeys[values["-SIM-"]], values["-SIM-"])
        if event == '-PV_DIV-': _pvDiversion(dbFile, values["-SIM-"])
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