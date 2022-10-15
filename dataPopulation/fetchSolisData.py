#!/usr/bin/python
import os
import sqlite3
import requests
import json
import datetime
import time
from sqlite3 import Error

CONFIG = "C:\\dev\\solar\\"

DOMAIN = "m.ginlong.com"
LANGUAGE = "2"
HEADERS = {'User-Agent': 'curl/7.72.0'}

def _login(session, user, passwd):
    loginOK = False
    
    if user == "" or passwd == "":
        print('Fatal: Missing credentials')
        return loginOK

    url = 'https://'+ DOMAIN +'/cpro/login/validateLogin.json'
    params = {
        "userName": user,
        "password": passwd,
        "lan": LANGUAGE,
        "domain": DOMAIN,
        "userType": "C"
    }

    try:
        resultData = session.post(url, data=params, headers=HEADERS)
        resultJson = resultData.json()
        if resultJson.get('result') and resultJson.get('result').get('isAccept', 0) == 1:
            loginOK = True
            print('Login successful for %s' % user)
        else:
            raise Exception(json.dumps(resultJson))
    except Exception as e:
        print(e)
        print('Login failed for %s' % user)
    
    return loginOK

def _getPlantId(session):
    url = 'http://' + DOMAIN + '/cpro/epc/plantview/view/doPlantList.json'

    cookies = {'language': LANGUAGE}
    resultData = session.get(url, cookies=cookies, headers=HEADERS)
    resultJson = resultData.json()

    plantId = resultJson['result']['pagination']['data'][0]['plantId']
    print('Found plantId: %s' % plantId)
    return plantId

def _fetch(user, passwd, start, end, cachedDates):
    stats = {}

    session = requests.session()
    
    if _login(session, user, passwd):
        plantId = _getPlantId(session)
        # get daily details
        delta = datetime.timedelta(days=1)
        workingDay = start
        while workingDay <= end:
            if workingDay.strftime("%Y-%m-%d") not in cachedDates:
                fetchdate = workingDay.strftime("%Y/%m/%d") #"2022/10/13"
                print ("Fetching data for " + fetchdate)
                url = 'http://' + DOMAIN + '/cpro/epc/plantDetail/showCharts.json'
                params = {
                    'plantId': int(plantId),
                    'type': 1,
                    'date': fetchdate, 
                    'plantTimezoneId': 32,
                }

                cookies = {'language': LANGUAGE}
                resultData = session.post(url, params=params, cookies=cookies, headers=HEADERS)
                resultJson = resultData.json()
                
                d, stat = _processOneDayFetch(resultJson)
                stats[d] = stat
            else:
                print ("Already had data for " + workingDay.strftime("%Y/%m/%d") + ", skipping" )
            workingDay += delta
    return stats

def _processOneDayFetch(data):
    totalGen = 0
    totalLoad = 0
    intervals = data["result"]["chartsDataAll"]
    for interval in intervals:
        totalGen += interval["power"]
        totalLoad += interval["power_useage"]
    genNorm = float(data["result"]["energy"])/totalGen
    loadNorm = float(data["result"]["plantSta"]["energy_useage"])/totalLoad

    stat = {}
    d = datetime.datetime.strptime(data["result"]["plantSta"]["date"], "%Y%m%d").date().strftime("%Y-%m-%d")
    stat["PV"] = float(data["result"]["energy"])
    stat["Load"] = float(data["result"]["plantSta"]["energy_useage"])

    intervalStats = []

    for interval in intervals:
        dt = datetime.datetime.strptime((time.ctime((float(interval["date"])) / 1000)), "%a %b %d %H:%M:%S %Y")
        # intervalStat = [_min, PV, Load, MinuteOfDay, DayOfWeek]
        intervalStat = [dt.strftime("%H:%M"), interval["power"] * genNorm, interval["power_useage"] * loadNorm, dt.hour*60+dt.minute, dt.strftime("%w")]
        intervalStats.append(intervalStat)

    stat["Intervals"] = intervalStats
    
    return d, stat

def _loadExistingData(storageFolder):
    ret = {}
    try:
        with open(os.path.join(storageFolder, "solisstats.json"), 'r') as f:
            ret = json.load(f)
    except:
        return {}, []
    sorteddates=sorted(ret.keys(), key=lambda x:x)
    return ret, sorteddates

def _common(user, passwd, start, end, storageFolder):
    old_data, cachedDates = _loadExistingData(storageFolder)
    try:
        finish = datetime.datetime.strptime(end, '%Y-%m-%d')
        begin = datetime.datetime.strptime(start, '%Y-%m-%d')
        stats = _fetch(user, passwd, begin, finish, cachedDates)
        old_data.update(stats)
        with open(os.path.join(storageFolder, "solisstats.json"), 'w') as f:
            json.dump(old_data, f)
    except Exception as e:
        print('%s : %s' % (type(e).__name__, str(e)))
    return old_data

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

def _createRows(fetchedData):
    ret = []
    for date, stats in fetchedData.items():
        DBDate = date
        intervals = stats["Intervals"]
        for interval in intervals:
            DB_min = interval[0]
            DBNormalPV = interval[1]
            DBNormalLoad = interval[2]
            DBMinuteOfDay = interval[3]
            DBDayOfWeek = interval[4]
            # print (DBDate, DB_min)
            ret.append((DBDate, DB_min, DBNormalLoad, DBNormalPV, DBMinuteOfDay, DBDayOfWeek))
    return ret

def _fillDB(dbFile, rows):
    conn = None
    try:
        conn = sqlite3.connect(dbFile)
        c = conn.cursor()
        c.executemany('INSERT OR REPLACE INTO dailystats VALUES(?,?,?,?,?,?);',rows)
        conn.commit()
        c.execute("INSERT INTO dailysums SELECT Date, SUM(NormalPV) AS PV, SUM(NormalLoad) AS Load, 0 AS FeedIn FROM dailystats GROUP BY Date")
        conn.commit()
        conn.close()
    except Error as e:
        print(e)

def guiSolisFetch(user, passwd, start, end, config):
    global CONFIG
    CONFIG = config
    with open(os.path.join(CONFIG, "EnvProperties.json"), 'r') as f:
        env = json.load(f)
    storageFolder = env["StorageFolder"]
    dbFile = os.path.join(storageFolder, env["DBFileName"])
    fetchedData = _common(user, passwd, start, end, storageFolder)
    _createDB(dbFile)
    rows = _createRows(fetchedData)
    _fillDB(dbFile, rows)

def main():
    # This is a test/CLI entrypoint -- does not create a DB, only creates json cache
    storageFolder = os.path.curdir
    user = input("username: ")
    passwd = input("password: ")
    start = input("start date (YYYY-MM-DD): ")
    end = input("finish date (YYYY-MM-DD): ")
    _common(user, passwd, start, end, storageFolder)
        
if __name__ == "__main__":
    main()