import json
from locale import locale_encoding_alias
import sqlite3
import PySimpleGUI as sg 
import os

from numpy import disp

from simulate import guiMain
from fetchdata_gui import guiFetch
from makedb import guiMakeDB
from makedbFromProfile import _guiDBFromProfile
from windowRates import getRates, _updateRates
from loadDefaultSolar import loadDefaultSolar
from reportdb import display
from pvgis2db import guiPVgis
from demodefaults import DEMO_START, DEMO_ANNUAL, DEMO_BASE, DEMO_MONTHLYDIST, DEMO_DOWDIST, DEMO_HOURLYDIST, DEMO_RATES, DEMO_SYSTEM

MAIN_WINDOW = None

CONFIG = "C:\\dev\\solar\\"
STORAGE = "C:\\dev\\solar\\"
DBFILE = "SimData.db"

STATUS_BASIC_CONFIG = False
STATUS_SYS_CONFIG = False
STATUS_SCENARIOS = False
STATUS_LOAD = False
STATUS_PV = False
STATUS_RATES = False

def _saveDemoConfig(): 
    # SystemProperties.json
    _updateSysConfig(DEMO_SYSTEM)
    # rates.json
    _updateRates(DEMO_RATES)
    # loadProfile.json
    profile = {}
    profile["AnnualUsage"] = DEMO_ANNUAL
    profile["HourlyBaseLoad"] = DEMO_BASE
    profile["MonthlyDistribution"] = DEMO_MONTHLYDIST
    profile["DayOfWeekDistribution"] = DEMO_DOWDIST
    profile["HourlyDistribution"] = DEMO_HOURLYDIST
    _saveProfile(profile)
    # populateDB 
    _guiDBFromProfile(CONFIG, DEMO_START)
    # solar 
    dbFile = os.path.join(STORAGE, DBFILE)
    loadDefaultSolar(CONFIG, dbFile)
    
    _setStatus()
    return

def _writeEnv():
    data = {}
    data["StorageFolder"] = STORAGE
    data["ConfigFolder"] = CONFIG
    data["DBFileName"] = DBFILE

    with open(os.path.join(CONFIG, "EnvProperties.json"), 'w') as f:
        json.dump(data, f)
    return

def _getConfig():
    global CONFIG
    global STORAGE
    global DBFILE

    enableSave = not os.path.isdir(CONFIG) and not os.path.isdir(STORAGE)
    enableDemo = not os.path.isfile(os.path.join(CONFIG, "EnvProperties.json"))

    left_col = [
            [sg.Text('Configuration Folder', size=(24,1)), sg.In(size=(25,1), enable_events=True ,key='-C_FOLDER-', default_text=CONFIG), sg.FolderBrowse()],
            [sg.Text('Storage Folder', size=(24,1)), sg.In(size=(25,1), enable_events=True ,key='-S_FOLDER-', default_text=STORAGE), sg.FolderBrowse()],
            [sg.Text('DB Filename', size=(24,1)), sg.In(size=(25,1), enable_events=True ,key='-DB_NAME-', default_text=DBFILE)],
            [sg.Button('Save', key='-CONFIG_OK-', disabled=enableSave, size=(15,1)), sg.Button('Add Demo data', key='-DEMO-', disabled=enableDemo, size=(15,1)), sg.Button('Close', key='-CLOSE-', size=(15,1)) ]
    ]
    layout = [[sg.Column(left_col, element_justification='l')]]    
    window = sg.Window('Time of use comparison -- config', layout,resizable=True)
        
    cfolder = CONFIG
    sfolder = STORAGE
    dbFile = DBFILE
    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, 'Exit'): break
        if event == '-C_FOLDER-': 
            cfolder = values['-C_FOLDER-']
            if os.path.isdir(cfolder) and os.path.isdir(sfolder):
                window['-CONFIG_OK-'].update(disabled=False) 
        if event == '-S_FOLDER-': 
            sfolder = values['-S_FOLDER-'] 
            if os.path.isdir(cfolder) and os.path.isdir(sfolder):
                window['-CONFIG_OK-'].update(disabled=False) 
        if event == '-DB_NAME-': dbFile = values['-DB_NAME-']
        if event == '-DEMO-':
            _saveDemoConfig()
        if event == '-CLOSE-':
            window.close()
            break
        if event == '-CONFIG_OK-':
            CONFIG = cfolder
            STORAGE = sfolder
            DBFILE = dbFile
            if os.path.isdir(cfolder) and os.path.isdir(sfolder):
                _writeEnv()
                _setStatus()
                window['-DEMO-'].update(disabled=False) 

def _loadSysConfig():
    global STATUS_SYS_CONFIG
    data = {}
    try: 
        with open(os.path.join(CONFIG, "SystemProperties.json"), 'r') as f:
            data = json.load(f)
        STATUS_SYS_CONFIG = True
        MAIN_WINDOW['-SYS_CONFIG_STAT-'].update(value="System config found")
    except:
        STATUS_SYS_CONFIG = False
        data = {"Battery Size": 5.7, "Original panels": 14, "Discharge stop": 19.6, "Min excess": 0.008, "Max discharge": 0.225, "Max charge": 0.225, "Max Inverter load": 5.0, "Massage FeedIn": 87.5, "Massage Buy": 94.5, "(Dis)charge loss": 4, "ChargeModel": {"0": 30, "12": 100, "90": 10, "100": 0}}
        MAIN_WINDOW['-SYS_CONFIG_STAT-'].update(value="System config not found")
    return data

def _loadRates():
    global STATUS_RATES
    data = {}
    try: 
        with open(os.path.join(CONFIG, "rates.json"), 'r') as f:
           data = json.load(f)
        MAIN_WINDOW['-RATES_STAT-'].update(value="Found " + str(len(data)) + " pricing plans")
        STATUS_RATES = True
    except:
        MAIN_WINDOW['-RATES_STAT-'].update(value="No vendor rates defined")
        STATUS_RATES = False
    return data

def _updateSysConfig(data):
    with open(os.path.join(CONFIG, "SystemProperties.json"), 'w') as f:
        json.dump(data, f)
    return

