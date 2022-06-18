import json
from locale import locale_encoding_alias
import sqlite3
import PySimpleGUI as sg 
from collections import defaultdict

from simulate import guiMain
from fetchdata_gui import guiFetch
from makedb import guiMakeDB
from makedbFromProfile import _guiDBFromProfile

MAIN_WINDOW = None

CONFIG = "C:\\dev\\solar\\"
STORAGE = "C:\\dev\\solar\\"
DBFILE = "SimData.db"

def _loadRates():
    STATUS_RATES = False
    data = []
    try: 
        with open(CONFIG + "rates.json", 'r') as f:
           data = json.load(f)
        STATUS_RATES = True
    except:
        STATUS_RATES = False
    return STATUS_RATES, data

def  _updateRates(rates):
    with open(CONFIG + "rates.json", 'w') as f:
        json.dump(rates, f)
    return

def _getRateRange(hourlyRates):
    rateRange = []
    previousRate = hourlyRates[0]
    begin = 0
    end = 0
    for hour, rate in enumerate(hourlyRates):
        if rate == previousRate:
            end = hour + 1
        else:
            rateRange.append({"begin": begin, "end": end, "price": previousRate})
            previousRate = rate
            begin = hour
            end = hour + 1
    rateRange.append({"begin": begin, "end": end - 1, "price": previousRate})
    # print (rateRange)
    return rateRange

def _getHourlyRates(rateRange):
    hourlyRates = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    for hr in range(0,25):
        for rng in rateRange:
            if hr >= rng["begin"] and hr <= rng["end"]: hourlyRates[hr] = rng["price"]
    # print (hourlyRates)
    return hourlyRates

def _renderOneRatePlan(ratePlan):
    plan = ratePlan["Plan"]
    try:
        feed = ratePlan["Feed"]
        standing = ratePlan["Standing charges"]
        bonus = ratePlan["Bonus cash"]
        supplier = ratePlan["Supplier"]
        rateEntries = ratePlan["Rates"]
    except:
        feed = 0
        standing = 0
        bonus = 0
        supplier = "Unknown"
        rateEntries = []
    left_col = [
            [sg.Text('Supplier name', size=(25,1)), sg.In(size=(25,1), enable_events=True ,key='-RATE_PLAN_SUPPLIER-', default_text=supplier)],
            [sg.Text('Plan name', size=(25,1)), sg.In(size=(25,1), enable_events=True ,key='-RATE_PLAN_NAME-', default_text=plan)],
            [sg.Text('Feed-in rate (c)', size=(25,1)), sg.In(size=(25,1), enable_events=True ,key='-RATE_PLAN_FEED-', default_text=feed)],
            [sg.Text('Standing charges (€)', size=(25,1)), sg.In(size=(25,1), enable_events=True ,key='-RATE_PLAN_STANDING-', default_text=standing)],
            [sg.Text('Sign up bonus (€)', size=(25,1)), sg.In(size=(25,1), enable_events=True ,key='-RATE_PLAN_BONUS-', default_text=bonus)],
            [sg.Text('======================================================================================', size=(86,1))]
    ]
    for i, rateEntry in enumerate(rateEntries):
        left_col.append([
            sg.Text('Applicable days:', size=(15,1)),
            sg.Checkbox('Sun', size=(5,1), default=0 in rateEntry["Days"], key='-RATE_DAY_0' + str(i)),
            sg.Checkbox('Mon', size=(5,1), default=1 in rateEntry["Days"], key='-RATE_DAY_1' + str(i)),
            sg.Checkbox('Tue', size=(5,1), default=2 in rateEntry["Days"], key='-RATE_DAY_2' + str(i)),
            sg.Checkbox('Wed', size=(5,1), default=3 in rateEntry["Days"], key='-RATE_DAY_3' + str(i)),
            sg.Checkbox('Thu', size=(5,1), default=4 in rateEntry["Days"], key='-RATE_DAY_4' + str(i)),
            sg.Checkbox('Fri', size=(5,1), default=5 in rateEntry["Days"], key='-RATE_DAY_5' + str(i)),
            sg.Checkbox('Sat', size=(5,1), default=6 in rateEntry["Days"], key='-RATE_DAY_6' + str(i))
        ])

        rateRange = _getRateRange(rateEntry["Hours"])
        #TEST
        _getHourlyRates(rateRange)
        #TEST

        for r, rate in enumerate(rateRange):
            left_col.append([
                sg.Button('Del', size=(6,1), key='-DEL_DAY_RATE-' + str(i) + str(r)),
                sg.Text('From (hr)', size=(15,1)), sg.In(size=(8,1), enable_events=True ,key='-RATE_BEGIN' + str(i) + str(r), default_text=rate["begin"]),
                sg.Text('To (hr)', size=(15,1)), sg.In(size=(8,1), enable_events=True ,key='-RATE_END' + str(i) + str(r), default_text=rate["end"]),
                sg.Text('Rate (cents)', size=(15,1)), sg.In(size=(8,1), enable_events=True ,key='-RATE_PRICE' + str(i) + str(r), default_text=rate["price"])
                ])
        left_col.append([
                sg.Button('Add', size=(6,1), key='-ADD_HR_RANGE-' + str(i)),
                sg.Text('From (hr)', size=(15,1)), sg.In(size=(8,1), enable_events=True ,key='-NEW_RATE_BEGIN' + str(i), default_text=0),
                sg.Text('To (hr)', size=(15,1)), sg.In(size=(8,1), enable_events=True ,key='-NEW_RATE_END' + str(i), default_text=24),
                sg.Text('Rate (cents)', size=(15,1)), sg.In(size=(8,1), enable_events=True ,key='-NEW_RATE_PRICE' + str(i), default_text=0)
                ])
        left_col.append([sg.Text('======================================================================================', size=(86,1))])
    
    left_col.append([sg.Button('Add another day profile', key='-ADD_DAY_RATE-'), sg.Button('Update and close', key='-UPDATE_RATE_PLAN-')])
    layout = [[sg.Column(left_col, element_justification='l')]]    
    window = sg.Window('Rate plan editor', layout,resizable=True)
        
    return window

