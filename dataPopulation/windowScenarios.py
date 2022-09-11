import hashlib
import json
from locale import locale_encoding_alias
import os
import copy
import sqlite3
from sqlite3 import Error
import PySimpleGUI as sg 
from collections import defaultdict

CONFIG = "C:\\dev\\solar\\"
STORAGE = "C:\\dev\\solar\\"
DBFILE = "SimData.db"

def _loadSysConfig():
    STATUS_SYS_CONFIG = False
    data = {}
    try: 
        with open(os.path.join(CONFIG, "SystemProperties.json"), 'r') as f:
            data = json.load(f)
        STATUS_SYS_CONFIG = True
    except:
        STATUS_SYS_CONFIG = False
        data = {"Battery Size": 5.7, "Original panels": 14, "Discharge stop": 19.6, "Min excess": 0.008, "Max discharge": 0.225, "Max charge": 0.225, "Max Inverter load": 5.0, "Massage FeedIn": 87.5, "Massage Buy": 94.5, "(Dis)charge loss": 4, "ChargeModel": {"0": 30, "12": 100, "90": 10, "100": 0}}
    return STATUS_SYS_CONFIG, data

def _updateSysConfig(data):
    with open(os.path.join(CONFIG, "SystemProperties.json"), 'w') as f:
        json.dump(data, f)
    return

def _renderLoadShift(loadShift, batterySize):
    left_col = []
    left_col.append([sg.Text('Load shifting is charging a battery when electricity prices are lower and using the battery when prices are higher. Load shifting is most useful when solar generation is low. Load shifting can be configured several times. Each configuration (time and charge) is applied in the months slected.', size=(150,2))])
    left_col.append([sg.Text('======================================================================================================================================================', size=(150,1))])
    for i, shift in enumerate(loadShift):
        try: absoluteStop = f'{float(shift["stop at"]) * batterySize / 100:.2f}'
        except: absoluteStop = '0.00'
        left_col.append([
            sg.Text('Begin charging at (hr)', size=(25,1)), sg.In(size=(25,1), enable_events=True ,key='-LS_BEGIN' + str(i), default_text=shift["begin"]),
            sg.Text('End charging at (hr)', size=(25,1)), sg.In(size=(25,1), enable_events=True ,key='-LS_END' + str(i), default_text=shift["end"]),
            sg.Text('Stop when battery at (%)', size=(25,1)), sg.In(size=(14,1), enable_events=True ,key='-LS_STOP' + str(i), default_text=shift["stop at"]),
            sg.Text(absoluteStop + '(kWh)', size=(12,1), key='-LS_KWH' + str(i))
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
            sg.Button('Del', size=(6,1), key='-DEL_LS_CFG-' + str(i))
        ])
        left_col.append([sg.Text('======================================================================================================================================================', size=(150,1))])
    left_col.append([sg.Button('Add a load shift configuration', key='-ADD_LS-')]),
    left_col.append([sg.Button('Done editing load shift', key='-UPDATE_LS-')])
    layout = [[sg.Column(left_col, element_justification='l')]]    
    window = sg.Window('Load shift editor', layout,resizable=True)
        
    return window

