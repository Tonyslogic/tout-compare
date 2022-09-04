import asyncio
import decimal
import logging
import json
import os
from string import Template
import sys
import sqlite3
from sqlite3 import Error

import PySimpleGUI as sg 

import aiohttp

CONFIG = "C:\\dev\\solar\\"
MGN = 919821

URL = Template( "https://re.jrc.ec.europa.eu/api/v5_2/seriescalc?lat=$LAT&lon=$LON&raddatabase=PVGIS-SARAH2&browser=1&outputformat=json&userhorizon=&usehorizon=1&angle=$SLOPE&aspect=$AZIMUTH&startyear=2020&endyear=2020&mountingplace=&optimalinclination=0&optimalangles=0&js=1&select_database_hourly=PVGIS-SARAH2&hstartyear=2020&hendyear=2020&trackingtype=0&hourlyangle=$SLOPE&hourlyaspect=$AZIMUTH")

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
        cur = conn.cursor()
        cur.executemany('INSERT INTO pvgis VALUES(?,?,?);',rows)
        cur.execute(""" UPDATE dailystats AS f
                        SET NormalPV = t.PV
                        FROM pvgis AS t
                        WHERE substr(f.Date, 6) = t.Date AND f.MinuteOfDay = t.MinuteOfDay
        """)
        cur.execute(""" UPDATE dailysums AS f
                        SET PV = t.PV
                        FROM (SELECT date, SUM (NormalPV) AS PV FROM dailystats GROUP BY date ORDER BY date) AS t
                        WHERE f.Date = t.Date
        """)
        cur.execute(""" DROP TABLE pvgis
        """)
        conn.commit()
        conn.close()
    except Error as e:
        print(e)

def _createDBTable(dbFile):
    conn = None
    try:
        conn = sqlite3.connect(dbFile)
        conn.execute("DROP TABLE IF EXISTS pvgis")
        conn.commit()
        conn.execute("CREATE TABLE IF NOT EXISTS pvgis ( \
                        Date TEXT NOT NULL, \
                        MinuteOfDay TEXT    NOT NULL, \
                        PV REAL    NOT NULL, \
                        PRIMARY KEY (Date, MinuteOfDay));")
        # print("pvgis created")
        conn.commit()
        conn.close()
    except Error as e:
        print(e)

def _create_rows(strings, dedicatedMPPT):
    ret = []
    stringCount = len(strings)
    
    for idx, hour in enumerate(strings[0]["data"]['outputs']['hourly']):
        date = hour["time"][4:6] + "-" + hour["time"][6:8]
        hr = hour["time"][9:11]
        power = hour["G(i)"] / 12 # to get 5mins
        PV = (power/MGN) * strings[0]["Panels"] * strings[0]["Wp"]
        if stringCount == 2:
            power2 = strings[1]["data"]['outputs']['hourly'][idx]["G(i)"] / 12
            PV2 = (power2/MGN) * strings[1]["Panels"] * strings[1]["Wp"]
            if dedicatedMPPT:
                PV += PV2
            else:
                PV = max(PV, PV2)
        for x in range (0, 12):
            minute = int(hr) * 60 + x * 5
            ret.append([date, minute, PV])
    
    # logger.info(f"Counted {len(ret)/24} rows")
    return ret

def _renderPanelNav():
    left_col = []
    left_col.append([sg.Text('Get solar data for your specific layout. Data is sourced from \'https://re.jrc.ec.europa.eu/pvg_tools/en/\'', size=(80,1))])
    left_col.append([sg.Text('Up to two strings can be configured for the same loaction. If each string is attached to the inverter (Dedicated MPPT), then the PV generationis the sum of the strings. Otherwise the max value is taken.', size=(80,2))])
    left_col.append([sg.Text('==============================================================================', size=(80,1))])
    left_col.append([sg.Text('Latitude', size=(15,1)), sg.In(size=(15,1), enable_events=True ,key='-LAT-', default_text="53.490"), sg.Text('Longditude', size=(15,1)), sg.In(size=(15,1), enable_events=True ,key='-LON-', default_text="-10.015")])
    left_col.append([sg.Text('==============================================================================', size=(80,1))])
    left_col.append([sg.Checkbox('Second string', size=(27,1), default=False, enable_events=True, key='-2NDSTRING-'),
                    sg.Checkbox('Dedicated MPPT', size=(27,1), disabled=True, default=False, key='-DEDICATED-')])
    left_col.append([sg.Text('Slope', size=(15,1)),sg.In(size=(15,1), enable_events=True ,key='-SLOPE1-', default_text="25"),
                    sg.Text('2nd string slope', size=(15,1)),sg.In(size=(15,1), disabled=True, enable_events=True ,key='-SLOPE2-', default_text="25")])
    left_col.append([sg.Text('Azimuth', size=(15,1)),sg.In(size=(15,1), enable_events=True ,key='-AZI1-', default_text="90"),
                    sg.Text('2nd string azimuth', size=(15,1)),sg.In(size=(15,1), disabled=True, enable_events=True ,key='-AZI2-', default_text="180")])
    left_col.append([sg.Text('Panels', size=(15,1)),sg.In(size=(15,1), enable_events=True ,key='-PAN1-', default_text="7"),
                    sg.Text('2nd string panels', size=(15,1)),sg.In(size=(15,1), disabled=True, enable_events=True ,key='-PAN2-', default_text="7")])
    left_col.append([sg.Text('Wp', size=(15,1)),sg.In(size=(15,1), enable_events=True ,key='-WP1-', default_text="325"),
                    sg.Text('2nd string Wp', size=(15,1)),sg.In(size=(15,1), disabled=True, enable_events=True ,key='-WP2-', default_text="325")])
    left_col.append([sg.Text('==============================================================================', size=(80,1))])
    left_col.append([sg.Button('Fetch & Load DB', size=(24,1), key='-FETCH_SOLAR-', disabled=False)])
    layout = [[sg.Column(left_col, element_justification='l')]]    
    window = sg.Window('Solar data retrieval', layout,resizable=True)
    return window

