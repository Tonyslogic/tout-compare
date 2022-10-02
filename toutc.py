from ast import keyword
import copy
import datetime
import itertools
import json
from locale import locale_encoding_alias
import sqlite3
import PySimpleGUI as sg 
import os

from numpy import disp
from dataPopulation.makedbFromSLP import guiDBFromSLP

from dataProcessing.simulate import guiMain
from dataProcessing.reportdb import display

from dataPopulation.fetchdata_gui import guiFetch
from dataPopulation.makedb import guiMakeDB
from dataPopulation.makedbFromProfile import _guiDBFromProfile
from dataPopulation.windowGenerateProfile import genProfile, _saveProfile
from dataPopulation.windowRates import getRates, _updateRates
from dataPopulation.makedbFromEISmartDataFile import guiDBFromEISmartMeter
from dataPopulation.loadDefaultSolar import loadDefaultSolar
from dataPopulation.pvgis2db import guiPVgis
from dataPopulation.demodefaults import DEMO_START, DEMO_ANNUAL, DEMO_BASE, DEMO_MONTHLYDIST, DEMO_DOWDIST, DEMO_HOURLYDIST, DEMO_RATES, DEMO_SYSTEM
from dataPopulation.windowScenarios import getScenarios

VERSION = "v0.0.25"

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
    _updateRates(CONFIG, DEMO_RATES)
    # loadProfile.json
    profile = {}
    profile["AnnualUsage"] = DEMO_ANNUAL
    profile["HourlyBaseLoad"] = DEMO_BASE
    profile["MonthlyDistribution"] = DEMO_MONTHLYDIST
    profile["DayOfWeekDistribution"] = DEMO_DOWDIST
    profile["HourlyDistribution"] = DEMO_HOURLYDIST
    _saveProfile(CONFIG, profile)
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
            sfolder = cfolder
            window['-S_FOLDER-'].update(value=cfolder)
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
    defaultRateDate = "2022-01-01"
    r_file = os.path.join(CONFIG, "rates.json")
    try: 
        defaultRateDate = datetime.datetime.fromtimestamp(os.path.getmtime(r_file)).strftime('%Y-%m-%d')
        with open(r_file, 'r') as f:
           data = json.load(f)
        MAIN_WINDOW['-RATES_STAT-'].update(value="Found " + str(len(data)) + " pricing plans")
        STATUS_RATES = True
    except:
        MAIN_WINDOW['-RATES_STAT-'].update(value="No vendor rates defined")
        STATUS_RATES = False
    return data, defaultRateDate

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

def _getScenarios():
    getScenarios(CONFIG)
    _setStatus()

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

def _generateLoadProfile():
    genProfile(CONFIG)
    _setStatus()
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
        [sg.Button('Generate profile', key='-LOAD_GENERATE-', size=(25,1)), sg.Text("Estimate your own profile", size=(24,1))],
        [sg.Button('Load profile from Electric Ireland', key='-LOAD_EI-', size=(25,1), disabled=False), sg.Text("Requires smart meter data", size=(24,1))],
        [sg.Button('Standard Load profile', key='-LOAD_SLP-', size=(25,1), disabled=False), sg.Text("Average usage from ESBN", size=(24,1))],
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
        if event == '-LOAD_EI-': 
            guiDBFromEISmartMeter(CONFIG)
        if event == '-LOAD_SLP-': 
            guiDBFromSLP(CONFIG)
        if event == '-OK-': 
            window.close()
            break
    _setStatus()
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
                sg.CalendarButton('Change date', size=(25,1), target='-CAL-', pad=None, key='-CAL1-', format=('%Y-%m-%d'))],
            [sg.Text('Number of months to simulate', size=(24,1)), 
                sg.In(size=(25,1), enable_events=True ,key='-SIM_MONTHS-', default_text="12"),
                sg.Checkbox("Save sim data", size=(15,1), default=True, disabled=False, enable_events=True, key='-SAVE_SIM_OUTPUT-'),
                sg.Checkbox("Use deemed export", size=(15,1), default=False, disabled=False, enable_events=True, key='-DEEMED_EXPORT-')],
            [sg.Text('=================================================================================================================', size=(100,1))],
            [sg.Text('Tariff rates to compare:', size=(50,1)), sg.Text('Scenarios to simulate:', size=(50,1))]
    ]
    rates, defaultRateDate = _loadRates()
    sysProps = _loadSysConfig()
    scenarios = sysProps["Scenarios"]
    for index, combination in enumerate(itertools.zip_longest(rates, scenarios, fillvalue=None)):
        rate = "--"
        rateActive = False
        rateKey = "-NA-"
        rateDisabled = True
        if combination[0] is not None:
            rate = combination[0]["Supplier"] + "," + combination[0]["Plan"]
            try: rateActive = combination[0]["Active"]
            except: rateActive = True
            try: rateDate = combination[0]["LastUpdate"]
            except: rateDate = defaultRateDate
            rate = rate + " [" + rateDate + "]"
            rateKey = '-RATE-'+ str(index)
            rateDisabled = False
        scenario = "--"
        scenarioActive = False
        scenarioKey = "-NA-"
        scenarioDisabled = True
        if combination[1] is not None:
            scenario = combination[1]["Name"]
            try: scenarioActive = combination[1]["Active"]
            except: scenarioActive = True
            scenarioKey = '-SCENARIO-'+ str(index)
            scenarioDisabled = False
        left_col.append([
            sg.Checkbox(rate, size=(47,1), default=rateActive, disabled=rateDisabled, enable_events=True, key=rateKey),
            sg.Checkbox(scenario, size=(47,1), default=scenarioActive, disabled=scenarioDisabled, enable_events=True, key=scenarioKey)
            ])
    left_col.append([sg.Text('===============================================================================================================', size=(100,1))])
    left_col.append([sg.Button('Simulate & Compare', key='-SIM_OK-')])
    # layout = [[sg.Column(left_col, element_justification='l')]]  
    layout = [[sg.Column(left_col, element_justification='l', size=(800, 500), expand_x=True, expand_y=True, scrollable=True,  vertical_scroll_only=True)]]  
    window = sg.Window('Simulation and comparison parameters', layout,resizable=True)

    while True:
        event, values = window.Read()
        if event in (sg.WIN_CLOSED, 'Exit'): break
        if event == '-CAL-': begin = values['-CAL-']
        if event == '-SIM_MONTHS-': end = values['-SIM_MONTHS-']
        if event == '-SIM_OK-': 
            # print(values)
            save = False
            deemed = False
            for key, value in values.items():
                if str(key).startswith('-RATE-'):
                    rateIndex = int(key[-1])
                    rates[rateIndex]["Active"] = value
                if str(key).startswith('-SCENARIO-'):
                    scenarioIndex = int(key[-1])
                    scenarios[scenarioIndex]["Active"] = value
                if str(key) == '-SAVE_SIM_OUTPUT-':
                    save = value
                if str(key) == '-DEEMED_EXPORT-':
                    deemed = value
            sysProps["Scenarios"] = scenarios
            _updateSysConfig(sysProps)
            _updateRates(CONFIG, rates)
            window.close()
            guiMain(CONFIG, begin, end, save, deemed)
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
            [sg.Button('Data visualization', key='-REPORTDB-', size=(25,1), disabled=True), sg.Button('Compare', key='-SIMULATE-', size=(25,1), disabled=True)],
            [sg.Button('Exit', key='-EXIT-', size=(25,1))]
    ]
    layout = [[sg.Column(left_col, element_justification='l')]]    
    MAIN_WINDOW = sg.Window('Electricity Time of Use Comparison (' + VERSION + ')', layout,resizable=True)
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