from io import StringIO
import logging
import json
import os
import sys
import sqlite3
from sqlite3 import Error
import datetime
from dateutil.relativedelta import *

import PySimpleGUI as sg
import pandas as pd

# from smart_lps import SMART_LP25
# from smart_lps import SMART_LP27 
from dataPopulation.smart_lps import SMART_LP25
from dataPopulation.smart_lps import SMART_LP27 

CONFIG = "C:\\dev\\solar\\"
STORAGE = "C:\\dev\\solar\\"
DBFILE = "SimData.db"

logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('[%(asctime)s] %(levelname)s [%(filename)s.%(funcName)s:%(lineno)d] %(message)s', datefmt='%a, %d %b %Y %H:%M:%S')
handler.setFormatter(formatter)
logger.addHandler(handler)

def _fillDB(dbFile, rows):
    conn = None
    try:
        conn = sqlite3.connect(dbFile)
        c = conn.cursor()
        c.executemany('INSERT INTO dailystats VALUES(?,?,?,?,?,?);',rows)
        conn.commit()
        c.execute("INSERT INTO dailysums SELECT Date, SUM(NormalPV) AS PV, SUM(NormalLoad) AS Load, 0 AS FeedIn FROM dailystats GROUP BY Date")
        conn.commit()
        conn.close()
    except Error as e:
        print(e)

def _createDB(dbFile):
    conn = None
    try:
        conn = sqlite3.connect(dbFile)
        conn.execute("DROP TABLE IF EXISTS dailysums")
        conn.execute("DROP TABLE IF EXISTS dailystats")
        conn.commit()
        conn.execute("CREATE TABLE IF NOT EXISTS dailystats ( \
                        Date TEXT NOT NULL, \
                        _min TEXT    NOT NULL, \
                        NormalLoad REAL DEFAULT '', \
                        NormalPV REAL DEFAULT '', \
                        MinuteOfDay INTEGER DEFAULT '', \
                        DayOfWeek INTEGER DEFAULT '', \
                        PRIMARY KEY (Date, _min));")
        # print("dailystats created")
        conn.execute("CREATE TABLE IF NOT EXISTS dailysums ( \
                        Date TEXT  PRIMARY KEY    NOT NULL, \
                        PV REAL    NOT NULL, \
                        Load REAL    NOT NULL, \
                        FeedIn REAL NOT NULL \
                        );")
        conn.commit()
        conn.close()
    except Error as e:
        print(e)

def _create_rows(smartMeterData, annualUsage):
    ret = []

    for _, row in smartMeterData.iterrows():
        DBDate = row['Date'].strip()
        DBNormalPV = 0
        DBDayOfWeek = datetime.datetime.strftime(datetime.datetime.strptime(DBDate, '%Y-%m-%d'), "%w")
        DBMinuteOfDay = 0
        while (DBMinuteOfDay < 1440):
            DB_min = '{:02d}:{:02d}'.format(*divmod(DBMinuteOfDay, 60))
            hm = DB_min.split(":")
            if int(hm[1]) <= 15: quarterHour = hm[0] + ":" + "15"
            if int(hm[1]) <= 30: quarterHour = hm[0] + ":" + "30"
            if int(hm[1]) <= 45: quarterHour = hm[0] + ":" + "45"
            if int(hm[1]) > 45: 
                if int(hm[0]) > 1: quarterHour = '{:02d}'.format(int(hm[0]) -1) + ":" + "00"
                else: quarterHour = "24:00:00"
            DBNormalLoad = row[quarterHour]/3 * annualUsage
            ret.append((DBDate, DB_min, DBNormalLoad, DBNormalPV, DBMinuteOfDay, DBDayOfWeek))
            DBMinuteOfDay += 5
    return ret


def _getStandardLPData():
    global CONFIG
    
    lpData = None
    annualUsage = 4200
    meterTypes = ["Urban", "Rural"]

    left_col = [
            [sg.Text('This will wipe the DB and add data from the Irish standard load profile (Nov 21). You can learn more here: https://rmdservice.com/standard-load-profiles/', size=(55,2))],
            [sg.Text('Select the meter type (Urban or Rural), and specify the annual usage in kWh. Then "Load"', size=(55,1))],
            [sg.Text('====================================================================================', size=(55,1))],
            [sg.Text('Smart meter type', size=(24,1)), sg.Combo(meterTypes, size=(25,1), readonly=True, key="-TYPE-")],
            [sg.Text('Annual usage (kWh)', size=(24,1)), sg.In(size=(25,1), enable_events=True ,key='-USAGE-', default_text="4200")],
            [sg.Button('Load', key='-LOAD-', disabled=False, size=(15,1)), sg.Button('Close', key='-CLOSE-', size=(15,1)) ]
    ]
    layout = [[sg.Column(left_col, element_justification='l')]]    
    window = sg.Window('ESBN Standard load profile', layout,resizable=True)
        
    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, 'Exit'): break
        if event == '-CLOSE-': break
        if event == '-LOAD-':
            meterType = values['-TYPE-']
            annualUsage = int(values['-USAGE-'])
            break
    window.close()
    
    if meterType is not None:
        if meterType == "Urban": lpData = pd.read_csv(StringIO(SMART_LP25)) 
        else: lpData = pd.read_csv(StringIO(SMART_LP27)) 
    
    return lpData, annualUsage

def guiDBFromSLP(config):
    global CONFIG
    CONFIG = config
    with open(os.path.join(CONFIG, "EnvProperties.json"), 'r') as f:
        env = json.load(f)
    
    lpData, annualUsage = _getStandardLPData()
    
    dbFile = os.path.join(env["StorageFolder"], env["DBFileName"])
    _createDB(dbFile)
    rows = _create_rows (lpData, annualUsage)
    _fillDB(dbFile, rows)


def main():
    # env = {}
    # with open(os.path.join(CONFIG,"EnvProperties.json"), 'r') as f:
    #     env = json.load(f)
    
    # lpData = pd.read_csv(StringIO(SMART_LP25))

    # dbFile = os.path.join(env["StorageFolder"], env["DBFileName"])
    # _createDB(dbFile)
    # rows = _create_rows (lpData, 8000)
    # _fillDB(dbFile, rows)
    guiDBFromSLP(CONFIG)

if __name__ == "__main__":
    try:
        CONFIG = sys.argv[1]
    except:
        pass
    print(CONFIG)
    main()