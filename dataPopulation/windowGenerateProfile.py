import json
from locale import locale_encoding_alias
import os
import copy
import PySimpleGUI as sg 
from collections import defaultdict

from dataPopulation.makedbFromProfile import _guiDBFromProfile

CONFIG = "C:\\dev\\solar\\"
STORAGE = "C:\\dev\\solar\\"
DBFILE = "SimData.db"

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

def _saveProfile(CONFIG, profile):
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

def genProfile(config):
    global CONFIG
    CONFIG = config    
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
            _saveProfile(CONFIG, profile) 
            # print (start)
            _guiDBFromProfile(CONFIG, start)
            # _setStatus()
            window.close()
            break

def main():
    genProfile(CONFIG)

if __name__ == "__main__":
    main()