def _scrapeLatestDayTypes(values):
    # {"0": [0,1,2,3,4,5,6]}
    dts = defaultdict(list)
    for key, value in values.items():
        if str(key).startswith('-RATE_DAY_'):
            if value:
                index = key[-1]
                day = key[-2]
                dts[index].append(int(day))
    # print(dts)
    return dts 

def _scrapeLatestRateRange(values):
    rr = defaultdict(list)
    begins = {}
    ends = {}
    prices = {}
    for value in values:
        if str(value).startswith('-RATE_BEGIN'):
            index = value[-2:]
            begins[index] = int(values[value])
        if str(value).startswith('-RATE_END'):
            index = value[-2:]
            ends[index] = int(values[value])
        if str(value).startswith('-RATE_PRICE'):
            index = value[-2:]
            prices[index] = float(values[value])
    # print(begins, ends, prices)
    for begin in begins:
        dtIndex = begin[0]
        rr[dtIndex].append({"begin": begins[begin], "end": ends[begin], "price": prices[begin]})
    # print(rr)
    return rr

def _scrapeNewRange(index, values):
    rng = {}
    begin = 0
    end = 0
    price = 0
    for value in values:
        if str(value).startswith('-NEW_RATE_BEGIN'):
            if index == int(value[-1:]):
                begin = int(values[value])
        if str(value).startswith('-NEW_RATE_END'):
            if index == int(value[-1:]):
                end = int(values[value])
        if str(value).startswith('-NEW_RATE_PRICE'):
            if index == int(value[-1:]):
                price = float(values[value])
    rng = {"begin": begin, "end": end, "price": price}
    return rng