def _getSysConfig():
    data = _loadSysConfig()
    cm = data["ChargeModel"]

    left_col = [
            [sg.Text('Battery size (KWH)', size=(35,1)), sg.In(size=(10,1), enable_events=True ,key='-BATTERY_SIZE-', default_text=data["Battery Size"])],
            [sg.Text('Number of panels', size=(35,1)), sg.In(size=(10,1), enable_events=True ,key='-ORIGINAL_PANELS-', default_text=data["Original panels"])],
            [sg.Text('Discharge stop (%)', size=(35,1)), sg.In(size=(10,1), enable_events=True ,key='-DISCHARGE_STOP-', default_text=data["Discharge stop"])],
            [sg.Text('Minimum solar excess (KWH)', size=(35,1)), sg.In(size=(10,1), enable_events=True ,key='-MIN_EXCESS-', default_text=data["Min excess"])],
            [sg.Text('The maximum charge rate (KWH)', size=(35,1)), sg.In(size=(10,1), enable_events=True ,key='-MAX_CHARGE-', default_text=data["Max charge"])],
            [sg.Text('The maximum dsicharge rate (KWH)', size=(35,1)), sg.In(size=(10,1), enable_events=True ,key='-MAX_DISCHARGE-', default_text=data["Max discharge"])],
            [sg.Text('The percentage of PV that is fed in (%)', size=(35,1)), sg.In(size=(10,1), enable_events=True ,key='-FIX_FEEDIN-', default_text=data["Massage FeedIn"])],
            [sg.Text('The buy massage (%)', size=(35,1)), sg.In(size=(10,1), enable_events=True ,key='-FIX_BUY-', default_text=data["Massage Buy"])],
            [sg.Text('Loss related to storage (%)', size=(35,1)), sg.In(size=(10,1), enable_events=True ,key='-DISCHARGE_LOSS-', default_text=data["(Dis)charge loss"])],
            [sg.Text('Max that the inverter can provide (KWH)', size=(35,1)), sg.In(size=(10,1), enable_events=True ,key='-MAX_INVERTER_LOAD-', default_text=data["Max Inverter load"])],
            
            [sg.Text('Charge model from 0-12 (%)', size=(35,1)), sg.In(size=(10,1), enable_events=True ,key='-CM_0_12-', default_text=cm["0"])],
            [sg.Text('Charge model from 12-90 (%)', size=(35,1)), sg.In(size=(10,1), enable_events=True ,key='-CM_12_90-', default_text=cm["12"])],
            [sg.Text('Charge model from 90-100 (%)', size=(35,1)), sg.In(size=(10,1), enable_events=True ,key='-CM_90_100-', default_text=cm["90"])],
            [sg.Text('Charge model from 100 (%)', size=(35,1)), sg.In(size=(10,1), enable_events=True ,key='-CM_100-', default_text=cm["100"])],
            [sg.Button('Update', key='-UPDATE_SYS_CFG-')]
    ]
    layout = [[sg.Column(left_col, element_justification='l')]]    
    window = sg.Window('Time of use comparison -- system config', layout,resizable=True)
        
    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, 'Exit'): break
        try: 
            if event == '-BATTERY_SIZE-': data["Battery Size"] = float(values['-BATTERY_SIZE-']) 
            if event == '-ORIGINAL_PANELS-': data["Original panels"] = int(values['-ORIGINAL_PANELS-'])
            if event == '-DISCHARGE_STOP-': data["Discharge stop"] = float(values['-DISCHARGE_STOP-'])  
            if event == '-MIN_EXCESS-': data["Min excess"] = float(values['-MIN_EXCESS-'])  
            if event == '-MAX_CHARGE-': data["Max charge"] = float(values['-MAX_CHARGE-']  )
            if event == '-MAX_DISCHARGE-': data["Max discharge"] = float(values['-MAX_DISCHARGE-'])
            if event == '-FIX_FEEDIN-': data["Massage FeedIn"] = float(values['-FIX_FEEDIN-'])
            if event == '-FIX_BUY-': data["Massage Buy"] = float(values['-FIX_BUY-'])  
            if event == '-DISCHARGE_LOSS-': data["(Dis)charge loss"] = int(values['-DISCHARGE_LOSS-'])  
            if event == '-MAX_INVERTER_LOAD-': data["Max Inverter load"] = float(values['-MAX_INVERTER_LOAD-']) 

            if event == '-CM_0_12-': cm["0"] = int(values['-CM_0_12-'])
            if event == '-CM_12_90-': cm["12"] = int(values['-CM_12_90-'])
            if event == '-CM_90_100-': cm["90"] = int(values['-CM_90_100-'])
            if event == '-CM_100-': cm["100"] = int(values['-CM_100-'])
            window['-UPDATE_SYS_CFG-'].update(disabled=False)
        except:
            window['-UPDATE_SYS_CFG-'].update(disabled=True)

        if event == '-UPDATE_SYS_CFG-':
            data["ChargeModel"] = cm
            _updateSysConfig(data)
            MAIN_WINDOW['-SYS_CONFIG_STAT-'].update(value="System config found")
            window.close()
            break

    return

def _loadBasicConfig():
    global STATUS_BASIC_CONFIG
    global CONFIG
    global STORAGE
    global DBFILE
    data = {}
    try: 
        with open(os.path.join(CONFIG, "EnvProperties.json"), 'r') as f:
            data = json.load(f)
        STATUS_BASIC_CONFIG = True
        CONFIG = data["ConfigFolder"]
        STORAGE = data["StorageFolder"]
        DBFILE = data["DBFileName"]
        MAIN_WINDOW['-CONFIG_STAT-'].update(value="Basic config found")
    except:
        STATUS_BASIC_CONFIG = False
        MAIN_WINDOW['-CONFIG_STAT-'].update(value="Basic config not found")
    return data

