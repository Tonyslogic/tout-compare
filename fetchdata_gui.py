import logging
import asyncio
from os import stat
import os
import sys
import datetime
import json


from alphaess.alphaess import alphaess

CONFIG = "C:\\dev\\solar\\"

USERNAME = "" # input("username: ")
PASSWORD = "" # input("password: ")
START = "" # input("start date (YYYY-MM-DD): ")
FINISH = "" # input("finish date (YYYY-MM-DD): ")

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
    global USERNAME, PASSWORD, START, FINISH, CONFIG
    USERNAME = user
    PASSWORD = passwd
    START = start
    FINISH = end
    CONFIG = config
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())


async def main():
    global START
    global CONFIG
    
    # try:
    #     CONFIG = sys.argv[1]
    # except:
    #     pass
    # print(CONFIG)
    
    useOldData = False
    
    env = {}
    with open(os.path.join(CONFIG, "EnvProperties.json"), 'r') as f:
        env = json.load(f)
    storageFolder = env["StorageFolder"]
    
    old_data, latest = _loadExistingData(storageFolder)
    try:
        fin = datetime.datetime.strptime(FINISH, '%Y-%m-%d')
        bgn = datetime.datetime.strptime(START, '%Y-%m-%d')
        fnd = datetime.datetime.strptime(latest, '%Y-%m-%d')
        if fnd < fin:
            dt = fnd + datetime.timedelta(days=1)
            START = datetime.datetime.strftime(dt, '%Y-%m-%d')
            useOldData = True
            print ("Updating start to " + START)
        if fnd > fin:
            print ("already have data to " + latest + ". Exiting")
            sys.exit(0)
    except:
        pass
    # sys.exit(0)

    logger.debug("instantiating Alpha ESS Client")

    client: alphaess = alphaess()

    logger.debug("Checking authentication")
    authenticated = await client.authenticate(USERNAME, PASSWORD)

    if authenticated:
        data = await client.getdata(START, FINISH)
        count = len(data[0]["statistics"])
        logger.info(f"Got data: {count}")
        if useOldData:
            dataToUse = old_data
            dataToUse[0]["statistics"].extend(data[0]["statistics"])
        else:
            dataToUse = data
        with open(os.path.join(storageFolder, "dailystats.json"), 'w') as f:
            json.dump(dataToUse, f)

# asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
# asyncio.run(main())
