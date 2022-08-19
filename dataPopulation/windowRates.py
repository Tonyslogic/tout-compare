import datetime
import json
from locale import locale_encoding_alias
import os
import copy
import PySimpleGUI as sg 
from collections import defaultdict

from dataProcessing.simulate import guiMain
from dataPopulation.fetchdata_gui import guiFetch
from dataPopulation.makedb import guiMakeDB
from dataPopulation.makedbFromProfile import _guiDBFromProfile

MAIN_WINDOW = None

CONFIG = "C:\\dev\\solar\\"
STORAGE = "C:\\dev\\solar\\"
DBFILE = "SimData.db"

def _loadRates():
    STATUS_RATES = False
    data = []
    defaultRateDate = "2022-01-01"
    r_file = os.path.join(CONFIG, "rates.json")
    try: 
        defaultRateDate = datetime.datetime.fromtimestamp(os.path.getmtime(r_file)).strftime('%Y-%m-%d')
        with open(os.path.join(CONFIG, "rates.json"), 'r') as f:
           data = json.load(f)
        STATUS_RATES = True
    except:
        STATUS_RATES = False
    return STATUS_RATES, data, defaultRateDate

def _loadImportFile(importFile):
    data = []
    try: 
        with open(os.path.join(CONFIG, importFile), 'r') as f:
            data = json.load(f)
    except: pass
    for rate in data:
        try: d = rate["LastUpdate"]
        except: rate["LastUpdate"] = datetime.datetime.today().strftime('%Y-%m-%d')
    return data

def  _updateRates(rates):
    r_file = os.path.join(CONFIG, "rates.json")
    if not os.path.isfile(r_file): return
    for rate in rates:
        try: d = rate["LastUpdate"]
        except: 
            rate["LastUpdate"] = datetime.datetime.fromtimestamp(os.path.getmtime(r_file)).strftime('%Y-%m-%d')
    with open(r_file, 'w') as f:
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