def _setStatus():
    _loadBasicConfig()
    data = _loadSysConfig()
    try:
        scenarios = data["Scenarios"]
        count = len(scenarios)
        if count > 0:
            MAIN_WINDOW['-SCENARIOS_STAT-'].update(value="Found " + str(count) + " scenarios")
            STATUS_SCENARIOS = True
        else: 
            MAIN_WINDOW['-SCENARIOS_STAT-'].update(value="No scenarios found")
            STATUS_SCENARIOS = False
    except:
        MAIN_WINDOW['-SCENARIOS_STAT-'].update(value="No scenarios found")
        STATUS_SCENARIOS = False

    try:
        dbFile = os.path.join(STORAGE, DBFILE)
        conn = sqlite3.connect(dbFile)
        cur = conn.cursor()
        cur.execute("SELECT min(Date), max(Date) FROM dailysums WHERE Load > 0")
        res = cur.fetchone()
        conn.close()
        MAIN_WINDOW['-PROFILE_STAT-'].update(value="Found load data from " + res[0] + " to " + res[1])
        STATUS_LOAD = True
    except:
        MAIN_WINDOW['-PROFILE_STAT-'].update(value="No load data found in DB")
        STATUS_LOAD = False
    
    try:
        zeroed = " "
        dbFile = os.path.join(STORAGE, DBFILE)
        conn = sqlite3.connect(dbFile)
        cur = conn.cursor()
        cur.execute("SELECT min(Date), max(Date) FROM dailysums WHERE PV > 0")
        res = cur.fetchone()
        # print(res[0])
        if res[0] == None:
            cur.execute("SELECT min(Date), max(Date) FROM dailysums")
            res = cur.fetchone() 
            zeroed = " zeroed "   
        conn.close()
        MAIN_WINDOW['-SOLAR_DATA_STAT-'].update(value="Found" + zeroed + "PV data from " + res[0] + " to " + res[1])
        STATUS_PV = True
    except:
        MAIN_WINDOW['-SOLAR_DATA_STAT-'].update(value="No PV data found in DB")
        STATUS_PV = False

    _loadRates()

    if (STATUS_LOAD or STATUS_PV):
        MAIN_WINDOW['-REPORTDB-'].update(disabled=False)
    else:
        MAIN_WINDOW['-REPORTDB-'].update(disabled=True)

    if (STATUS_BASIC_CONFIG and STATUS_SYS_CONFIG and STATUS_SCENARIOS and STATUS_LOAD and STATUS_PV and STATUS_RATES):
        MAIN_WINDOW['-SIMULATE-'].update(disabled=False)
    else:
        MAIN_WINDOW['-SIMULATE-'].update(disabled=True)
    
    if not STATUS_BASIC_CONFIG:
        MAIN_WINDOW['-SYS_CONFIG-'].update(disabled=True)
        MAIN_WINDOW['-SCENARIOS-'].update(disabled=True)
        MAIN_WINDOW['-PROFILE-'].update(disabled=True)
        MAIN_WINDOW['-SOLAR_DATA-'].update(disabled=True)
        MAIN_WINDOW['-RATES-'].update(disabled=True)
    else:
        MAIN_WINDOW['-SYS_CONFIG-'].update(disabled=False)
        MAIN_WINDOW['-SCENARIOS-'].update(disabled=False)
        MAIN_WINDOW['-PROFILE-'].update(disabled=False)
        MAIN_WINDOW['-SOLAR_DATA-'].update(disabled=False)
        MAIN_WINDOW['-RATES-'].update(disabled=False)
    return

def _renderLoadShift(loadShift):
    left_col = []
    left_col.append([sg.Text('Load shifting is charging a battery when electricity prices are lower and using the battery when prices are higher. Load shifting is most useful when solar generation is low. Load shifting can be configured several times. Each configuration (time and charge) is applied in the months slected.', size=(150,2))])
    left_col.append([sg.Text('======================================================================================================================================================', size=(150,1))])
    for i, shift in enumerate(loadShift):
        left_col.append([
            sg.Text('Begin charging at (hr)', size=(25,1)), sg.In(size=(25,1), enable_events=True ,key='-LS_BEGIN' + str(i), default_text=shift["begin"]),
            sg.Text('End charging at (hr)', size=(25,1)), sg.In(size=(25,1), enable_events=True ,key='-LS_END' + str(i), default_text=shift["end"]),
            sg.Text('Stop when battery at (%)', size=(25,1)), sg.In(size=(25,1), enable_events=True ,key='-LS_STOP' + str(i), default_text=shift["stop at"])
            ])
        left_col.append([
            sg.Text('Applicable months:', size=(25,1)),
            sg.Checkbox('Jan', size=(5,1), default=1 in shift["months"], key='-LS_MONTH_1' + str(i)),
            sg.Checkbox('Feb', size=(5,1), default=2 in shift["months"], key='-LS_MONTH_2' + str(i)),
            sg.Checkbox('Mar', size=(5,1), default=3 in shift["months"], key='-LS_MONTH_3' + str(i)),
            sg.Checkbox('Apr', size=(5,1), default=4 in shift["months"], key='-LS_MONTH_4' + str(i)),
            sg.Checkbox('May', size=(5,1), default=5 in shift["months"], key='-LS_MONTH_5' + str(i)),
            sg.Checkbox('Jun', size=(5,1), default=6 in shift["months"], key='-LS_MONTH_6' + str(i)),
            sg.Checkbox('Jul', size=(5,1), default=7 in shift["months"], key='-LS_MONTH_7' + str(i)),
            sg.Checkbox('Aug', size=(5,1), default=8 in shift["months"], key='-LS_MONTH_8' + str(i)),
            sg.Checkbox('Sep', size=(5,1), default=9 in shift["months"], key='-LS_MONTH_9' + str(i)),
            sg.Checkbox('Oct', size=(5,1), default=10 in shift["months"], key='-LS_MONTH_A' + str(i)),
            sg.Checkbox('Nov', size=(5,1), default=11 in shift["months"], key='-LS_MONTH_B' + str(i)),
            sg.Checkbox('Dec', size=(5,1), default=12 in shift["months"], key='-LS_MONTH_C' + str(i)),
        ])
        left_col.append([sg.Text('======================================================================================================================================================', size=(150,1))])
    left_col.append([sg.Button('Add a load shift configuration', key='-ADD_LS-')]),
    left_col.append([sg.Button('Done editing load shift', key='-UPDATE_LS-')])
    layout = [[sg.Column(left_col, element_justification='l')]]    
    window = sg.Window('Load shift editor', layout,resizable=True)
        
    return window

