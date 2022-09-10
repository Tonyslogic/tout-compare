import logging
import asyncio
from os import stat
import os
import sys
import datetime
import json
import threading


from dataPopulation.alphaess.alphaess import alphaess

CONFIG = "C:\\dev\\solar\\"

USERNAME = "" # input("username: ")
PASSWORD = "" # input("password: ")
START = "" # input("start date (YYYY-MM-DD): ")
FINISH = "" # input("finish date (YYYY-MM-DD): ")
FETCH_START = ""
async_loop = None

logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('[%(asctime)s] %(levelname)s [%(filename)s.%(funcName)s:%(lineno)d] %(message)s', datefmt='%a, %d %b %Y %H:%M:%S')
handler.setFormatter(formatter)
logger.addHandler(handler)

def _loadExistingData(storageFolder):
    ret = {}
    latest = datetime.datetime.strptime('2021-04-01', '%Y-%m-%d')
    try:
        with open(os.path.join(storageFolder, "dailystats.json"), 'r') as f:
            ret = json.load(f)
    except:
        return None, None
    for day in ret[0]['statistics']:
        for entry in day:
            theDate = entry
            try: 
                dt = datetime.datetime.strptime(theDate, '%Y-%m-%d')
                # print(theDate)
                if dt > latest: latest = dt
            except ValueError:
                print("looking at dodgy data" + theDate) 
            # print 'a' if a > b else 'b' if b > a else 'tie'
    last = datetime.datetime.strftime(latest, '%Y-%m-%d')
    # print(last)
    return ret, last

def guiFetch(user, passwd, start, end, config): 
    global USERNAME, PASSWORD, START, FINISH, CONFIG, async_loop
    USERNAME = user
    PASSWORD = passwd
    START = start
    FINISH = end
    CONFIG = config
    with open(os.path.join(CONFIG, "EnvProperties.json"), 'r') as f:
        env = json.load(f)
    storageFolder = env["StorageFolder"]
    useOldData, oldData, getNewData = _prepare(storageFolder)
    if getNewData == True: 
        print("Getting new data")
        asyncio.get_event_loop().run_until_complete(_fetch(useOldData, oldData, storageFolder))
    else: print ("Not fetching new data")

async def _fetch(useOldData, old_data, storageFolder):
    logger.debug("instantiating Alpha ESS Client")

    client: alphaess = alphaess()

    logger.debug("Checking authentication")
    authenticated = await client.authenticate(USERNAME, PASSWORD)

    if authenticated:
        data = await client.getdata(FETCH_START, FINISH)
        count = len(data[0]["statistics"])
        logger.info(f"Got data: {count}")
        if useOldData:
            dataToUse = old_data
            dataToUse[0]["statistics"].extend(data[0]["statistics"])
        else:
            dataToUse = data
        with open(os.path.join(storageFolder, "dailystats.json"), 'w') as f:
            json.dump(dataToUse, f)
    return

def _prepare(storageFolder):
    global START
    global FETCH_START
    global CONFIG
    
    useOldData = True
    getNewData = False
    old_data = {}
    
    old_data, latest = _loadExistingData(storageFolder)
    try:
        fin = datetime.datetime.strptime(FINISH, '%Y-%m-%d')
        bgn = datetime.datetime.strptime(START, '%Y-%m-%d')
        fnd = datetime.datetime.strptime(latest, '%Y-%m-%d')
        if fnd < fin:
            dt = fnd + datetime.timedelta(days=1)
            FETCH_START = datetime.datetime.strftime(dt, '%Y-%m-%d')
            useOldData = True
            getNewData = True
            print ("Updating start to " + FETCH_START)
        if fnd >= fin:
            print ("already have data to " + latest + ". Exiting")
            # return useOldData, old_data, getNewData
    except:
        pass
    return useOldData, old_data, getNewData