import logging
import json
import sys
import sqlite3
from sqlite3 import Error
import datetime
from dateutil.relativedelta import *

CONFIG = "C:\\dev\\solar\\"

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

def _create_rows(profile, begin):
    ret = []
    workingday = datetime.datetime.strptime(begin, '%Y-%m-%d')
    finish = workingday + relativedelta(months=12) #+ datetime.timedelta(days=-1)
    daycount = (finish - workingday).days
    while (workingday < finish):
        DBDate = datetime.datetime.strftime(workingday, '%Y-%m-%d')
        DBMinuteOfDay = 0
        DBDayOfWeek = datetime.datetime.strftime(workingday, "%w")
        while (DBMinuteOfDay < 1440):
            DB_min = '{:02d}:{:02d}'.format(*divmod(DBMinuteOfDay, 60))
            DBNormalPV = 0
            DBNormalLoad = _getNormalLoad(DB_min, profile, workingday, daycount)
            ret.append((DBDate, DB_min, DBNormalLoad, DBNormalPV, DBMinuteOfDay, DBDayOfWeek))
            DBMinuteOfDay += 5
        workingday += datetime.timedelta(days=1)
        # print (DBDate, DBDayOfWeek)
    return ret

def _guiDBFromProfile(config, begin):
    global CONFIG
    CONFIG = config
    loadProfile = {}
    with open(CONFIG + "EnvProperties.json", 'r') as f:
        env = json.load(f)
    dbFile = env["StorageFolder"] + env["DBFileName"]
    _createDB(dbFile)

    with open(env["ConfigFolder"] + "loadProfile.json") as lp:
        loadProfile = json.load(lp)
    rows = _create_rows (loadProfile, begin)

    _fillDB(dbFile, rows)


def main():
    env = {}
    loadProfile = {}
    with open(CONFIG + "EnvProperties.json", 'r') as f:
        env = json.load(f)
    dbFile = env["StorageFolder"] + env["DBFileName"]
    _createDB(dbFile)

    with open(env["ConfigFolder"] + "loadProfile.json") as lp:
        loadProfile = json.load(lp)
    # logger.info(f"The number of days:: {len(data[0]['statistics'])}")
    begin = input("Start date (YYYY-MM-DD): ")
    rows = _create_rows (loadProfile, begin)

    _fillDB(dbFile, rows)

if __name__ == "__main__":
    try:
        CONFIG = sys.argv[1]
    except:
        pass
    print(CONFIG)
    main()