def _editLoadShift(loadShift):
    lsWindow = _renderLoadShift(loadShift)
    while True:
        event, values = lsWindow.read()
        # print(event)
        if event in (sg.WIN_CLOSED, 'Exit'): break
        if event == '-ADD_LS-': 
            loadShift.append({"stop at": 80, "begin": 2, "end": 4, "months": [1,2,3,4,5,6,7,8,9,10,11,12]})
            lsWindow.close()
            lsWindow = _renderLoadShift(loadShift)
        if event == '-UPDATE_LS-':
            newLoadShift = []
            for i, _ in enumerate(loadShift):
                shift = {}
                months = [1,2,3,4,5,6,7,8,9,10,11,12]
                # print (values)
                for key, value in values.items():
                    if str(key).endswith(str(i)):
                        if str(key).startswith('-LS_MONTH_'):
                            if value:
                                months.append(int(key[-2],16))
                        if str(key).startswith('-LS_BEGIN'):
                            shift["begin"] = int(value)
                        if str(key).startswith('-LS_END'):
                            shift["end"] = int(value)
                        if str(key).startswith('-LS_STOP'):
                            shift["stop at"] = int(value)
                shift["months"] = months
                newLoadShift.append(shift)
                loadShift = newLoadShift
            # print(loadShift)
            lsWindow.close()
            break
    return loadShift

def _renderCarCharge(carCharge):
    left_col = []
    left_col.append([sg.Text('Car charging allows you to explore the impacts of charging a car at various times. Times, days and months are used to apply additional load. The additional load is specified in KWH. In the future, diverters (automatically use surplus solar) may be added.', size=(150,2))])
    left_col.append([sg.Text('======================================================================================================================================================', size=(150,1))])
    for i, charge in enumerate(carCharge):
        left_col.append([
            sg.Text('Begin charging at (hr)', size=(25,1)), sg.In(size=(25,1), enable_events=True ,key='-CC_BEGIN' + str(i), default_text=charge["begin"]),
            sg.Text('End charging at (hr)', size=(25,1)), sg.In(size=(25,1), enable_events=True ,key='-CC_END' + str(i), default_text=charge["end"]),
            sg.Text('Electricity draw (KWH)', size=(25,1)), sg.In(size=(25,1), enable_events=True ,key='-CC_STOP' + str(i), default_text=charge["draw"])
            ])
        left_col.append([
            sg.Text('Applicable months:', size=(25,1)),
            sg.Checkbox('Jan', size=(5,1), default=1 in charge["months"], key='-CC_MONTH_1' + str(i)),
            sg.Checkbox('Feb', size=(5,1), default=2 in charge["months"], key='-CC_MONTH_2' + str(i)),
            sg.Checkbox('Mar', size=(5,1), default=3 in charge["months"], key='-CC_MONTH_3' + str(i)),
            sg.Checkbox('Apr', size=(5,1), default=4 in charge["months"], key='-CC_MONTH_4' + str(i)),
            sg.Checkbox('May', size=(5,1), default=5 in charge["months"], key='-CC_MONTH_5' + str(i)),
            sg.Checkbox('Jun', size=(5,1), default=6 in charge["months"], key='-CC_MONTH_6' + str(i)),
            sg.Checkbox('Jul', size=(5,1), default=7 in charge["months"], key='-CC_MONTH_7' + str(i)),
            sg.Checkbox('Aug', size=(5,1), default=8 in charge["months"], key='-CC_MONTH_8' + str(i)),
            sg.Checkbox('Sep', size=(5,1), default=9 in charge["months"], key='-CC_MONTH_9' + str(i)),
            sg.Checkbox('Oct', size=(5,1), default=10 in charge["months"], key='-CC_MONTH_A' + str(i)),
            sg.Checkbox('Nov', size=(5,1), default=11 in charge["months"], key='-CC_MONTH_B' + str(i)),
            sg.Checkbox('Dec', size=(5,1), default=12 in charge["months"], key='-CC_MONTH_C' + str(i)),
        ])
        left_col.append([
            sg.Text('Applicable days:', size=(25,1)),
            sg.Checkbox('Sun', size=(5,1), default=0 in charge["days"], key='-CC_DAY_0' + str(i)),
            sg.Checkbox('Mon', size=(5,1), default=1 in charge["days"], key='-CC_DAY_1' + str(i)),
            sg.Checkbox('Tue', size=(5,1), default=2 in charge["days"], key='-CC_DAY_2' + str(i)),
            sg.Checkbox('Wed', size=(5,1), default=3 in charge["days"], key='-CC_DAY_3' + str(i)),
            sg.Checkbox('Thu', size=(5,1), default=4 in charge["days"], key='-CC_DAY_4' + str(i)),
            sg.Checkbox('Fri', size=(5,1), default=5 in charge["days"], key='-CC_DAY_5' + str(i)),
            sg.Checkbox('Sat', size=(5,1), default=6 in charge["days"], key='-CC_DAY_6' + str(i))
        ])
        left_col.append([sg.Text('======================================================================================================================================================', size=(150,1))])
    left_col.append([sg.Button('Add another car charging schedule entry', key='-ADD_CC-')])
    left_col.append([sg.Button('Done editing the car charge schedule', key='-UPDATE_CC-')])
    layout = [[sg.Column(left_col, element_justification='l')]]    
    window = sg.Window('Car charge load editor', layout,resizable=True)
        
    return window


def _editCarCharge(carCharge):
    ccWindow = _renderCarCharge(carCharge)
    
    while True:
        event, values = ccWindow.read()
        # print(event)
        if event in (sg.WIN_CLOSED, 'Exit'): break
        if event == '-ADD_CC-': 
            carCharge.append({"draw": 7.5, "begin": 2, "end": 4, "months": [1,2,3,4,5,6,7,8,9,10,11,12], "days": [0,1,2,3,4,5,6]})
            ccWindow.close()
            ccWindow = _renderCarCharge(carCharge)
        if event == '-UPDATE_CC-':
            newCarCharge = []
            for i, _ in enumerate(carCharge):
                charge = {}
                months = [1,2,3,4,5,6,7,8,9,10,11,12]
                days = [0,1,2,3,4,5,6]
                # print (values)
                for key, value in values.items():
                    if str(key).endswith(str(i)):
                        if str(key).startswith('-CC_MONTH_'):
                            if value:
                                months.append(int(key[-2],16))
                        if str(key).startswith('-CC_DAY_'):
                            if value:
                                days.append(int(key[-2]))
                        if str(key).startswith('-CC_BEGIN'):
                            charge["begin"] = int(value)
                        if str(key).startswith('-CC_END'):
                            charge["end"] = int(value)
                        if str(key).startswith('-CC_STOP'):
                            charge["draw"] = float(value)
                charge["months"] = months
                charge["days"] = days
                newCarCharge.append(charge)
                carCharge = newCarCharge
            # print(carCharge)
            ccWindow.close()
            break
    return carCharge

