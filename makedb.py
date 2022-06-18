import logging
import json
import sys
import sqlite3
from sqlite3 import Error

CONFIG = "C:\\dev\\solar\\"

logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('[%(asctime)s] %(levelname)s [%(filename)s.%(funcName)s:%(lineno)d] %(message)s', datefmt='%a, %d %b %Y %H:%M:%S')
handler.setFormatter(formatter)
logger.addHandler(handler)

def _calculateNormalData(conn):
    tempTable = "CREATE TEMPORARY TABLE Factors AS WITH FactorsQ AS (SELECT D, (SL * 5 / Load) AS LF, (SPV * 5 / PV) AS PVF FROM (SELECT DISTINCT dailystats.date as D, SUM (dailystats.Load) AS SL, dailysums.Load, SUM (dailystats.PV) AS SPV, dailysums.PV FROM dailystats, dailysums WHERE D = dailysums.Date GROUP BY D)) SELECT * FROM FactorsQ"
    populateNormals = """REPLACE INTO dailystats 
        SELECT Date, _min, BAT, LOAD, PV, FeedIn, GridConsumption, 
            (dailystats.Load * 5 / temp.Factors.LF) AS NL, 
            (dailystats.PV * 5 / temp.Factors.PVF) AS NPV, 
            (substr(_min, 1, instr(_min, ':')-1)*60 + substr(_min, instr(_min, ':')+1)) AS MinuteOfDay,
            strftime('%w', date) as DayOfWeek 
        FROM dailystats, temp.Factors WHERE dailystats.Date = temp.Factors.D"""
    dropTempTable = "DROP TABLE Temp.Factors"

    c = conn.cursor()
    c.execute (tempTable)
    c.execute (populateNormals)
    c.execute (dropTempTable)
    conn.commit()

def _fillDB(dbFile, rows, sums):
    conn = None
    try:
        conn = sqlite3.connect(dbFile)
        c = conn.cursor()
        c.executemany('INSERT INTO dailystats VALUES(?,?,?,?,?,?,?,?,?,?,?);',rows)
        c.executemany('INSERT INTO dailysums VALUES(?,?,?,?);',sums)
        conn.commit()
        _calculateNormalData(conn)
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
                        BAT REAL    NOT NULL, \
                        Load REAL    NOT NULL, \
                        PV REAL    NOT NULL, \
                        FeedIn REAL    NOT NULL, \
                        GridConsumption REAL    NOT NULL, \
                        NormalLoad REAL DEFAULT '', \
                        NormalPV REAL DEFAULT '', \
                        MinuteOfDay INTEGER DEFAULT '', \
                        DayOfWeek INTEGER DEFAULT '', \
                        PRIMARY KEY (Date, _min));")
        print("dailystats created")
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

def _create_rows(data):
    ret = []
    summaries = []
    for day in data:
        for entry in day:
            theDate = entry
            theDaysData = day[entry]
            summary = [theDate, 
                        theDaysData['Epvtoday'], 
                        theDaysData['ELoad'],
                        theDaysData['EFeedIn']]
            summaries.append(summary)
            for idx, t in enumerate(theDaysData['Time']):
                row = [theDate, t, 
                        theDaysData['Cbat'][idx], 
                        theDaysData['HomePower'][idx], 
                        theDaysData['Ppv'][idx], 
                        theDaysData['FeedIn'][idx], 
                        theDaysData['GridCharge'][idx],
                        0, 0, 0, 0
                        ]
                ret.append(row)
        del ret[-1]
    logger.info(f"Counted {len(ret)} rows")
    return ret, summaries

def guiMakeDB(config):
    global CONFIG
    CONFIG = config
    main()

def main():
    
    env = {}
    with open(CONFIG + "EnvProperties.json", 'r') as f:
        env = json.load(f)
    storageFolder = env["StorageFolder"]
    dbFileName = env["DBFileName"]

    with open(storageFolder + "dailystats.json", 'r') as f:
        data = json.load(f)
    logger.info(f"The number of days:: {len(data[0]['statistics'])}")
    rows, sums = _create_rows (data[0]['statistics'])

    dbFile = storageFolder + dbFileName
    _createDB(dbFile)
    _fillDB(dbFile, rows, sums)

if __name__ == "__main__":
    try:
        CONFIG = sys.argv[1]
    except:
        pass
    print(CONFIG)
    main()