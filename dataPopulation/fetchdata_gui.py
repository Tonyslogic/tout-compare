import logging
import asyncio
from os import stat
import os
import sys
import datetime
import json
import threading
import time

from dataPopulation.alphaess.alphaess import alphaess

CONFIG = "C:\\dev\\solar\\"
ASYNC_LOOP = None

logger = logging.getLogger('')
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('[%(asctime)s] %(levelname)s [%(filename)s.%(funcName)s:%(lineno)d] %(message)s', datefmt='%a, %d %b %Y %H:%M:%S')
handler.setFormatter(formatter)
logger.addHandler(handler)

def _loadExistingData(storageFolder):
    ret = [{"statistics": []}]
    try:
        with open(os.path.join(storageFolder, "dailystats.json"), 'r') as f:
            ret = json.load(f)
    except:
        return ret, []
    dates = []
    for entry in ret[0]['statistics']:
        dates.extend(entry.keys())
    sorteddates=sorted(dates, key=lambda x:x)
    return ret, sorteddates

def guiFetch(user, passwd, start, end, config): 
    global CONFIG, ASYNC_LOOP
    CONFIG = config
    with open(os.path.join(CONFIG, "EnvProperties.json"), 'r') as f:
        env = json.load(f)
    storageFolder = env["StorageFolder"]
    old_data, cachedDates = _loadExistingData(storageFolder)
    try:
        finish = datetime.datetime.strptime(end, '%Y-%m-%d')
        begin = datetime.datetime.strptime(start, '%Y-%m-%d')
        stats, units = asyncio.get_event_loop().run_until_complete( _fetch(user, passwd, begin, finish, cachedDates) )
        if "sys_sn" not in old_data[0]:
            print ("Missing meta-data")
            del units[0]['statistics']
            old_data[0].update(units[0])
            print (old_data[0])
        old_data[0]['statistics'].extend(stats)
        with open(os.path.join(storageFolder, "dailystats.json"), 'w') as f:
            json.dump(old_data, f)
    except Exception as e:
        print('%s : %s' % (type(e).__name__, str(e)))

async def _fetch(user, passwd, start, end, cachedDates):
    stats = []
    units = []
    print("instantiating Alpha ESS Client")

    client: alphaess = alphaess()

    print("Checking authentication")
    authenticated = await client.authenticate(user, passwd)

    if authenticated:
        print ("Authenticated")
        delta = datetime.timedelta(days=1)
        workingDay = start
        while workingDay <= end:
            if workingDay.strftime("%Y-%m-%d") not in cachedDates:
                print ("Fetching data for " + workingDay.strftime("%Y-%m-%d"))
                data, units = await client.getOneDayStatsData(workingDay.strftime("%Y-%m-%d"))
                if data:
                    for entry in data:
                        for key, value in entry.items():
                            stats.append({key :value['statistics']})
                time.sleep(0.7)
            else:  
                print ("Already had data for " + workingDay.strftime("%Y-%m-%d") + ", skipping" )
            workingDay += delta
    return stats, units