def _renderOneScenario(scenario):
    try:
        bat = scenario["Battery Size"]
        pan = scenario["Increaed panels"]
        stop = scenario["Discharge stop"]
    except:
        bat = 5.7
        pan = 14
        stop = 19.6
    left_col = [
            [sg.Text('A what-if scenaio describes additional load and variations to the solar/inverter configuration. Scenarios are visible in the simulation output. Load shifting and Car charging are not mandatory.', size=(50,3))],
            [sg.Text('===================================================', size=(50,1))],
            [sg.Text('Name', size=(25,1)), sg.In(size=(25,1), enable_events=True ,key='-SCENARIO_NAME-', default_text=scenario["Name"])],
            [sg.Text('Battery size (KWH)', size=(25,1)), sg.In(size=(25,1), enable_events=True ,key='-SCENARIO_BATTERY-', default_text=bat)],
            [sg.Text('Number of panels', size=(25,1)), sg.In(size=(25,1), enable_events=True ,key='-SCENARIO_PANELS-', default_text=pan)],
            [sg.Text('Discharge stop (%)', size=(25,1)), sg.In(size=(25,1), enable_events=True ,key='-DISCHARGE_STOP-', default_text=stop)],
            [sg.Button("Load shifting", size=(24,1), key='-EDIT_LOAD_SHIFT-'), sg.Button("Car charging", size=(24,1), key='-EDIT_CAR_CHARGING-')],
            [sg.Text('===================================================', size=(50,1))],
            [sg.Button('Done editing scenario', key='-UPDATE_SCENARIO-')]
    ]
    layout = [[sg.Column(left_col, element_justification='l')]]    
    window = sg.Window('Scenario editor', layout,resizable=True)
        
    return window

def _editScenario(scenario):
    loadShift = []
    try: loadShift = scenario["LoadShift"]
    except: pass
    carCharge = []
    try: carCharge = scenario["CarCharge"]
    except: pass

    scenarioWindow = _renderOneScenario(scenario)
    while True:
        event, values = scenarioWindow.read()
        if event in (sg.WIN_CLOSED, 'Exit'): break
        try: 
            if event == '-SCENARIO_NAME-': scenario["Name"] = values['-SCENARIO_NAME-'] 
            if event == '-SCENARIO_BATTERY-': scenario["Battery Size"] = float(values['-SCENARIO_BATTERY-']) 
            if event == '-SCENARIO_PANELS-': scenario["Increaed panels"] = int(values['-SCENARIO_PANELS-'])
            if event == '-DISCHARGE_STOP-': scenario["Discharge stop"] = float(values['-DISCHARGE_STOP-'])
            if event == '-EDIT_LOAD_SHIFT-': scenario["LoadShift"] = _editLoadShift(loadShift)
            if event == '-EDIT_CAR_CHARGING-': scenario["CarCharge"] = _editCarCharge(carCharge)
            scenarioWindow['-UPDATE_SCENARIO-'].update(disabled=False)
        except:
            scenarioWindow['-UPDATE_SCENARIO-'].update(disabled=True)
        if event == '-UPDATE_SCENARIO-': 
            scenarioWindow.close()
            break
    return scenario

def _renderScenarioNav(scenarios):
    saveDisabled = False
    left_col = []
    left_col.append([sg.Text('At least one what-if scenario is needed. Click on a scenario to edit. Delete operates on the scenario in the same row', size=(50,2))])
    left_col.append([sg.Text('===================================================', size=(50,1))])
    if len(scenarios) == 0:
        left_col.append([sg.Text('There are no scenarios defined yet.', size=(50,1))])
        saveDisabled = True
    for i, scenario in enumerate(scenarios):
        name = scenario["Name"]
        deleteKey = '-DELETE_SCENARIO_'+ str(i) +'-'
        left_col.append(
            [sg.Button(name, size=(24,1), key='-EDIT_SCENARIO_'+ str(i) +'-'), sg.Button("Delete", size=(24,1), key=deleteKey)]
        )
    left_col.append([])
    left_col.append([sg.Text('===================================================', size=(50,1))])
    left_col.append([sg.Button('Add a new scenario', size=(24,1), key='-ADD_SCENARIO-'), sg.In(size=(24,1), enable_events=True ,key='-NEW_SCENARIO_NAME-', default_text="<New scenario name>")])
    left_col.append([sg.Button('Save scenarios', size=(24,1), key='-SAVE_SCENARIOS-', disabled=saveDisabled)])
    layout = [[sg.Column(left_col, element_justification='l')]]    
    window = sg.Window('Scenario navigation', layout,resizable=True)
    return window

def _getScenarios():
    data = _loadSysConfig()
    try:
        scenarios = data["Scenarios"]
    except:
        scenarios = []
    nav_window = _renderScenarioNav(scenarios)
    while True:
        event, values = nav_window.Read()
        if event in (sg.WIN_CLOSED, 'Exit'): break
        if str(event).startswith('-EDIT_SCENARIO_'):
            scenarioIndex = int(event[-2])
            updatedScenario = _editScenario(scenarios[scenarioIndex])
            scenarios[scenarioIndex] = updatedScenario
            nav_window.close()
            nav_window = _renderScenarioNav(scenarios)
        if str(event).startswith('-DELETE_SCENARIO_'):
            index = int(event[-2])
            del scenarios[index]
            nav_window.close()
            nav_window = _renderScenarioNav(scenarios)
        if event == '-ADD_SCENARIO-': 
            scenarios.append({
                "Name": values['-NEW_SCENARIO_NAME-'], 
                "Battery Size": 5.7,
                "Increaed panels": 14,
                "Discharge stop": 19.6,
                "LoadShift": [],
                "CarCharge": []})
            nav_window.close()
            nav_window = _renderScenarioNav(scenarios)
        if event == '-SAVE_SCENARIOS-': 
            data["Scenarios"] = scenarios
            _updateSysConfig(data)
            _setStatus()
            break

    nav_window.close()
    return

