import json
from locale import locale_encoding_alias
import os
import copy
import PySimpleGUI as sg 
from collections import defaultdict

CONFIG = "C:\\dev\\solar\\"
STORAGE = "C:\\dev\\solar\\"
DBFILE = "SimData.db"

def _loadSysConfig():
    data = {}
    try: 
        with open(os.path.join(CONFIG, "SystemProperties.json"), 'r') as f:
            data = json.load(f)
        if "HWUse" not in data:
            data.update({"HWCapacity": 165, "HWUsage": 200, "HWIntake": 15, "HWTarget": 75, "HWLoss": 8, "HWRate": 2.5, "HWUse": [(7,75),(14,10),(20,15)]})
    except:
        data = {"Battery Size": 5.7, "Original panels": 14, "Discharge stop": 19.6, "Min excess": 0.008, "Max discharge": 0.225, "Max charge": 0.225, "Max Inverter load": 5.0, "Massage FeedIn": 87.5, "Massage Buy": 94.5, "(Dis)charge loss": 4, "ChargeModel": {"0": 30, "12": 100, "90": 10, "100": 0}, "HWCapacity": 165, "HWUsage": 200, "HWIntake": 15, "HWTarget": 75, "HWLoss": 8, "HWRate": 2.5, "HWUse": [(7,75),(14,10),(20,15)]}
    return data

def _saveSysConfig(data):
    with open(os.path.join(CONFIG, "SystemProperties.json"), 'w') as f:
        json.dump(data, f)
    return

def _getWaterConfig():
    data = _loadSysConfig()
    
    left_col = [
            [sg.Text('Hot water tank configuration, size & behaviour (shared).', size=(45,1))],
            [sg.Text('Tank capacity (Liter).', size=(35,1)), sg.In(size=(10,1), enable_events=True ,key='-HW_TANK-', default_text=data["HWCapacity"])],
            [sg.Text('Water intake temperature (C)', size=(35,1)), sg.In(size=(10,1), enable_events=True ,key='-HW_INTAKE-', default_text=data["HWIntake"])],
            [sg.Text('Water target temperature (C)', size=(35,1)), sg.In(size=(10,1), enable_events=True ,key='-HW_TARGET-', default_text=data["HWTarget"])],
            [sg.Text('Hot water daily loss (%)', size=(35,1)), sg.In(size=(10,1), enable_events=True ,key='-HW_LOSS-', default_text=data["HWLoss"])],
            [sg.Text('Hot water immersion (kWh)', size=(35,1)), sg.In(size=(10,1), enable_events=True ,key='-HW_RATE-', default_text=data["HWRate"])],
            [sg.Text('Hot water daily usage (Liter)', size=(35,1)), sg.In(size=(10,1), enable_events=True ,key='-HW_USAGE-', default_text=data["HWUsage"])],
            
            [sg.Text('HW usage #1 (Hour , %)', size=(35,1)), 
                    sg.In(size=(4,1), enable_events=True ,key='-HW_USE1-', default_text=data["HWUse"][0][0]), 
                    sg.In(size=(4,1), enable_events=True ,key='-HW_USE1%-', default_text=data["HWUse"][0][1])],
            [sg.Text('HW usage #2 (Hour , %)', size=(35,1)), 
                    sg.In(size=(4,1), enable_events=True ,key='-HW_USE2-', default_text=data["HWUse"][1][0]), 
                    sg.In(size=(4,1), enable_events=True ,key='-HW_USE2%-', default_text=data["HWUse"][1][1])],
            [sg.Text('HW usage #3 (Hour , %)', size=(35,1)), 
                    sg.In(size=(4,1), enable_events=True ,key='-HW_USE3-', default_text=data["HWUse"][2][0]), 
                    sg.In(size=(4,1), enable_events=True ,key='-HW_USE3%-', default_text=data["HWUse"][2][1])],
            
            [sg.Button('Save', key='-UPDATE_SYS_CFG-')]
    ]
    layout = [[sg.Column(left_col, element_justification='l', size=(400, 300), expand_x=True, expand_y=True, scrollable=True,  vertical_scroll_only=True)]]    
    window = sg.Window('Hot water configuration', layout,resizable=True)
        
    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, 'Exit'): break
        try:
            if event == '-HW_TANK-': data["HWCapacity"] = float(values['-HW_TANK-'])  
            if event == '-HW_USAGE-': data["HWUsage"] = float(values['-HW_USAGE-'])  
            if event == '-HW_INTAKE-': data["HWIntake"] = float(values['-HW_INTAKE-'])  
            if event == '-HW_TARGET-': data["HWTarget"] = float(values['-HW_TARGET-'])  
            if event == '-HW_LOSS-': data["HWLoss"] = float(values['-HW_LOSS-'])   
            if event == '-HW_RATE-': data["HWRate"] = float(values['-HW_RATE-'])  
            if event == '-HW_USE1-': data["HWUse"][0] = (float(values['-HW_USE1-']), float(values['-HW_USE1%-'])  )
            if event == '-HW_USE1%-': data["HWUse"][0] = (float(values['-HW_USE1-']), float(values['-HW_USE1%-'])  )
            if event == '-HW_USE2-': data["HWUse"][1] = (float(values['-HW_USE2-']), float(values['-HW_USE2%-'])  )
            if event == '-HW_USE2%-': data["HWUse"][1] = (float(values['-HW_USE2-']), float(values['-HW_USE2%-'])  )
            if event == '-HW_USE3-': data["HWUse"][2] = (float(values['-HW_USE3-']), float(values['-HW_USE3%-'])  )
            if event == '-HW_USE3%-': data["HWUse"][2] = (float(values['-HW_USE3-']), float(values['-HW_USE3%-']) )

            window['-UPDATE_SYS_CFG-'].update(disabled=False)
        except Exception as e:
            print (e)
            window['-UPDATE_SYS_CFG-'].update(disabled=True)

        if event == '-UPDATE_SYS_CFG-':
            _saveSysConfig(data)
            window.close()
            break

    return

def setWaterConfig(config):
    global CONFIG
    CONFIG = config  
    _getWaterConfig()

def main():
    setWaterConfig(CONFIG)

if __name__ == "__main__":
    main()