def _renderOneRatePlan(ratePlan, defaultRatePlan):
    updateDisabled = False
    saveStatus = ""
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
    try: rateDate = ratePlan["LastUpdate"]
    except: rateDate = defaultRatePlan
    try: reference = ratePlan["Reference"]
    except: reference = ""
    left_col = [
            [sg.Text('Provide details of the supplier/plan. The data for this comes from the supplier, or comparison web site. Feel free to use the with or without tax figure, but be consistent', size=(86,2))],
            [sg.Text('======================================================================================', size=(86,1))],
            [sg.Text('Supplier name', size=(25,1)), sg.In(size=(25,1), enable_events=True ,key='-RATE_PLAN_SUPPLIER-', default_text=supplier)],
            [sg.Text('Plan name', size=(25,1)), sg.In(size=(25,1), enable_events=True ,key='-RATE_PLAN_NAME-', default_text=plan)],
            [sg.Text('Feed-in rate (c)', size=(25,1)), sg.In(size=(25,1), enable_events=True ,key='-RATE_PLAN_FEED-', default_text=feed)],
            [sg.Text('Standing charges (€)', size=(25,1)), sg.In(size=(25,1), enable_events=True ,key='-RATE_PLAN_STANDING-', default_text=standing)],
            [sg.Text('Sign up bonus (€)', size=(25,1)), sg.In(size=(25,1), enable_events=True ,key='-RATE_PLAN_BONUS-', default_text=bonus)],
            [sg.Text('Last update', size=(25,1)), sg.In(size=(25,1), enable_events=True ,key='-RATE_PLAN_DATE-', default_text=rateDate)],
            [sg.Text('Reference', size=(25,1)), sg.In(size=(25,1), enable_events=True ,key='-RATE_PLAN_REF-', default_text=reference)],
            [sg.Text('======================================================================================', size=(86,1))],
            [sg.Text('The plan must include at least one day profile. Day profiles are separated by \'====\'. Additional day profiles are needed for weekend rates. Between all day profiles, each day must be covered. The hourly ranges in each day profile must cover the full 24 hours. The end of one range must be the start of the next. Hours are integer values.', size=(86,3))],
            [sg.Text('You can add a range to a day profile by populating the fields (making sure the \'From\' is the same as the previous \'To\') below the \'-----\' and pressing \'Add\'. Note that the costs of adjacent ranges must be different, or they will be merged. Similarly make sure the times and costs line up before deleting a range.', size=(86,3))],
            [sg.Text('======================================================================================', size=(86,1))]
    ]
    if len(rateEntries) == 0: 
        updateDisabled = True
        saveStatus = "No profiles defined"
        left_col.append([sg.Text('No day profiles yet. Please add by pressing \'Add another day profile\'', size=(86,1))])
        left_col.append([sg.Text('======================================================================================', size=(86,1))])
    else:
        # Check for missing days
        updateDisabled, saveStatus = _checkForMissingDays(rateEntries)

    for i, rateEntry in enumerate(rateEntries):
        left_col.append([
            sg.Text('Applicable days:', size=(15,1)),
            sg.Checkbox('Sun', size=(5,1), default=0 in rateEntry["Days"], key='-RATE_DAY_0' + str(i), enable_events=True),
            sg.Checkbox('Mon', size=(5,1), default=1 in rateEntry["Days"], key='-RATE_DAY_1' + str(i), enable_events=True),
            sg.Checkbox('Tue', size=(5,1), default=2 in rateEntry["Days"], key='-RATE_DAY_2' + str(i), enable_events=True),
            sg.Checkbox('Wed', size=(5,1), default=3 in rateEntry["Days"], key='-RATE_DAY_3' + str(i), enable_events=True),
            sg.Checkbox('Thu', size=(5,1), default=4 in rateEntry["Days"], key='-RATE_DAY_4' + str(i), enable_events=True),
            sg.Checkbox('Fri', size=(5,1), default=5 in rateEntry["Days"], key='-RATE_DAY_5' + str(i), enable_events=True),
            sg.Checkbox('Sat', size=(5,1), default=6 in rateEntry["Days"], key='-RATE_DAY_6' + str(i), enable_events=True)
        ])

        rateRange = _getRateRange(rateEntry["Hours"])
        #TEST
        # _getHourlyRates(rateRange)
        #TEST

        for r, rate in enumerate(rateRange):
            left_col.append([
                sg.Text('From (hr)', size=(15,1)), sg.In(size=(8,1), enable_events=True ,key='-RATE_BEGIN' + str(i) + str(r), default_text=rate["begin"]),
                sg.Text('To (hr)', size=(15,1)), sg.In(size=(8,1), enable_events=True ,key='-RATE_END' + str(i) + str(r), default_text=rate["end"]),
                sg.Text('Rate (cents)', size=(15,1)), sg.In(size=(8,1), enable_events=True ,key='-RATE_PRICE' + str(i) + str(r), default_text=rate["price"]),
                sg.Button('Del', size=(6,1), key='-DEL_DAY_RATE-' + str(i) + str(r))
                ])
        left_col.append([sg.Text('--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------', size=(86,1))])
        left_col.append([
                sg.Text('From (hr)', size=(15,1)), sg.In(size=(8,1), enable_events=True ,key='-NEW_RATE_BEGIN' + str(i), default_text=0),
                sg.Text('To (hr)', size=(15,1)), sg.In(size=(8,1), enable_events=True ,key='-NEW_RATE_END' + str(i), default_text=24),
                sg.Text('Rate (cents)', size=(15,1)), sg.In(size=(8,1), enable_events=True ,key='-NEW_RATE_PRICE' + str(i), default_text=0),
                sg.Button('Add', size=(6,1), key='-ADD_HR_RANGE-' + str(i))
                ])
        left_col.append([sg.Button('Delete this day profile', key='-DEL_DAY_PROFILE' + str(i), size=(30,1), disabled=False)])
        left_col.append([sg.Text('======================================================================================', size=(86,1))])
    
    left_col.append([sg.Button('Add another day profile', key='-ADD_DAY_RATE-', size=(30,1))])
    left_col.append([sg.Button('Update and close', key='-UPDATE_RATE_PLAN-', size=(30,1), disabled=updateDisabled), sg.Text(saveStatus, key='-UPDATE_RATE_PLAN_STATUS-', size=(30,1))])
    layout = [[sg.Column(left_col, element_justification='l', size=(700, 700), expand_y=True, scrollable=True,  vertical_scroll_only=True)]]    
    window = sg.Window('Rate plan editor', layout,resizable=True)
        
    return window

def _checkForMissingDays(rateEntries):
    updateDisabled = False
    saveStatus = ""
    days = [0,1,2,3,4,5,6]
    missingdays = [0,1,2,3,4,5,6]
    for day in days:
        for rateEntry in rateEntries:
            if day in rateEntry["Days"]:
                try:
                    missingdays.remove(day)
                except:
                    pass
    if len(missingdays) > 0:
        updateDisabled = True
        saveStatus = "Not all days covered"
    return updateDisabled,saveStatus

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