def _fetchAlphaData():
    left_col = [
             [sg.Text('Start date', size=(24,1)), 
              sg.In(size=(25,1), enable_events=True ,key='-START-', default_text="2022-06-01"), 
              sg.CalendarButton('Change date', size=(25,1), target='-START-', pad=None, key='-CAL_START-', format=('%Y-%m-%d'))],
             [sg.Text('Finish date', size=(24,1)), 
              sg.In(size=(25,1), enable_events=True ,key='-FINISH-', default_text="2022-06-01"), 
              sg.CalendarButton('Change date', size=(25,1), target='-FINISH-', pad=None, key='-CAL_END-', format=('%Y-%m-%d'))],
            [sg.Text('AlphaESS username', size=(24,1)), sg.In(size=(25,1), enable_events=True ,key='-ALPHA_USER-', default_text="")],
            [sg.Text('AlphaESS password', size=(24,1)), sg.In(size=(25,1), enable_events=True ,key='-ALPHA_PASS-', default_text="", password_char='*')],
            [sg.Button('Fetch data', key='-FETCH_ALPHA-'), sg.Text("This will fetch data (PV & Load) and populate the DB", size=(50,1), key='-ALPHA_FETCH_STATUS-')]
    ]
    layout = [[sg.Column(left_col, element_justification='l')]]    
    window = sg.Window('Simulation parameters', layout,resizable=True)

    user = ""
    passwd = ""
    begin = ""
    end = ""

    while True:
        event, values = window.Read()
        if event in (sg.WIN_CLOSED, 'Exit'): break
        if event == '-START-': begin = values['-START-']
        if event == '-FINISH-': end = values['-FINISH-']
        if event == '-ALPHA_USER-': user = values['-ALPHA_USER-']
        if event == '-ALPHA_PASS-': passwd = values['-ALPHA_PASS-']
        if event == '-FETCH_ALPHA-': 
            begin = values['-START-']
            end = values['-FINISH-']
            user = values['-ALPHA_USER-']
            passwd = values['-ALPHA_PASS-']
            guiFetch(user, passwd, begin, end, CONFIG)
            guiMakeDB(CONFIG)
            _setStatus()
            break

    window.close()
    return

def _getSliderRows(monthlyDist):
    ret = []
    upperRange = (100 / len(monthlyDist)) * 2
    for k, v in monthlyDist.items():
        ret.append([sg.Text(k, size=(8,1)), sg.Slider(range=(0.0,upperRange), default_value=v, key='-SLIDER_' + k, resolution=.1, size=(60,10), orientation='h', disable_number_display=True)])
    return ret

def _extractFromSliders(values):
    ret = {}
    totalv = 0
    for k, v in values.items():
        totalv += float(v)
    for k, v in values.items():
        if str(k).startswith("-SLIDER_"):
            ret[k[-3:]] = float(v) * 100 / totalv
    return ret

def _renderMonthlyDist(distribution):
    sliderrows = _getSliderRows(distribution)
    left_col = [[sg.Text("Use the sliders to indicate how load is used the relative to the months of the year. For example if you use electric heating the load will likely be higher in the colder months of the year.", size=(80,3))]]
    left_col.extend(sliderrows)
    left_col.extend([[sg.Button('Update distribution', size=(30,1), key='-SAVE_MONTHLY-')]])
    layout = [[sg.Column(left_col, element_justification='l')]]    
    window = sg.Window('Monthly distribution', layout,resizable=True)
    return window

def _getMonthlyDist(profile):
    monthlyDist = {"Jan": 9.37, "Feb": 7.08, "Mar": 8.12, "Apr": 8.14, "May": 9.4, "Jun": 8.98, "Jul": 8.87, "Aug": 9.17, "Sep": 6.45, "Oct": 7.95, "Nov": 7.53, "Dec": 8.96}
    try:
        monthlyDist = profile["MonthlyDistribution"]
    except:
        pass
    window = _renderMonthlyDist(monthlyDist)
    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, 'Exit'): break
        if event == '-SAVE_MONTHLY-':
            monthlyDist = _extractFromSliders(values)
            window.close()
            break
    return monthlyDist

def _renderDOWDist(dowdDist):
    sliderrows = _getSliderRows(dowdDist)
    left_col = [[sg.Text("Use the sliders to indicate how load is used the relative to the days of the year. For example if you use batch cook at the weekend load will be higher on Saturday and Sunday.", size=(80,3))]]
    left_col.extend(sliderrows)
    left_col.extend([[sg.Button('Update distribution', size=(30,1), key='-SAVE_DOWD-')]])
    layout = [[sg.Column(left_col, element_justification='l')]]    
    window = sg.Window('Day of week distribution', layout,resizable=True)
    return window

def _getDOWDist(profile):
    dayOfWeekDist = {"Sun": 14.75, "Mon": 14.13, "Tue": 13.22, "Wed": 13.67, "Thu": 13.68, "Fri": 14.18, "Sat": 16.37
    }
    try:
        dayOfWeekDist = profile["DayOfWeekDistribution"]
    except:
        pass
    window = _renderDOWDist(dayOfWeekDist)
    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, 'Exit'): break
        if event == '-SAVE_DOWD-':
            dayOfWeekDist = _extractFromSliders(values)
            # print(dayOfWeekDist)
            window.close()
            break
    return dayOfWeekDist

def _renderHourlyDist(dowdDist):
    sliderrows = _getSliderRows(dowdDist)
    left_col = [[sg.Text("Use the sliders to indicate how load is used the relative to the hours of the day. For example if you use fiishe work at 5 and cook dinner at 6, the load will be higher than say at 4am.", size=(80,3))]]
    left_col.extend(sliderrows)
    left_col.extend([[sg.Button('Update distribution', size=(30,1), key='-SAVE_HODD-')]])
    layout = [[sg.Column(left_col, element_justification='l')]]    
    window = sg.Window('Day of week distribution', layout,resizable=True)
    return window