def _editRatePlan(ratePlan):
    ratePlanWindow = _renderOneRatePlan(ratePlan)
    while True:
        event, values = ratePlanWindow.read()
        if event in (sg.WIN_CLOSED, 'Exit'): break
        try: 
            ratePlanWindow['-UPDATE_RATE_PLAN-'].update(disabled=False)
            if str(event).startswith('-DEL_DAY_RATE'):
                dtindex = int(event[-2])
                rowindex = int(event[-1])
                latestRanges = _scrapeLatestRateRange(values)
                del latestRanges[str(dtindex)][rowindex]
                new = _getHourlyRates(latestRanges[str(dtindex)])
                ratePlan["Rates"][dtindex]["Hours"] = new
                ratePlanWindow.close()
                ratePlanWindow = _renderOneRatePlan(ratePlan)
            if str(event).startswith('-ADD_HR_RANGE-'): 
                index = int(event[-1])
                latestRanges = _scrapeLatestRateRange(values)
                addition = _scrapeNewRange(index, values)
                latestRanges[str(index)].append(addition)
                new = _getHourlyRates(latestRanges[str(index)])
                ratePlan["Rates"][index]["Hours"] = new
                ratePlanWindow.close()
                ratePlanWindow = _renderOneRatePlan(ratePlan)
            if str(event).startswith('-ADD_DAY_RATE-'):
                if "Rates" not in ratePlan.keys(): ratePlan["Rates"] = []
                ratePlan["Rates"].append({"Days": [], "Hours": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]})
                ratePlanWindow.close()
                ratePlanWindow = _renderOneRatePlan(ratePlan)
        except:
            ratePlanWindow['-UPDATE_RATE_PLAN-'].update(disabled=True)
        if event == '-UPDATE_RATE_PLAN-': 
            # Simple props
            supplier = values["-RATE_PLAN_SUPPLIER-"]
            plan = values["-RATE_PLAN_NAME-"]
            feed = float(values["-RATE_PLAN_FEED-"])
            standing = float(values["-RATE_PLAN_STANDING-"])
            bonus = float(values["-RATE_PLAN_BONUS-"])
            # and the day types, including the hourly rates
            latestRanges = _scrapeLatestRateRange(values)
            latestDayTypes = _scrapeLatestDayTypes(values)
            rates = []
            for index in range(0, len(latestRanges)):
                r = _getHourlyRates(latestRanges[str(index)])
                dt = latestDayTypes[str(index)]
                rates.append({"Days": dt, "Hours": r})
            
            ratePlan["Supplier"] = supplier
            ratePlan["Plan"] = plan
            ratePlan["Rates"] = rates
            ratePlan["Feed"] = feed
            ratePlan["Standing charges"] = standing
            ratePlan["Bonus cash"] = bonus

            ratePlanWindow.close()
            # print (ratePlan)
            break
    return ratePlan

def _renderRatePlanNav(ratePlans):
    left_col = []
    for i, ratePlan in enumerate(ratePlans):
        supplier = ratePlan["Supplier"]
        plan = ratePlan["Plan"]
        deleteKey = '-DELETE_RATE_PLAN_'+ str(i) +'-'
        left_col.append(
            [sg.Text(supplier, size=(25,1)), sg.Button(plan, size=(24,1), key='-EDIT_RATE_PLAN_'+ str(i) +'-'), sg.Button("Delete", size=(24,1), key=deleteKey)]
        )
    left_col.append([])
    left_col.append([sg.Text("New supplier", size=(25,1)), sg.Button('Add', size=(24,1), key='-ADD_RATE_PLAN-'), sg.In(size=(24,1), enable_events=True ,key='-NEW_RATE_PLAN_NAME-', default_text="New scenario")])
    left_col.append([sg.Button('Save', size=(24,1), key='-SAVE_RATE_PLAN-')])
    layout = [[sg.Column(left_col, element_justification='l')]]    
    window = sg.Window('Rates navigation', layout,resizable=True)
    return window

def getRates(config):
    global CONFIG
    CONFIG = config
    status, rates = _loadRates()
    nav_window = _renderRatePlanNav(rates)
    while True:
        event, values = nav_window.Read()
        if event in (sg.WIN_CLOSED, 'Exit'): break
        if str(event).startswith('-EDIT_RATE_PLAN_'):
            ratePlanIndex = int(event[-2])
            updatedRatePlan = _editRatePlan(rates[ratePlanIndex])
            rates[ratePlanIndex] = updatedRatePlan
            nav_window.close()
            nav_window = _renderRatePlanNav(rates)
        if str(event).startswith('-DELETE_RATE_PLAN_'):
            index = int(event[-2])
            del rates[index]
            nav_window.close()
            nav_window = _renderRatePlanNav(rates)
        if event == '-ADD_RATE_PLAN-': 
            rates.append({
                "Supplier": "New supplier", 
                "Plan": values['-NEW_RATE_PLAN_NAME-'],
                "Feed": 0,
                "Standing charges": 0,
                "Bonus cash": 0,
                "Supplier": "Unknown",
                "Rates": []
                })
            nav_window.close()
            nav_window = _renderRatePlanNav(rates)
        if event == '-SAVE_RATE_PLAN-': 
            _updateRates(rates)
            # print(rates)
            break

    nav_window.close()
    return status

def main():
    status = getRates(CONFIG)

if __name__ == "__main__":
    main()