def _editRatePlan(ratePlan, defaulteRateDate):
    oldRatePlan = copy.deepcopy(ratePlan)
    ratePlanWindow = _renderOneRatePlan(ratePlan, defaulteRateDate)
    while True:
        event, values = ratePlanWindow.read()
        if event in (sg.WIN_CLOSED, 'Exit'): 
            ratePlan = oldRatePlan
            break
        try: 
            ratePlanWindow['-UPDATE_RATE_PLAN-'].update(disabled=False)
            if str(event).startswith('-RATE_DAY_'): 
                _getSimpleProps(ratePlan, values)
                # and the day types, including the hourly rates
                latestRanges = _scrapeLatestRateRange(values)
                latestDayTypes = _scrapeLatestDayTypes(values)
                rates = []
                for index in range(0, len(latestRanges)):
                    r = _getHourlyRates(latestRanges[str(index)])
                    dt = latestDayTypes[str(index)]
                    rates.append({"Days": dt, "Hours": r})
                ratePlan["Rates"] = rates
                updateDisabled, saveStatus = _checkForMissingDays(ratePlan["Rates"])
                ratePlanWindow['-UPDATE_RATE_PLAN-'].update(disabled=updateDisabled)
                ratePlanWindow['-UPDATE_RATE_PLAN_STATUS-'].update(value=saveStatus)
                
            if str(event).startswith('-DEL_DAY_RATE'):
                dtindex = int(event[-2])
                rowindex = int(event[-1])
                latestRanges = _scrapeLatestRateRange(values)
                latestDayTypes = _scrapeLatestDayTypes(values)
                del latestRanges[str(dtindex)][rowindex]
                new = _getHourlyRates(latestRanges[str(dtindex)])
                ratePlan["Rates"][dtindex]["Hours"] = new
                ratePlan["Rates"][dtindex]["Days"] = latestDayTypes[str(dtindex)]
                _getSimpleProps(ratePlan, values)
                ratePlanWindow.close()
                ratePlanWindow = _renderOneRatePlan(ratePlan, defaulteRateDate)
            if str(event).startswith('-ADD_HR_RANGE-'): 
                index = int(event[-1])
                latestRanges = _scrapeLatestRateRange(values)
                latestDayTypes = _scrapeLatestDayTypes(values)
                addition = _scrapeNewRange(index, values)
                latestRanges[str(index)].append(addition)
                new = _getHourlyRates(latestRanges[str(index)])
                ratePlan["Rates"][index]["Hours"] = new
                ratePlan["Rates"][index]["Days"] = latestDayTypes[str(index)]
                _getSimpleProps(ratePlan, values)
                ratePlanWindow.close()
                ratePlanWindow = _renderOneRatePlan(ratePlan, defaulteRateDate)
            if str(event).startswith('-DEL_DAY_PROFILE'):
                index = int(event[-1])
                del ratePlan["Rates"][index]
                ratePlanWindow.close()
                ratePlanWindow = _renderOneRatePlan(ratePlan, defaulteRateDate)
            if str(event).startswith('-ADD_DAY_RATE-'):
                if "Rates" not in ratePlan.keys(): ratePlan["Rates"] = [] 
                _getSimpleProps(ratePlan, values)
                # and the day types, including the hourly rates
                latestRanges = _scrapeLatestRateRange(values)
                latestDayTypes = _scrapeLatestDayTypes(values)
                rates = []
                for index in range(0, len(latestRanges)):
                    r = _getHourlyRates(latestRanges[str(index)])
                    dt = latestDayTypes[str(index)]
                    rates.append({"Days": dt, "Hours": r})
                ratePlan["Rates"] = rates
                ratePlan["Rates"].append({"Days": [0,1,2,3,4,5,6], "Hours": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]})
                _getSimpleProps(ratePlan, values)
                ratePlanWindow.close()
                ratePlanWindow = _renderOneRatePlan(ratePlan, defaulteRateDate)
        except:
            ratePlanWindow['-UPDATE_RATE_PLAN-'].update(disabled=True)
        if event == '-UPDATE_RATE_PLAN-': 
            _getSimpleProps(ratePlan, values)
            # and the day types, including the hourly rates
            latestRanges = _scrapeLatestRateRange(values)
            latestDayTypes = _scrapeLatestDayTypes(values)
            rates = []
            for index in range(0, len(latestRanges)):
                r = _getHourlyRates(latestRanges[str(index)])
                dt = latestDayTypes[str(index)]
                rates.append({"Days": dt, "Hours": r})
            ratePlan["Rates"] = rates

            ratePlanWindow.close()
            # print (ratePlan)
            break
    return ratePlan