def _getHourlyDist(profile):
    hourlyList = [3.52,2.87,2.68,2.53,2.18,2.10,3.95,3.72,3.54,3.35,4.04,5.16,5.57,4.85,4.56,4.10,4.54,7.96,5.86,4.40,4.27,4.43,5.05,4.77]
    hourlyDist = {}
    try:
        hourlyList = profile["HourlyDistribution"]
    except:
        pass
    for i, hour in enumerate(hourlyList):
        hourlyDist[str(i) + '-' + str(i+1)] = hour
    window = _renderHourlyDist(hourlyDist)
    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, 'Exit'): break
        if event == '-SAVE_HODD-':
            hourlyDist = _extractFromSliders(values)
            hourlyList = []
            for k,v in hourlyDist.items():
                hourlyList.append(v)
            # print(hourlyList)
            window.close()
            break
    return hourlyList

def _renderLoadGeneration(profile):
    md = "Not set"
    dd = "Not set"
    hd = "Not set"
    if "MonthlyDistribution" in profile: md = "OK, set"
    if "DayOfWeekDistribution" in profile: dd = "OK, set"
    if "HourlyDistribution" in profile: hd = "OK, set"
    saveDisabled = True
    if "MonthlyDistribution" in profile and "DayOfWeekDistribution" in profile and "HourlyDistribution" in profile:
        saveDisabled = False

    left_col = [
        
        [sg.Text('The load generator creates 5 minute usage data and stores it in the database for the simulator. It generates 12 months of data. It needs a start date.', size=(75,2))],
        [sg.Text('The annual usage is the total KWH that will be used in a year. The hourly base load is what the home consumes when nobody is home (standby devices, fridge, freezer)', size=(85,2))],
        [sg.Text('The three distributions are used to figure out how the annual usage is spread across hours, days and months. These must be set before the profile is complete.)', size=(85,2))],
        [sg.Text('====================================================================================', size=(85,1))],
        [sg.Text('Start date', size=(30,1)), 
             sg.In(size=(25,1), enable_events=True ,key='-CAL-', default_text='2022-01-01'), 
             sg.CalendarButton('Change date', size=(25,1), target='-CAL-', pad=None, 
                                key='-CAL1-', format=('%Y-%m-%d'))],
        [sg.Text('Annual usage (KWH)', size=(30,1)), sg.In(size=(25,1), enable_events=True ,key='-ANNUAL_USE-', default_text=profile["AnnualUsage"])],
        [sg.Text('Hourly base load (KWH)', size=(30,1)), sg.In(size=(25,1), enable_events=True ,key='-BASE_LOAD-', default_text=profile["HourlyBaseLoad"])],
        [sg.Text('Monthly distribution (% by month)', size=(30,1)), sg.Button('Monthly distribution', key='-MONTH_DIST-', size=(21,1)), sg.Text(md, size=(10,1), key='-MONTH_DIST_STAT-')],
        [sg.Text('Day of week distribution (% by day)', size=(30,1)), sg.Button('Daily distribution', key='-DOW_DIST-', size=(21,1)), sg.Text(dd, size=(10,1), key='-DOW_DIST_STAT-')],
        [sg.Text('Hourly distribution (% per hour)', size=(30,1)), sg.Button('Hourly distribution', key='-HOUR_DIST-', size=(21,1)), sg.Text(hd, size=(10,1), key='-HOUR_DIST_STAT-')],
        [sg.Text('====================================================================================', size=(85,1))],
        [sg.Button('Save profile and generate data', size=(30,1), key='-GEN_LOAD-', disabled=saveDisabled), sg.Text("This will generate data (Load only) initialize and populate the DB", size=(50,1), key='-ALPHA_FETCH_STATUS-')]
    ]
    layout = [[sg.Column(left_col, element_justification='l')]]    
    window = sg.Window('Load generation input', layout,resizable=True)
    return window

def _saveProfile(profile):
    # print (profile)
    with open(os.path.join(CONFIG, "loadProfile.json"), 'w') as f:
        json.dump(profile, f)
    return

def _loadProfile():
    profile = {}
    try:
        with open(os.path.join(CONFIG, "loadProfile.json")) as lp:
            profile = json.load(lp)
    except:
        profile = {"AnnualUsage": 8000, "HourlyBaseLoad": 0.3}
    return profile

def _generateLoadProfile():
    md = False
    dwd = False
    hdd = False
    profile = _loadProfile()
    if "MonthlyDistribution" in profile: md = True
    if "DayOfWeekDistribution" in profile: dwd = True
    if "HourlyDistribution" in profile: hdd = True
    window = _renderLoadGeneration(profile)
    start = '2022-01-01'
    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, 'Exit'): break
        try:
            if event == '-ANNUAL_USE-':
                profile["AnnualUsage"] = float(values['-ANNUAL_USE-'])
            if event == '-BASE_LOAD-':
                profile["HourlyBaseLoad"] = float(values['-BASE_LOAD-'])
        except:
            pass
        if event == '-CAL-': start = values['-CAL-']
        if event == '-MONTH_DIST-':
            profile["MonthlyDistribution"] = _getMonthlyDist(profile)
            md = True
            window['-MONTH_DIST_STAT-'].update(value='OK, set')
            if md and dwd and hdd:
                window['-GEN_LOAD-'].update(disabled=False)
        if event == '-DOW_DIST-':
            profile["DayOfWeekDistribution"] = _getDOWDist(profile)
            dwd = True
            window['-DOW_DIST_STAT-'].update(value='OK, set')
            if md and dwd and hdd:
                window['-GEN_LOAD-'].update(disabled=False)
        if event == '-HOUR_DIST-':
            profile["HourlyDistribution"] = _getHourlyDist(profile)
            hdd = True
            window['-HOUR_DIST_STAT-'].update(value='OK, set')
            if md and dwd and hdd:
                window['-GEN_LOAD-'].update(disabled=False)
        if event == '-GEN_LOAD-':
            _saveProfile(profile) 
            # print (start)
            _guiDBFromProfile(CONFIG, start)
            _setStatus()
            window.close()
            break
    return