def _getPanelsGUI():
    panels = None
    secondString = False
    
    nav_window = _renderPanelNav()
    while True:
        event, values = nav_window.Read()
        if event in (sg.WIN_CLOSED, 'Exit'): break
        if event == '-2NDSTRING-':
            secondString = not values["-2NDSTRING-"]
            nav_window['-DEDICATED-'].update(disabled=secondString)
            nav_window['-SLOPE2-'].update(disabled=secondString)
            nav_window['-AZI2-'].update(disabled=secondString)
            nav_window['-PAN2-'].update(disabled=secondString)
            nav_window['-WP2-'].update(disabled=secondString)
        if event == '-FETCH_SOLAR-':
            panels = {}
            panels["Location"] = {"Latitude": values['-LAT-'], "Longitude": values['-LON-']}
            panels["DedicatedMPPTs"] = values['-DEDICATED-']
            panels["Strings"] = []
            decimal.getcontext().prec = 3
            az1 = decimal.Decimal(values['-AZI1-'])
            if az1 > 180: az1 = 360 - az1
            panels["Strings"].append({"Slope": float(values['-SLOPE1-']), "Azimuth": str(az1), "Panels": int(values['-PAN1-']), "Wp": float(values['-WP1-'])})
            if values["-2NDSTRING-"]:
                az2 = decimal.Decimal(values['-AZI2-'])
                if az2 > 180: az2 = 360 -az2
                panels["Strings"].append({"Slope": float(values['-SLOPE2-']), "Azimuth": str(az2), "Panels": int(values['-PAN2-']), "Wp": float(values['-WP2-'])})
            # print (panels)
            nav_window.close()
            break

    return panels

def guiPVgis(config):
    global CONFIG
    CONFIG = config
    panels = _getPanelsGUI()
    if panels is not None: main(panels)

async def _getDataFromPVGIS(slope, azimuth, latitude, longitude):
    ret = {}
    url = URL.substitute({'LAT': latitude, 'LON': longitude, 'SLOPE': slope, 'AZIMUTH': azimuth})
    async with aiohttp.ClientSession() as session:
            response = await session.get(url)

            try:
                response.raise_for_status()
            except:
                pass
            if response.status != 200:
                print(response)
                return None

            json_response = await response.json()

            if "outputs" in json_response:
                if json_response["outputs"] is not None:
                    return json_response
                else:
                    return None
    return ret

def main(panels):
    
    env = {}
    with open(os.path.join(CONFIG, "EnvProperties.json"), 'r') as f:
        env = json.load(f)
    storageFolder = env["StorageFolder"]
    dbFileName = env["DBFileName"]

    for string in panels["Strings"]:
        string["data"] =  asyncio.get_event_loop().run_until_complete(_getDataFromPVGIS(string["Slope"], string["Azimuth"], panels["Location"]["Latitude"], panels["Location"]["Longitude"]))
    rows = _create_rows (panels["Strings"], panels["DedicatedMPPTs"])
    # print (len(rows))

    dbFile = os.path.join(storageFolder, dbFileName)
    _createDBTable(dbFile)
    _fillDB(dbFile, rows)

if __name__ == "__main__":
    try:
        CONFIG = sys.argv[1]
    except:
        pass
    print(CONFIG)
    panels = {}
    panels["Location"] = {"Latitude": 53.626, "Longitude": -8.171}
    panels["DedicatedMPPTs"] = True
    panels["Strings"] = []
    panels["Strings"].append({"Slope": 24, "Azimuth": 136, "Panels": 13, "Wp": 325})
    panels["Strings"].append({"Slope": 24, "Azimuth": 226, "Panels": 13, "Wp": 325})
    # main(panels)
    guiPVgis(CONFIG)