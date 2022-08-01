import logging
import json
import os
import sys
import sqlite3
from sqlite3 import Error
from numpy import rot90

import pandas as pd
import matplotlib.pyplot as plt

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

def _monthlyFeed(dbFile, ax):
    conn = None
    df = None
    try:
        conn = sqlite3.connect(dbFile)
        df = pd.read_sql_query(""" SELECT YEAR, M, MONTH, FEED, (MONTH || ',' || YEAR) AS MY FROM (
                        SELECT DISTINCT strftime('%Y', date) AS YEAR, strftime('%m', date) as M, 
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
                        SUM (FeedIn) AS FEED 
                        FROM dailysums GROUP BY M, YEAR ORDER BY M, YEAR )""", conn)
        pd.set_option("display.max.columns", None)
        df.head()
        df.plot(kind='bar',x='MY', y='FEED', ax=ax, ylabel="kWH", title="Monthly Feed")
        ax.tick_params(labelrotation=45)
        conn.close()
    except Error as e:
        print(e)
    return df



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

def display(config):
    global CONFIG
    CONFIG = config
    env = {}
    with open(os.path.join(CONFIG, "EnvProperties.json"), 'r') as f:
        env = json.load(f)
    dbFile = os.path.join(env["StorageFolder"], env["DBFileName"])
    fig, axs = plt.subplots(nrows =2, ncols=2)
    fig.subplots_adjust(hspace=.45)
    
    totalbyhour = _totalUseByHour(dbFile, axs[0][0])
    totalbydayofweek = _totalUseByDay(dbFile, axs[1][0])
    # feedbymonth = _monthlyFeed(dbFile, axs[0][1])
    loadbymonth = _monthlyLoad(dbFile, axs[0][1])
    generatebymonth = _monthlyGen(dbFile, axs[1][1])

    plt.show()

def main():
    display(CONFIG)

if __name__ == "__main__":
    try:
        CONFIG = sys.argv[1]
    except:
        pass
    print(CONFIG)
    main()