def _editLoadShift(loadShift, batterySize):
    oldLoadShift = copy.deepcopy(loadShift)
    lsWindow = _renderLoadShift(loadShift, batterySize)
    while True:
        event, values = lsWindow.read()
        # print(event)
        if event in (sg.WIN_CLOSED, 'Exit'): 
            loadShift = oldLoadShift
            break
        if str(event).startswith('-LS_STOP'):
            index = int(event[-1])
            stop = values['-LS_STOP' + str(index)]
            try: absoluteStop = f'{float(stop) * batterySize / 100:.2f}' + '(kWh)'
            except: absoluteStop = '0.00 (kWh)'
            lsWindow['-LS_KWH' + str(index)].update(value=absoluteStop)
        if str(event).startswith('-DEL_LS_CFG'):
            index = int(event[-1])
            del loadShift[index]
            lsWindow.close()
            lsWindow = _renderLoadShift(loadShift, batterySize)
        if event == '-ADD_LS-': 
            loadShift.append({"stop at": 80, "begin": 2, "end": 4, "months": [1,2,3,4,5,6,7,8,9,10,11,12]})
            lsWindow.close()
            lsWindow = _renderLoadShift(loadShift, batterySize)
        if event == '-UPDATE_LS-':
            newLoadShift = []
            for i, _ in enumerate(loadShift):
                shift = {}
                months = [] #[1,2,3,4,5,6,7,8,9,10,11,12]
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
            sg.Button('Del', size=(6,1), key='-DEL_CC_CFG-' + str(i))
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
    oldCarCharge = copy.deepcopy(carCharge)
    ccWindow = _renderCarCharge(carCharge)
    
    while True:
        event, values = ccWindow.read()
        # print(event)
        if event in (sg.WIN_CLOSED, 'Exit'): 
            carCharge = oldCarCharge
            break
        if str(event).startswith('-DEL_CC_CFG'):
            index = int(event[-1])
            del carCharge[index]
            ccWindow.close()
            ccWindow = _renderCarCharge(carCharge)
        if event == '-ADD_CC-': 
            carCharge.append({"draw": 7.5, "begin": 2, "end": 4, "months": [1,2,3,4,5,6,7,8,9,10,11,12], "days": [0,1,2,3,4,5,6]})
            ccWindow.close()
            ccWindow = _renderCarCharge(carCharge)
        if event == '-UPDATE_CC-':
            newCarCharge = []
            for i, _ in enumerate(carCharge):
                charge = {}
                months = [] #[1,2,3,4,5,6,7,8,9,10,11,12]
                days = [] #[0,1,2,3,4,5,6]
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

