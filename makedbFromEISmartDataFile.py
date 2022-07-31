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

def _getNormalLoad(mod, profile, workingday, daycount):
    ret = 0
    month = datetime.datetime.strftime(workingday, "%b")
    dow = datetime.datetime.strftime(workingday, "%a")
    hod = int(mod[:-3])
    year = int(datetime.datetime.strftime(workingday, "%Y"))
    imonth = int(datetime.datetime.strftime(workingday, "%m"))
    day = datetime.date(year, imonth, 1)
    single_day = datetime.timedelta(days=1)
    totalXXXDaysInMonth = 0
    while day.month == imonth:
        if day.weekday() == 0:
            totalXXXDaysInMonth += 1
        day += single_day
    
    # ret = profile["HourlyBaseLoad"]/12
    annualuse = profile["AnnualUsage"] # - (profile["HourlyBaseLoad"] * 24 * daycount)

    distMonth = profile["MonthlyDistribution"][month]/100
    distdow = profile["DayOfWeekDistribution"][dow]/100
    disthod = profile["HourlyDistribution"][hod]/100

    monthuse = annualuse * distMonth
    dayuse = (monthuse / totalXXXDaysInMonth) * distdow 
    houruse = dayuse * disthod

    ret += houruse/12

    return ret

def _create_rows(smartMeterData):
    ret = []

    for _, row in smartMeterData.iterrows():
        date = row['Date'].split("/")
        DBDate = date[2] + "-" + date[1] + "-" + date[0]
        DBNormalPV = 0
        DBDayOfWeek = datetime.datetime.strftime(datetime.datetime.strptime(DBDate, '%Y-%m-%d'), "%w")
        DBMinuteOfDay = 0
        while (DBMinuteOfDay < 1440):
            DB_min = '{:02d}:{:02d}'.format(*divmod(DBMinuteOfDay, 60))
            hm = DB_min.split(":")
            if int(hm[1]) > 29: halfHour = hm[0] + ":" + "00"
            else: halfHour = hm[0] + ":" + "30"
            DBNormalLoad = row[halfHour]/6
            ret.append((DBDate, DB_min, DBNormalLoad, DBNormalPV, DBMinuteOfDay, DBDayOfWeek))
            DBMinuteOfDay += 5
    return ret
def _getSmartMeterFilename():
    global CONFIG
    
    smartMeterFile = None

    left_col = [
            [sg.Text('This will wipe the DB and add data from a smart meter data file. If you have solar, the data will not be very good as much of the load profile will be obscured by the solar generation. Note that Feed-in data was not part of the file when this was written. ', size=(85,3))],
            [sg.Text('Log into Electric Ireland (https://youraccountonline.electricireland.ie/). Select your account. Select the "Details" section (at the smae level as "Insights". Scroll down to "Download your smart meter data". Click on that link and note where you save the file.', size=(85,3))],
            [sg.Text('Use the file selector to locate the file and click "Load', size=(85,1))],
            [sg.Text('====================================================================================', size=(85,1))],
            [sg.Text('Smart Meter Data file', size=(24,1)), sg.In(size=(25,1), enable_events=True ,key='-C_FOLDER-', default_text=CONFIG), sg.FileBrowse()],
            [sg.Button('Load', key='-CONFIG_OK-', disabled=True, size=(15,1)), sg.Button('Close', key='-CLOSE-', size=(15,1)) ]
    ]
    layout = [[sg.Column(left_col, element_justification='l')]]    
    window = sg.Window('Electric Ireland Smart Meter Data import', layout,resizable=True)
        
    cfolder = CONFIG
    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, 'Exit'): break
        if event == '-C_FOLDER-': 
            cfolder = values['-C_FOLDER-']
            if os.path.isfile(cfolder):
                window['-CONFIG_OK-'].update(disabled=False) 
        if event == '-CLOSE-':
            window.close()
            break
        if event == '-CONFIG_OK-':
            if os.path.isfile(cfolder):
                smartMeterFile = values['-C_FOLDER-']
                window.close()
                break
    return smartMeterFile


def guiDBFromEISmartMeter(config):
    global CONFIG
    CONFIG = config
    with open(os.path.join(CONFIG, "EnvProperties.json"), 'r') as f:
        env = json.load(f)
    
    smartMeterFile = _getSmartMeterFilename()
    if smartMeterFile is None: return

    smartMeterData = pd.read_csv(smartMeterFile)

    dbFile = os.path.join(env["StorageFolder"], env["DBFileName"])
    _createDB(dbFile)
    rows = _create_rows (smartMeterData)
    _fillDB(dbFile, rows)


def main():
    env = {}
    with open(os.path.join(CONFIG,"EnvProperties.json"), 'r') as f:
        env = json.load(f)
    smartMeterFile = _getSmartMeterFilename()
    if smartMeterFile is None: return

    smartMeterData = pd.read_csv(smartMeterFile)

    dbFile = os.path.join(env["StorageFolder"], env["DBFileName"])
    _createDB(dbFile)
    rows = _create_rows (smartMeterData)
    _fillDB(dbFile, rows)

if __name__ == "__main__":
    try:
        CONFIG = sys.argv[1]
    except:
        pass
    print(CONFIG)
    main()