def _getSolarData():
    left_col = [
        [sg.Text('There is only one option for solar data right now. This will use a default that matches the system configuration. The same 12 months of solar data will be applied to the database for the existing load data dates. If there is more than one year of load data, the solar data will be repeated.', size=(55,4))],
        [sg.Text('Use this if you don\'t have solar data, but want to see the impact it may have. The data is from ireland, facing south east, a good year.', size=(55,2))],
        [sg.Text('======================================================', size=(55,1))],
        [sg.Button('Load default solar data', key='-LOAD_DEFAULT-', size=(25,1)), sg.Text("Overwrites the solar data in the DB", size=(25,1))],
        [sg.Button('Load solar data from PV GIS', key='-LOAD_PVGIS-', size=(25,1)), sg.Text("Needs location and aspect information", size=(25,1))],
        [sg.Button('OK', key='-OK-', size=(25,1))]
    ]
    layout = [[sg.Column(left_col, element_justification='l')]]    
    window = sg.Window('Electricity usage profile', layout,resizable=True)
    window.finalize()

    _setStatus()

    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, 'Exit'): break
        if event == '-LOAD_DEFAULT-': 
            dbFile = os.path.join(STORAGE, DBFILE)
            loadDefaultSolar(CONFIG, dbFile)
            _setStatus()
        if event == '-LOAD_PVGIS-': 
            guiPVgis(CONFIG)
            _setStatus()
        if event == '-OK-': 
            window.close()
            break
    return

def _getLoadProfile():
    left_col = [
        [sg.Text('A load profile describes how electricity is used over the year. There are several ways to get a load profile. Your inverter/solar supplier may provide this information in a way that can be integrated; your electricity provider may provide smart meter data; you can guestimate your own usage. The load profile is used in the simulator to see when to draw on solar or the grid. The load profile should not include load shifting or car charging. These are covered in the what-if scenarios', size=(50,8))],
        [sg.Text('===================================================', size=(50,1))],
        [sg.Button('Load profile from AlphaESS', key='-LOAD_ALPHA-', size=(25,1)), sg.Text("Requires AlphaESS login", size=(24,1))],
        [sg.Button('Generate profile', key='-LOAD_GENERATE-', size=(25,1)), sg.Text("Use this if you have no data", size=(24,1))],
        [sg.Button('Load profile from Electric Ireland', key='-LOAD_EI-', size=(25,1), disabled=True), sg.Text("Requires smart meter data (login)", size=(24,1))],
        [sg.Button('OK', key='-OK-', size=(25,1))]
    ]
    layout = [[sg.Column(left_col, element_justification='l')]]    
    window = sg.Window('Electricity usage profile', layout,resizable=True)
    window.finalize()

    _setStatus()

    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, 'Exit'): break
        if event == '-LOAD_ALPHA-': 
            _fetchAlphaData()
        if event == '-LOAD_GENERATE-': 
            _generateLoadProfile()
        if event == '-OK-': 
            window.close()
            break
    return

def _getProviderRates():
    getRates(CONFIG)
    _setStatus()
    return

def _showReportDB():
    display(CONFIG)
    return

def _callSimulate():
    begin = "2001-01-01"
    try:
        dbFile = os.path.join(STORAGE, DBFILE)
        conn = sqlite3.connect(dbFile)
        cur = conn.cursor()
        cur.execute("SELECT min(Date) FROM dailysums")
        res = cur.fetchone()
        conn.close()
        begin = res[0]
    except:
        pass
    end = 12
    left_col = [
             [sg.Text('Start date', size=(24,1)), 
             sg.In(size=(25,1), enable_events=True ,key='-CAL-', default_text=begin), 
             sg.CalendarButton('Change date', size=(25,1), target='-CAL-', pad=None, 
                                key='-CAL1-', format=('%Y-%m-%d'))],
            [sg.Text('Number of months to simulate', size=(24,1)), sg.In(size=(25,1), enable_events=True ,key='-SIM_MONTHS-', default_text="12")],
            [sg.Button('OK', key='-SIM_OK-')]
    ]
    layout = [[sg.Column(left_col, element_justification='l')]]    
    window = sg.Window('Simulation parameters', layout,resizable=True)

    while True:
        event, values = window.Read()
        if event in (sg.WIN_CLOSED, 'Exit'): break
        if event == '-CAL-': begin = values['-CAL-']
        if event == '-SIM_MONTHS-': end = values['-SIM_MONTHS-']
        if event == '-SIM_OK-': 
            window.close()
            guiMain(CONFIG, begin, end)
            break


def _mainWin():
    global MAIN_WINDOW

    left_col = [
            [sg.Button('Basic Configuration', key='-CONFIG_LAUNCH-', size=(25,1)), sg.Text("Checking", size=(24,1), key='-CONFIG_STAT-')],
            [sg.Button('System Configuration', key='-SYS_CONFIG-', size=(25,1)), sg.Text("Checking...", size=(24,1), key='-SYS_CONFIG_STAT-')],
            [sg.Button('Scenarios', key='-SCENARIOS-', size=(25,1)), sg.Text("Checking...", size=(24,1), key='-SCENARIOS_STAT-')],
            [sg.Button('Usage profile', key='-PROFILE-', size=(25,1)), sg.Text("Checking...", size=(40,1), key='-PROFILE_STAT-')],
            [sg.Button('Solar data', key='-SOLAR_DATA-', size=(25,1), disabled=False), sg.Text("Checking...", size=(40,1), key='-SOLAR_DATA_STAT-')],
            [sg.Button('Provider rates', key='-RATES-', size=(25,1), disabled=False), sg.Text("Checking...", size=(24,1), key='-RATES_STAT-')],
            [sg.Button('Show load graphs', key='-REPORTDB-', size=(25,1), disabled=True), sg.Button('Simulate', key='-SIMULATE-', size=(25,1), disabled=True)],
            [sg.Button('Exit', key='-EXIT-', size=(25,1))]
    ]
    layout = [[sg.Column(left_col, element_justification='l')]]    
    MAIN_WINDOW = sg.Window('Electricity Time of Use Comparison', layout,resizable=True)
    MAIN_WINDOW.finalize()

    _setStatus()

    while True:
        event, values = MAIN_WINDOW.read()
        if event in (sg.WIN_CLOSED, 'Exit'): break
        if event == '-CONFIG_LAUNCH-': _getConfig()
        if event == '-SYS_CONFIG-': _getSysConfig()
        if event == '-SCENARIOS-': _getScenarios()
        if event == '-PROFILE-': _getLoadProfile()
        if event == '-SOLAR_DATA-': _getSolarData()
        if event == '-RATES-': _getProviderRates()
        if event == '-REPORTDB-': _showReportDB()
        if event == '-SIMULATE-': _callSimulate()
        if event == '-EXIT-': break


def main():
    # sg.main_sdk_help()
    _mainWin()

if __name__ == "__main__":
    main()