def _renderDivert(divert):
    left_col = []
    hwd = {"active": False, "tank": 60, "target": 75, "usage": 500, "intake": 10}
    try: hwd = divert["HWD"]
    except: pass
    left_col.append([sg.Text('Diversion monitors the feed in to the grid. When feed in is detected, the available capacity is \'diverted\' to either a car or hot water heater. This avoids a poor Feed in Tariff, and helps to maximize self consumption.', size=(150,2))])
    left_col.append([sg.Text('======================================================================================================================================================', size=(150,1))])
    left_col.append([sg.Text('Hot water diversion assumes: that the daily usage is distributed 70% @ 08:00, 10% @ 14:00 and 20% @ 20:00; Tank heat loss is 1/3°C per hour.', size=(150,1))])
    left_col.append([sg.Checkbox('Enable Hot Water Diverter', size=(50,1), default=hwd["active"], key='-HWD-')])
    left_col.append([sg.Text('Tank size (liter)', size=(25,1)), sg.In(size=(25,1), enable_events=True ,key='-TANK_SIZE-', default_text=hwd["tank"]),
                    sg.Text('Target temp (°C)', size=(25,1)), sg.In(size=(25,1), enable_events=True ,key='-TARGET_TEMP-', default_text=hwd["target"])])
    left_col.append([sg.Text('Daily usage (liter)', size=(25,1)), sg.In(size=(25,1), enable_events=True ,key='-USAGE-', default_text=hwd["usage"]),
                    sg.Text('Intake temp (°C)', size=(25,1)), sg.In(size=(25,1), enable_events=True ,key='-INTAKE_TEMP-', default_text=hwd["intake"])])
    left_col.append([sg.Text('======================================================================================================================================================', size=(150,1))])
    evd = {"active": False, "ev1st": True, "begin": 11, "end": 16, "dailymax": 7.5, "months": [], "days": []}
    try: evd = divert["EVD"]
    except: pass
    left_col.append([sg.Checkbox('Enable Electric Vehicle Diverter', size=(50,1), default=evd["active"], key='-EVD-'),
                    sg.Checkbox('Charge the EV before heating water', size=(50,1), default=evd["ev1st"], disabled=not evd["active"], key='-EV1ST-')])
    left_col.append([
            sg.Text('Begin charging at (hr)', size=(25,1)), sg.In(size=(25,1), enable_events=True ,key='-EV_DIV_BEGIN-', default_text=evd["begin"]),
            sg.Text('End charging at (hr)', size=(25,1)), sg.In(size=(25,1), enable_events=True ,key='-EV_DIV_END-', default_text=evd["end"]),
            sg.Text('Max daily charge (KWhr)', size=(25,1)), sg.In(size=(25,1), enable_events=True ,key='-EV_DIV_MAX-', default_text=evd["end"])
            ])

    left_col.append([
        sg.Text('Applicable months:', size=(25,1)),
        sg.Checkbox('Jan', size=(5,1), default=1 in evd["months"], key='-DIV_MONTH_1'),
        sg.Checkbox('Feb', size=(5,1), default=2 in evd["months"], key='-DIV_MONTH_2'),
        sg.Checkbox('Mar', size=(5,1), default=3 in evd["months"], key='-DIV_MONTH_3'),
        sg.Checkbox('Apr', size=(5,1), default=4 in evd["months"], key='-DIV_MONTH_4'),
        sg.Checkbox('May', size=(5,1), default=5 in evd["months"], key='-DIV_MONTH_5'),
        sg.Checkbox('Jun', size=(5,1), default=6 in evd["months"], key='-DIV_MONTH_6'),
        sg.Checkbox('Jul', size=(5,1), default=7 in evd["months"], key='-DIV_MONTH_7'),
        sg.Checkbox('Aug', size=(5,1), default=8 in evd["months"], key='-DIV_MONTH_8'),
        sg.Checkbox('Sep', size=(5,1), default=9 in evd["months"], key='-DIV_MONTH_9'),
        sg.Checkbox('Oct', size=(5,1), default=10 in evd["months"], key='-DIV_MONTH_A'),
        sg.Checkbox('Nov', size=(5,1), default=11 in evd["months"], key='-DIV_MONTH_B'),
        sg.Checkbox('Dec', size=(5,1), default=12 in evd["months"], key='-DIV_MONTH_C')
    ])
    left_col.append([
        sg.Text('Applicable days:', size=(25,1)),
        sg.Checkbox('Sun', size=(5,1), default=0 in evd["days"], key='-DIV_DAY_0'),
        sg.Checkbox('Mon', size=(5,1), default=1 in evd["days"], key='-DIV_DAY_1'),
        sg.Checkbox('Tue', size=(5,1), default=2 in evd["days"], key='-DIV_DAY_2'),
        sg.Checkbox('Wed', size=(5,1), default=3 in evd["days"], key='-DIV_DAY_3'),
        sg.Checkbox('Thu', size=(5,1), default=4 in evd["days"], key='-DIV_DAY_4'),
        sg.Checkbox('Fri', size=(5,1), default=5 in evd["days"], key='-DIV_DAY_5'),
        sg.Checkbox('Sat', size=(5,1), default=6 in evd["days"], key='-DIV_DAY_6')
    ])
    #     left_col.append([sg.Text('======================================================================================================================================================', size=(150,1))])
    left_col.append([sg.Button('Done editing the diverter configuration', key='-UPDATE_DIVERTER-')])
    layout = [[sg.Column(left_col, element_justification='l')]]    
    window = sg.Window('Diverter configuration editor', layout,resizable=True)
        
    return window