def _getSimpleProps(ratePlan, values):
    # Simple props
    supplier = values["-RATE_PLAN_SUPPLIER-"]
    plan = values["-RATE_PLAN_NAME-"]
    feed = float(values["-RATE_PLAN_FEED-"])
    standing = float(values["-RATE_PLAN_STANDING-"])
    bonus = float(values["-RATE_PLAN_BONUS-"])
    rateDate = values["-RATE_PLAN_DATE-"]
    reference = values["-RATE_PLAN_REF-"]
    ratePlan["Supplier"] = supplier
    ratePlan["Plan"] = plan
    ratePlan["Feed"] = feed
    ratePlan["Standing charges"] = standing
    ratePlan["Bonus cash"] = bonus
    ratePlan["LastUpdate"] = rateDate
    ratePlan["Reference"]  = reference

def _renderRatePlanNav(ratePlans):
    saveDisabled = False
    left_col = []
    left_col.append([sg.Text('At least one supplier and plan is needed. The rates are used by the simulator to calculate the costs of the various what-if scenarios.', size=(80,2))])
    left_col.append([sg.Text('To add a supplier/plan, provide a name and click \'Create new plan\'. To delete a supplier/plan use the delete button on the same row. To edit a suplier/plan click the button named for the plan.', size=(80,2))])
    left_col.append([sg.Text('==============================================================================', size=(80,1))])
    if len(ratePlans) == 0 : 
        left_col.append([sg.Text('No supplier/plans defined, Create before saving.', size=(80,1))])
        saveDisabled = True
    for i, ratePlan in enumerate(ratePlans):
        supplier = ratePlan["Supplier"]
        plan = ratePlan["Plan"]
        deleteKey = '-DELETE_RATE_PLAN_'+ str(i) +'-'
        left_col.append(
            [sg.Text(supplier, size=(25,1)), sg.Button(plan, size=(24,1), key='-EDIT_RATE_PLAN_'+ str(i) +'-'), sg.Button("Delete", size=(24,1), key=deleteKey)]
        )
    left_col.append([])
    left_col.append([sg.Text('==============================================================================', size=(80,1))])
    left_col.append([sg.Text("New supplier", size=(25,1)), sg.Button('Create new plan', size=(24,1), key='-ADD_RATE_PLAN-'), sg.In(size=(28,1), enable_events=True ,key='-NEW_RATE_PLAN_NAME-', default_text="<New plan name>")])
    left_col.append([sg.Text("Import rate file", size=(25,1)), sg.In(size=(28,1), enable_events=True ,key='-R_FILE-', default_text=CONFIG), sg.FileBrowse(), sg.Button('Import', size=(16,1), key='-IMPORT_RATES-')])
    left_col.append([sg.Text('==============================================================================', size=(80,1))])
    left_col.append([sg.Button('Save', size=(24,1), key='-SAVE_RATE_PLAN-', disabled=saveDisabled)])
    # layout = [[sg.Column(left_col, element_justification='l')]]    
    layout = [[sg.Column(left_col, element_justification='l', size=(650, 500), expand_y=True, scrollable=True,  vertical_scroll_only=True)]]  
    window = sg.Window('Rates navigation', layout,resizable=True)
    return window

def getRates(config):
    global CONFIG
    CONFIG = config
    status, rates, defaultRateDate = _loadRates()
    nav_window = _renderRatePlanNav(rates)
    while True:
        event, values = nav_window.Read()
        if event in (sg.WIN_CLOSED, 'Exit'): break
        if str(event).startswith('-EDIT_RATE_PLAN_'):
            ratePlanIndex = int(event[-2])
            updatedRatePlan = _editRatePlan(rates[ratePlanIndex], defaultRateDate)
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
                "Rates": [],
                "Active": True,
                "LastUpdate": datetime.datetime.today().strftime('%Y-%m-%d')
                })
            nav_window.close()
            nav_window = _renderRatePlanNav(rates)
        if event == '-IMPORT_RATES-': 
            importFile = values['-R_FILE-']
            rates.extend(_loadImportFile(importFile))
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