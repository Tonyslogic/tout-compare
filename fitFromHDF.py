import logging
import json
import os
import sys
import sqlite3
from sqlite3 import Error
import datetime
from dateutil.relativedelta import *

import PySimpleGUI as sg
import pandas as pd 

logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('[%(asctime)s] %(levelname)s [%(filename)s.%(funcName)s:%(lineno)d] %(message)s', datefmt='%a, %d %b %Y %H:%M:%S')
handler.setFormatter(formatter)
logger.addHandler(handler)

def _create_rows(smartMeterData):
    activeImport = []
    activeExport = []
    valueKey = "Read Value"
    typeKey = "Read Type"
    dateKey = "Read Date & Time"

    importType = "Active Import Interval (kW)"
    exportType = "Active Export Interval (kW)"

    DBNormalPV = 0
    delta = datetime.timedelta(minutes=5)
    
    for _, row in smartMeterData.iterrows():
        if row[typeKey] == importType:
            pass
        elif row[typeKey] == exportType:
            dts = row[dateKey]
            dt = datetime.datetime.strptime(dts, '%d-%m-%Y %H:%M')
            theExport = float(row[valueKey])/2 # 30 minute intrvals and kW to kWh
            activeExport.append((dt, theExport))
        
    return activeImport, activeExport

def _getSmartMeterFilename():
    
    smartMeterFile = None
    sDate = '2022-03-08'
    eDate = '2022-12-06'
    rate = '14'

    left_col = [
            [sg.Text('Log into ESBN account (https://www.esbnetworks.ie/existing-connections/meters-and-readings/my-smart-data).  Scroll down to "Download HDF". Click on that link and note where you save the file.', size=(85,3))],
            [sg.Text('Use the file selector to locate the file and click "Load', size=(85,1))],
            [sg.Text('====================================================================================', size=(85,1))],
            [sg.Text("Rate (cents)", size=(9,1)), sg.In(size=(5,1), enable_events=True, key='-RATE-', default_text='21'),
             sg.Text('Start date', size=(7,1)), sg.In(size=(10,1), enable_events=True ,key='-SCAL-', default_text='2022-03-08'), 
                sg.CalendarButton('Change date', size=(12,1), target='-SCAL-', pad=None, key='-SCAL1-', format=('%Y-%m-%d')),
             sg.Text('Start date', size=(7,1)), sg.In(size=(10,1), enable_events=True ,key='-ECAL-', default_text='2022-12-06'), 
                sg.CalendarButton('Change date', size=(12,1), target='-ECAL-', pad=None, key='-ECAL1-', format=('%Y-%m-%d'))
            ],
            [sg.Text('Smart Meter Data file', size=(24,1)), sg.In(size=(25,1), enable_events=True ,key='-C_FOLDER-'), sg.FileBrowse()],
            [sg.Button('Calculate', key='-CONFIG_OK-', disabled=True, size=(15,1)), sg.Button('Close', key='-CLOSE-', size=(15,1)) ]
    ]
    layout = [[sg.Column(left_col, element_justification='l')]]    
    window = sg.Window('ESBN Smart Meter Data import', layout,resizable=True)
    
    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, 'Exit'): break
        if event == '-C_FOLDER-': 
            cfolder = values['-C_FOLDER-']
            if os.path.isfile(cfolder):
                window['-CONFIG_OK-'].update(disabled=False) 
        if event == '-CLOSE-':
            window.close()
            break
        if event == '-CONFIG_OK-':
            if os.path.isfile(cfolder):
                smartMeterFile = values['-C_FOLDER-']
                sDate = values['-SCAL-']
                eDate = values['-ECAL-']
                rate = values['-RATE-']
                window.close()
                break
    return smartMeterFile, sDate, eDate, rate

def main():
    smartMeterFile, begin, finish, cents = _getSmartMeterFilename()
    if smartMeterFile is None: return

    smartMeterData = pd.read_csv(smartMeterFile)
    activeImport, activeExport = _create_rows(smartMeterData)
    df = pd.DataFrame(activeExport, columns =['Date', 'Export'])

    
    seris = df.groupby(df.Date.dt.date)['Export'].sum()
    df2 = pd.DataFrame({'Date':seris.index, 'Export':seris.values})
    
    start = datetime.datetime.strptime(begin, '%Y-%m-%d').date()
    end = datetime.datetime.strptime(finish, '%Y-%m-%d').date()

    totalExport = 0
    for _, row in df2.iterrows():
        if start <= row['Date'] <= end:
            totalExport += row['Export']
    print ("Total kWh exported From", begin, "to", finish, ":", '%.2f' % (totalExport))
    print ("Export value: €", '%.2f' % (totalExport*int(cents)/100))
    
if __name__ == "__main__":
    main()