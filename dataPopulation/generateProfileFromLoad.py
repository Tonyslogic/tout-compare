import json
from locale import locale_encoding_alias
import os
import copy
import sqlite3
from sqlite3 import Error
from string import Template
import PySimpleGUI as sg 
from collections import defaultdict

CONFIG = "C:\\dev\\solar\\"
STORAGE = "C:\\dev\\solar\\"
DBFILE = "SimData.db"

DEMO_MONTHLYDIST = {"Jan": 9.37, "Feb": 7.08, "Mar": 8.12, "Apr": 8.14, "May": 9.4, "Jun": 8.98, "Jul": 8.87, "Aug": 9.17, "Sep": 6.45, "Oct": 7.95, "Nov": 7.53, "Dec": 8.96}
DEMO_DOWDIST = {"Sun": 14.75, "Mon": 14.13, "Tue": 13.22, "Wed": 13.67, "Thu": 13.68, "Fri": 14.18, "Sat": 16.37}
DEMO_HOURLYDIST = [3.52,2.87,2.68,2.53,2.18,2.10,3.95,3.72,3.54,3.35,4.04,5.16,5.57,4.85,4.56,4.10,4.54,7.96,5.86,4.40,4.27,4.43,5.05,4.77]


def _renderLoadGeneration():
    
    left_col = [
        
        [sg.Text('The profile generator creates uses 5 minute usage data and creates a profile.json. It needs a start date and end date.', size=(75,2))],
        [sg.Text('====================================================================================', size=(85,1))],
        [sg.Text('Start date', size=(30,1)), 
             sg.In(size=(25,1), enable_events=True ,key='-CAL-', default_text='2021-10-01'), 
             sg.CalendarButton('Change date', size=(25,1), target='-CAL-', pad=None, 
                                key='-CAL1-', format=('%Y-%m-%d'))],
        [sg.Text('End date', size=(30,1)), 
             sg.In(size=(25,1), enable_events=True ,key='-CALE-', default_text='2022-09-30'), 
             sg.CalendarButton('Change date', size=(25,1), target='-CALE-', pad=None, 
                                key='-CAL2-', format=('%Y-%m-%d'))],
        [sg.Text('====================================================================================', size=(85,1))],
        [sg.Button('Generate profile.json', size=(30,1), key='-GEN_LOAD-'), sg.Text("This will generate profile.json from load data in the DB", size=(50,1), key='-ALPHA_FETCH_STATUS-')]
    ]
    layout = [[sg.Column(left_col, element_justification='l')]]    
    window = sg.Window('Load profile from DB load', layout,resizable=True)
    return window

def _saveProfile(CONFIG, profile):
    # print (profile)
    with open(os.path.join(CONFIG, "loadProfile.json"), 'w') as f:
        json.dump(profile, f)
    return

def _getDBData(dbFile, start, end, t_sql):
    ret = []
    conn = None
    try:
        conn = sqlite3.connect(dbFile)
        c = conn.cursor()
        c.execute(t_sql.substitute({'START': start, 'END': end}))
        ret = c.fetchall()
        conn.close()
    except Error as e:
        print("Load data not found in DB: " + str(e))
    return ret

def _extractProfile(CONFIG, start, end):
    ret = {}

    t_total = Template(""" SELECT SUM (NormalLoad) AS LOAD FROM dailystats WHERE Date < '$END' AND Date > '$START' """)
    t_hourly = Template(""" SELECT SUBSTR(_min,1,INSTR(_min,':') -1) As HOUR, SUM (NormalLoad) AS LOAD 
                                FROM dailystats  
                                WHERE Date < '$END' AND Date > '$START'
                                GROUP BY SUBSTR(_min,1,INSTR(_min,':') -1) ORDER BY CAST (HOUR AS NUMBER) """)
    t_daily = Template(""" SELECT DISTINCT strftime('%w', date) as D, 
                            case cast (strftime('%w', date) as integer)
                                when 0 then 'Sun'
                                when 1 then 'Mon'
                                when 2 then 'Tue'
                                when 3 then 'Wed'
                                when 4 then 'Thu'
                                when 5 then 'Fri'
                                else 'Sat' end as DAYOFWEEK, 
                            SUM (NormalLoad) AS LOAD 
                            FROM dailystats  
                            WHERE Date < '$END' AND Date > '$START'
                            GROUP BY D """)
    t_monthly = Template(""" SELECT YEAR, M, MONTH, LOAD, (YEAR || ',' || MONTH) AS MY FROM (
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
                                    when 09 then 'Sep'
                                    when 10 then 'Oct'
                                    when 11 then 'Nov'
                                    when 12 then 'Dec'
                                    else 'Mar' end as MONTH, 
                                SUM (Load) AS LOAD
                                FROM dailysums 
                                WHERE Date < '$END' AND Date > '$START'
                                GROUP BY M, YEAR ORDER BY M, YEAR ) ORDER BY YEAR, MN  """)
    
    with open(os.path.join(CONFIG, "EnvProperties.json"), 'r') as f:
        env = json.load(f)
    dbFile = os.path.join(env["StorageFolder"], env["DBFileName"])

    totRes = _getDBData(dbFile, start, end, t_total)
    tot = float(totRes[0][0])
    ret["AnnualUsage"] = tot
    ret["HourlyBaseLoad"] = 300 /1000
    
    hourlyRes = _getDBData(dbFile, start, end, t_hourly)
    hourlyDist = []
    for row in hourlyRes:
        hourlyDist.append(100 * float(row[1]) / tot)
    ret["HourlyDistribution"] = hourlyDist

    dailyDist = {}
    dailyRes = _getDBData(dbFile, start, end, t_daily)
    for row in dailyRes:
        dailyDist[row[1]] = (100 * float(row[2] / tot))
    ret["DayOfWeekDistribution"] = dailyDist

    montlyDist = {}
    monthlyRes = _getDBData(dbFile, start, end, t_monthly)
    for row in monthlyRes:
        montlyDist[row[2]] = (100 * float(row[3] / tot))
    ret["MonthlyDistribution"] = montlyDist
    
    return ret

def genProfile(config):
    global CONFIG
    CONFIG = config    
    window = _renderLoadGeneration()
    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, 'Exit'): break
        if event == '-CAL-': start = values['-CAL-']
        if event == '-CALE-': end = values['-CALE-']
        if event == '-GEN_LOAD-':
            start = values['-CAL-']
            end = values['-CALE-']
            profile = _extractProfile(CONFIG, start, end)
            _saveProfile(CONFIG, profile) 
            break
    window.close()

def main():
    genProfile(CONFIG)

if __name__ == "__main__":
    main()