def _editDivert(divert):
    oldDivert = copy.deepcopy(divert)
    divertWindow = _renderDivert(divert)
    
    while True:
        event, values = divertWindow.read()
        # print(event)
        if event in (sg.WIN_CLOSED, 'Exit'): 
            divert = oldDivert
            break
        if event == '-UPDATE_DIVERTER-':
            divert = {"HWD": {}, "EVD": {}}
            try:
                divert["HWD"]["active"] = values["-HWD-"]
                divert["HWD"]["tank"] = int(values["-TANK_SIZE-"])
                divert["HWD"]["target"] = int(values["-TARGET_TEMP-"])
                divert["HWD"]["intake"] = int(values["-INTAKE_TEMP-"])
                divert["HWD"]["usage"] = int(values["-USAGE-"])
                
                divert["EVD"]["active"] = values["-EVD-"]
                divert["EVD"]["ev1st"] = values["-EV1ST-"]
                divert["EVD"]["begin"] = int(values["-EV_DIV_BEGIN-"])
                divert["EVD"]["end"] = int(values["-EV_DIV_END-"])
                divert["EVD"]["dailymax"] = float(values["-EV_DIV_MAX-"])

                divert["EVD"]["months"] = []
                divert["EVD"]["days"] = []

                for key, value in values.items():
                    if str(key).startswith('-DIV_MONTH'):
                        if value:
                            divert["EVD"]["months"].append(int(key[-1],16))
                    if str(key).startswith('-DIV_DAY'):
                        if value:
                            divert["EVD"]["days"].append(int(key[-1]))

                # print (divert)
                divertWindow.close()
            except:
                print ("Bad stuff in parsing diverter")
                pass
            break
    return divert

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
            [sg.Button("Load shifting", size=(15,1), key='-EDIT_LOAD_SHIFT-'), sg.Button("Car charging", size=(15,1), key='-EDIT_CAR_CHARGING-'), sg.Button("Diverters", size=(15,1), key='-EDIT_DIVERT-')],
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
    divert = {}
    try: divert = scenario["Divert"]
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
            if event == '-EDIT_LOAD_SHIFT-': 
                loadShift = _editLoadShift(loadShift, float(values['-SCENARIO_BATTERY-']))
                scenario["LoadShift"] = loadShift
            if event == '-EDIT_CAR_CHARGING-': 
                carCharge = _editCarCharge(carCharge)
                scenario["CarCharge"] = carCharge
            if event == '-EDIT_DIVERT-': 
                divert = _editDivert(divert)
                scenario["Divert"] = divert
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
        left_col.append(
            [sg.Text(name, size=(24,1)), 
            sg.Button("Edit", size=(5,1), key='-EDIT_SCENARIO_'+ str(i) +'-'), 
            sg.Button("Copy", size=(5,1), key='-COPY_SCENARIO_'+ str(i) +'-'),
            sg.Button("Delete", size=(7,1), key='-DELETE_SCENARIO_'+ str(i) +'-')
            ])
    left_col.append([])
    left_col.append([sg.Text('===================================================', size=(50,1))])
    left_col.append([sg.Button('Add a new scenario', size=(24,1), key='-ADD_SCENARIO-'), sg.In(size=(24,1), enable_events=True ,key='-NEW_SCENARIO_NAME-', default_text="<New scenario name>")])
    left_col.append([sg.Button('Save scenarios', size=(24,1), key='-SAVE_SCENARIOS-', disabled=saveDisabled), sg.Button('Clear DB cache', size=(24,1), key='-CLEAN_DB-')])
    layout = [[sg.Column(left_col, element_justification='l')]]    
    window = sg.Window('Scenario navigation', layout,resizable=True)
    return window

def _getActiveMD5(scenario):
    # only active scenarios are persisted
    active = True
    try: active = scenario["Active"]
    except: pass
    scenario["Active"] = True
    ret = hashlib.md5(json.dumps(scenario, sort_keys=True).encode('utf-8')).hexdigest()
    scenario["Active"] = active
    return ret

