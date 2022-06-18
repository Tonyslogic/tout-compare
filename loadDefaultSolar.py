import logging
import json
import sys
import sqlite3
from sqlite3 import Error
import pandas as pd

from solardaily import DAILY
from solarsums import SUMS


CONFIG = "C:\\dev\\solar\\"

logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('[%(asctime)s] %(levelname)s [%(filename)s.%(funcName)s:%(lineno)d] %(message)s', datefmt='%a, %d %b %Y %H:%M:%S')
handler.setFormatter(formatter)
logger.addHandler(handler)

def loadDefaultSolar(config, dbFile):
    global CONFIG
    CONFIG = config
    _loadDefaultSolar(dbFile)

def _loadDefaultSolar(dbFile):
    # jsn = []
    # with open("solarsums.json", 'r') as f:
    #     jsn = json.load(f)
    # sums = pd.read_json(jsn)
    # with open("solardaily.json", 'r') as f:
    #     jsn = json.load(f)
    # daily = pd.read_json(jsn)
    daily = pd.read_json(DAILY)
    sums = pd.read_json(SUMS)
    # print(df2)
    conn = None
    try:
        conn = sqlite3.connect(dbFile)
        sums.to_sql('temp_sums', conn, if_exists='replace')
        daily.to_sql('temp_daily', conn, if_exists='replace')
        
        cur = conn.cursor()
        cur.execute(""" UPDATE dailysums AS f
                        SET PV = t.PV
                        FROM temp_sums AS t
                        WHERE substr(f.Date, 6) = t.MD
        """)
        # print("sums done")
        cur.execute(""" UPDATE dailystats AS f
                        SET NormalPV = t.NormalPV
                        FROM temp_daily AS t
                        WHERE substr(f.Date, 6) = t.MD AND f.MinuteOfDay = t.MinuteOfDay
        """)
        cur.execute(""" DROP TABLE temp_daily
        """)
        cur.execute(""" DROP TABLE temp_sums
        """)
        conn.commit()
        conn.close()
    except Error as e:
        print(e)
    return

def main():
    env = {}
    with open(CONFIG + "EnvProperties.json", 'r') as f:
        env = json.load(f)
    dbFile = env["StorageFolder"] + env["DBFileName"]

    
    _loadDefaultSolar(dbFile)
    
if __name__ == "__main__":
    try:
        CONFIG = sys.argv[1]
    except:
        pass
    # print(CONFIG)
    main()