def _cleanDB():
    with open(os.path.join(CONFIG, "EnvProperties.json"), 'r') as f:
        env = json.load(f)
    dbFile = os.path.join(env["StorageFolder"], env["DBFileName"])
    d1 = "DROP TABLE scenarios"
    d2 = "DROP TABLE scenariodata"
    d3 = "DROP TABLE scenarioTotals"
    conn = None
    try:
        conn = sqlite3.connect(dbFile)
        c = conn.cursor()
        c.execute(d1)
        c.execute(d2)
        c.execute(d3)
        conn.commit()
        conn.close()
    except Error as e:
        print(e)
    return

def _deleteScenarioFromDB(md5):
    with open(os.path.join(CONFIG, "EnvProperties.json"), 'r') as f:
        env = json.load(f)
    dbFile = os.path.join(env["StorageFolder"], env["DBFileName"])

    d1 = "DELETE FROM scenariodata WHERE scenarioID = (SELECT id FROM scenarios WHERE md5 = '" + md5 + "');"
    d2 = "DELETE FROM scenarioTotals WHERE scenarioID = (SELECT id FROM scenarios WHERE md5 = '" + md5 + "');"
    d3 = "DELETE FROM scenarios WHERE md5 = '" + md5 + "';"

    conn = None
    try:
        conn = sqlite3.connect(dbFile)
        c = conn.cursor()
        c.execute(d1)
        c.execute(d2)
        c.execute(d3)
        conn.commit()
        conn.close()
    except Error as e:
        print(e)
    return

def _getOldmd5s(scenarios):
    old_md5s = {}
    
    for idx, scenario in enumerate(scenarios): 
        old_md5s[idx] = _getActiveMD5(scenario)

    return old_md5s

def getScenarios(config):
    global CONFIG
    CONFIG = config
    status, data = _loadSysConfig()
    try:
        scenarios = data["Scenarios"]
    except:
        scenarios = []
    scenarios =  sorted(scenarios, key=lambda d: d['Name'])
    old_md5s = _getOldmd5s(scenarios)
    nav_window = _renderScenarioNav(scenarios)
    while True:
        event, values = nav_window.Read()
        if event in (sg.WIN_CLOSED, 'Exit'): break
        if str(event).startswith('-EDIT_SCENARIO_'):
            scenarioIndex = int(event[-2])
            updatedScenario = _editScenario(scenarios[scenarioIndex])
            if _getActiveMD5(updatedScenario) not in old_md5s.values():
                _deleteScenarioFromDB(old_md5s[scenarioIndex])
            scenarios[scenarioIndex] = updatedScenario
            old_md5s = _getOldmd5s(scenarios)
            nav_window.close()
            nav_window = _renderScenarioNav(scenarios)
        if str(event).startswith('-DELETE_SCENARIO_'):
            index = int(event[-2])
            del scenarios[index]
            _deleteScenarioFromDB(old_md5s[index])
            scenarios =  sorted(scenarios, key=lambda d: d['Name'])
            old_md5s = _getOldmd5s(scenarios)
            nav_window.close()
            nav_window = _renderScenarioNav(scenarios)
        if str(event).startswith('-COPY_SCENARIO_'):
            scenarioIndex = int(event[-2])
            thecopy = copy.deepcopy(scenarios[scenarioIndex])
            thecopy["Name"] += "(copy)"
            scenarios.append(thecopy)
            scenarios =  sorted(scenarios, key=lambda d: d['Name'])
            old_md5s = _getOldmd5s(scenarios)
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
            scenarios =  sorted(scenarios, key=lambda d: d['Name'])
            old_md5s = _getOldmd5s(scenarios)
            nav_window.close()
            nav_window = _renderScenarioNav(scenarios)
        if event == '-CLEAN_DB-': 
            _cleanDB()
        if event == '-SAVE_SCENARIOS-': 
            data["Scenarios"] = scenarios
            _updateSysConfig(data)
            break

    nav_window.close()
    return

def main():
    getScenarios(CONFIG)

if __name__ == "__main__":
    main()