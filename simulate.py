import csv
import logging
import json
import os
import sys
import sqlite3
from sqlite3 import Error
import pandas as pd
import matplotlib.pyplot as plt
import collections
import datetime
from dateutil.relativedelta import *

import PySimpleGUI as sg

TABLE = None
WINDOW = None

STATE_OF_CHARGE_KWH = 0
INPUT_SOC = 19.6
BATTERY_MINIMUM_KWH = 0
CHARGE_MODEL = dict()
IGNORE_LEVEL = 0
BATTERY_SIZE_KWH = 0
MAX_DISCHARGE_KWH = 0
CHARGING_LOSS_FACTOR = 0
FEED_MODIFIER = 1
BUY_MODIFIER = 1
LOAD_SHIFT = dict()
CAR_CHARGE = dict()
PV_GEN_MODIFIER = 1
ORIGINAL_PANEL_COUNT = 14
MAX_INVERTER_LOAD = 0.41666666
DIVERT = dict()

CONFIG = "C:\\dev\\solar\\"

logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('[%(asctime)s] %(levelname)s [%(filename)s.%(funcName)s:%(lineno)d] %(message)s', datefmt='%a, %d %b %Y %H:%M:%S')
handler.setFormatter(formatter)
logger.addHandler(handler)

def _processOneRow(soc, load, pv, cfg):
    newSOC = soc
    feed = 0
    buy = 0

    pv = pv * PV_GEN_MODIFIER

    batAvailable = min(MAX_DISCHARGE_KWH, max(0, (soc - BATTERY_MINIMUM_KWH)))
    batChargeAvailable = min(BATTERY_SIZE_KWH - soc, _getMaxChargeForSOC(soc))

    if not cfg: available = pv + batAvailable
    else: available = pv

    if load > available:
        buy = load - available
        if not cfg: newSOC = soc - batAvailable * CHARGING_LOSS_FACTOR  
    else: # we cover the load without the grid
        if load > pv:
            if not cfg: 
                newSOC = soc - (load - pv) * CHARGING_LOSS_FACTOR
            else: 
                buy = load - pv
        else: # there is extra pv to charge/feed
            if ((pv - load) > IGNORE_LEVEL):
                if not cfg: 
                    charge = min((pv - load), batChargeAvailable)
                    newSOC = soc + charge
                    feed = pv - load - charge
                    if MAX_INVERTER_LOAD < feed + charge:
                        feed = MAX_INVERTER_LOAD - charge
                else:
                    # soc was already calculated
                    # but the feed does not consider this
                    feed = min(pv - load, MAX_INVERTER_LOAD)
                feed = feed * FEED_MODIFIER

    return newSOC, feed, buy

def _getCFG(date, minuteOfDay, soc):
    cfg = False
    extraLoad = 0
    newSOC = soc
    month = int(date.split('-')[1])
    try:
        lsd = LOAD_SHIFT[month]
    except KeyError:
        return cfg, extraLoad, newSOC    
    if lsd[0] < minuteOfDay < lsd[1]:
        cfg = True
        freeCap = BATTERY_SIZE_KWH - soc
        extraLoad = min(freeCap, _getMaxChargeForSOC(soc))
        newSOC = soc + extraLoad

    return cfg, extraLoad, newSOC

def _getCarLoad(date, dow, mod):
    carLoad = 0
    month = int(date.split('-')[1])
    
    try:
        ccm = CAR_CHARGE[month]
        ccd = ccm[dow]
        if ccd[0] < mod < ccd[1]:
            carLoad = ccd[2]
    except KeyError:
        pass 
    return carLoad

def _divert(availablefeed, date, minuteOfDay, dayOfWeek, dailyDiversionTotals):
    diversion = 0
    hw_d = 0
    ev_d = 0
    if date not in dailyDiversionTotals:
        previouaDate = datetime.datetime.strftime((datetime.datetime.strptime(date, '%Y-%m-%d') - datetime.timedelta(days=1)), '%Y-%m-%d')
        previousDateTemp = 15
        try: 
            # print (date, dailyDiversionTotals[previouaDate])    
            previousDateTemp = DIVERT["HWD"]["intake"]
            previousDateTemp = dailyDiversionTotals[previouaDate]["HWTemp"]
        except: pass
        dailyDiversionTotals[date] = {"HW": 0, "EV": 0, "HWTemp": previousDateTemp}

    inputTemp = dailyDiversionTotals[date]["HWTemp"]

    # Failfast
    if not DIVERT["HWD"]["active"] and not DIVERT["EVD"]["active"]: return hw_d, ev_d, dailyDiversionTotals
    
    if DIVERT["HWD"]["active"]:
        tank = DIVERT["HWD"]["tank"]
        # calculate the water draw
        # Reduce the temp by 1/3 degree each hour
        usage = DIVERT["HWD"]["usage"]
        if minuteOfDay % 60 == 0 :
            inputTemp = max (DIVERT["HWD"]["intake"], inputTemp - 0.333333333333333)
            # Reduce the temp to cater for usage: 70%@08:00 10%@14:00 20%@20:00
            hour = minuteOfDay // 60
            match hour:
                case 8: usage = usage * 0.7
                case 14: usage = usage * 0.1
                case 20: usage = usage * 0.2
                case _: usage = 0
        inputTemp = ((tank - usage) * inputTemp + usage * DIVERT["HWD"]["intake"]) / tank
        inputTemp = max (DIVERT["HWD"]["intake"], inputTemp)

        # The most that could be drawn (kWH) to get to the target temp
        hw_d = (tank * 1000) * 4.2 * (DIVERT["HWD"]["target"] - inputTemp)
    
    if DIVERT["EVD"]["active"]:
        divertToEVSoFarToday = dailyDiversionTotals[date]["EV"]
        dailyMax = DIVERT["EVD"]["dailymax"]
        availableEVC = max(0, (dailyMax - divertToEVSoFarToday))
        if availableEVC > 0:
            month = int(date.split('-')[1])
            if month in DIVERT["EVD"]["months"] and dayOfWeek in DIVERT["EVD"]["days"] :
                ev_d = availableEVC
    
    if DIVERT["EVD"]["ev1st"]:
        ev_d = min(availablefeed, ev_d)
        hw_d = min(availablefeed - ev_d, hw_d) 
    else:
        hw_d = min(availablefeed, hw_d)
        ev_d = min(availablefeed - hw_d, ev_d) 

    hw_d = max (0, hw_d)
    ev_d = max (0, ev_d)

    dailyDiversionTotals[date]["HW"] += hw_d
    if DIVERT["HWD"]["active"]: dailyDiversionTotals[date]["HWTemp"] = ((hw_d * 3600000) / (tank * 4200)) + inputTemp
    
    dailyDiversionTotals[date]["EV"] += ev_d
    # diversion = hw_d + ev_d

    return hw_d, ev_d, dailyDiversionTotals 

def _simulate(df, start, finish):
    res = []
    daysInSim = finish - start
    totals = {"totalFeed": 0, "totalBuy": 0, "totalEV": 0, "totalHWDiv": 0, "totalHWDNeed": 0, "totalEVDiv": 0}
    dailyDiversionTotals = {}
    newSOC = STATE_OF_CHARGE_KWH
    
    for r in list(zip(df['NormalLoad'], df['NormalPV'], df['Date'], df['MinuteOfDay'], df['DayOfWeek'])):
        if start <= datetime.datetime.strptime(r[2], '%Y-%m-%d') <= finish:
            cfg, cfgload, newSOC = _getCFG(r[2], r[3], newSOC) # Ignores using solar first if there is spare capacity, so processOneRow does this
            # TODO: Add the car load here
            carload = _getCarLoad(r[2], r[4], r[3])
            # newSOC, feed, buy = _processOneRow(soc, load, pv, cfg):
            newSOC, feed, buy = _processOneRow(newSOC, r[0] + cfgload + carload, r[1], cfg)
            # see if there any diversions in place, and reduce feed. Track dailymax EV and daily usage for water
            hw_d, ev_d, dailyDiversionTotals = _divert(feed, r[2], r[3], r[4], dailyDiversionTotals)
            feed = feed - (hw_d + ev_d)
            hwt = dailyDiversionTotals[r[2]]["HWTemp"]
            res.append((r[2], r[3], r[4], feed, buy, newSOC, carload, hwt, hw_d, ev_d)) # Date, MOD, DOW, feed, buy, soc, DirectEVcharge, waterTemp, kWHDivToWater, kWHDivToEV
            totals["totalFeed"] += feed
            totals["totalBuy"] += buy
            totals["totalEV"] += carload
            totals["totalHWDiv"] += hw_d
            totals["totalEVDiv"] += ev_d
            if DIVERT["HWD"]["active"]  and r[3] == 0:
                totals["totalHWDNeed"] += DIVERT["HWD"]["KWH"]
 
    print ("\tBuy: " + str(int(totals["totalBuy"])) + " KWh" + "; Sell: " + str(int(totals["totalFeed"])) + " KWh")
    return res, totals

def _loadDataFrameFromDB(dbFile):
    conn = None
    df = None
    try:
        conn = sqlite3.connect(dbFile)
        df = pd.read_sql_query("""SELECT Date, MinuteOfDay, NormalLoad, NormalPV, DayOfWeek 
                                FROM dailystats 
                                ORDER BY Date, MinuteOfDay""", conn)
        conn.close()
    except Error as e:
        print(e)
    return df

def _loadProperties(configLocation):
    global STATE_OF_CHARGE_KWH
    global BATTERY_MINIMUM_KWH
    global CHARGE_MODEL
    global IGNORE_LEVEL
    global BATTERY_SIZE_KWH
    global maxChargeKWH
    global MAX_DISCHARGE_KWH
    global CHARGING_LOSS_FACTOR
    global FEED_MODIFIER
    global BUY_MODIFIER
    # global LOAD_SHIFT
    # global CAR_CHARGE
    global PV_GEN_MODIFIER
    global ORIGINAL_PANEL_COUNT
    global MAX_INVERTER_LOAD

    with open(os.path.join(configLocation, "SystemProperties.json"), 'r') as f:
        data = json.load(f)
    STATE_OF_CHARGE_KWH = data["Battery Size"] * INPUT_SOC /100
    BATTERY_MINIMUM_KWH = data["Discharge stop"] * data["Battery Size"] / 100
    IGNORE_LEVEL = data["Min excess"]
    BATTERY_SIZE_KWH = data["Battery Size"]
    maxChargeKWH = data["Max charge"]
    MAX_DISCHARGE_KWH = data["Max discharge"]
    FEED_MODIFIER = data["Massage FeedIn"] / 100
    BUY_MODIFIER = data["Massage Buy"] / 100
    CHARGING_LOSS_FACTOR = 1 + data["(Dis)charge loss"] / 100
    ORIGINAL_PANEL_COUNT = data["Original panels"]
    MAX_INVERTER_LOAD  = data["Max Inverter load"] / 12
    
    _getChargeModel(data)
    
    return data["Scenarios"]

def _setDiversions(diversion_c):
    global DIVERT
    DIVERT = diversion_c
    evdValidity = dict()
    if DIVERT["HWD"]["active"]:
        gramsOfWater = DIVERT["HWD"]["usage"] * 1000
        tempRise = DIVERT["HWD"]["target"] - DIVERT["HWD"]["intake"]
        # Specific heat capacity of water = 4.2 J / g.K
        # 1KWH = 3.6 MJ 
        DIVERT["HWD"]["KWH"] = (gramsOfWater * tempRise * 4.2) / 3600000 
    if DIVERT["EVD"]["active"]:
        c_months = diversion_c["EVD"]["months"]
        c_days = diversion_c["EVD"]["days"]
        c_begin = diversion_c["EVD"]["begin"]
        c_end = diversion_c["EVD"]["end"]
        for m in c_months:
            days = dict()
            for d in c_days:
                days[d] = (c_begin * 60, c_end * 60)
            evdValidity[m] = days
        DIVERT["EVD"]["Validity"] = evdValidity
    return

def _setCarCharge(carCharge_c):
    global CAR_CHARGE
    CAR_CHARGE = dict()
    for config in carCharge_c:
        draw = config["draw"]
        begin = config["begin"]
        end = config["end"]
        for m in config["months"]:
            days = dict()
            for d in config["days"]:
                days[d] = (begin * 60, end * 60, draw / 12)
            CAR_CHARGE[m] = days

def _setLoadShift(cfg_c):
    global LOAD_SHIFT
    LOAD_SHIFT = dict()
    for config in cfg_c:
        stopAt = config["stop at"]
        begin = config["begin"]
        end = config["end"]
        for m in config["months"]:
            LOAD_SHIFT[m] = (begin * 60, end * 60, stopAt * BATTERY_SIZE_KWH / 100)

def _getChargeModel(data):
    # Load the Charge model for the batttery
    cm = data["ChargeModel"]
    int_cm = {int(k) : v for k, v in cm.items()}
    ordered_cm = collections.OrderedDict(sorted(int_cm.items()))
    first = None
    chargeRate = 0
    for k, v in ordered_cm.items():
        if first is None: 
            first = k
            chargeRate = v
            continue
        CHARGE_MODEL[(first * BATTERY_SIZE_KWH / 100, k * BATTERY_SIZE_KWH / 100)] = chargeRate * maxChargeKWH /100
        chargeRate = v
        first = k

def _getMaxChargeForSOC(soc):
    ret = 0
    for key in CHARGE_MODEL:
        if key[0] <= soc < key[1]:
            ret = CHARGE_MODEL[key]
    return ret

def _loadPricePlans(configLocation):
    with open(os.path.join(configLocation, "rates.json"), 'r') as f:
        data = json.load(f)
    return data

def _buildRateLookup(rates):
    lookup = dict()
    for rate in rates:
        hours = rate["Hours"]
        for day in rate["Days"]:
            lookup[day] = {}
            for hour, hourlyrate in enumerate(hours):
                lookup[day][(hour*60, (hour+1)*60)] = hourlyrate

    return lookup

def _getRate(rateLookup, dow, mod):
    rate = 0
    ranges = rateLookup[dow]
    for key in ranges:
        if key[0] < mod < key[1]:
            rate = ranges[key]

    return rate

def _getCosts(usage, rateLookup, feedInRate):
    # usage indices: 0=Date, 1=MOD, 2=DOW, 3=feed, 4=buy, 5=soc
    buy = 0
    sell = 0
    for use in usage:
        rate = _getRate(rateLookup, use[2], use[1])
        buy += use[4] * rate
        sell += use[3] * feedInRate

    return buy, sell

def _showMeTheMoney(usage, pricePlans):
    ret = []
    for plan in pricePlans:
        active = True
        try:
            active = plan["Active"]
        except:
            pass
        if not active: continue
        cost = {}
        cost["Supplier"] = plan["Supplier"]
        cost["Plan"] = plan["Plan"]
        print ("\tWorking on plan: " + cost["Supplier"] + "::" + cost["Plan"])
        rateLookup = _buildRateLookup(plan["Rates"])
        feedInRate = plan["Feed"]
        buy, sell = _getCosts(usage, rateLookup, feedInRate)
        cost["Buy"] = buy / 100
        cost["Sell"] = sell / 100
        cost["Fixed"] = plan["Standing charges"]
        cost["Carrot"] = plan["Bonus cash"]
        cost["Total"] = ((buy - sell) / 100) - cost["Carrot"] + cost["Fixed"]
        ret.append(cost)

    return ret

def _loadScenario(scenario):
    global BATTERY_SIZE_KWH
    global BATTERY_MINIMUM_KWH
    # global LOAD_SHIFT
    # global CAR_CHARGE
    global PV_GEN_MODIFIER

    BATTERY_SIZE_KWH = scenario["Battery Size"]
    BATTERY_MINIMUM_KWH = scenario["Discharge stop"] * scenario["Battery Size"] / 100
    cfg_c = scenario["LoadShift"]
    _setLoadShift(cfg_c)
    PV_GEN_MODIFIER = scenario["Increaed panels"] / ORIGINAL_PANEL_COUNT
    
    carCharge_c = scenario["CarCharge"]
    _setCarCharge(carCharge_c)

    diversion_c = {"HWD": {"active": False}, "EVD": {"active": False}}
    try: 
        diversion_c = scenario["Divert"]
    except: pass
    _setDiversions(diversion_c)

    print ("Working on scenario: " + scenario["Name"])
    return scenario["Name"]

def double_click(event):
    """
    Additional event for double-click on header
    event: class event
    """
    region = TABLE.identify("region", event.x, event.y)
    if region == 'heading':                                 # Only care double-clock on headings
        cid = int(TABLE.identify_column(event.x)[1:])-1     # check which column clicked
        WINDOW.write_event_value("-TABLE-DOUBLE-CLICK-", cid)

def click(event):
    """
    Additional event for double-click on header
    event: class event
    """
    region = TABLE.identify("region", event.x, event.y)
    if region == 'heading':                                 # Only care double-clock on headings
        cid = int(TABLE.identify_column(event.x)[1:])-1     # check which column clicked
        WINDOW.write_event_value("-TABLE-CLICK-", cid)

def _renderSimpleGUI(chartData, begin, end):
    global TABLE
    global WINDOW
    # sg.theme('DarkBlue')
    # sg.set_options(font='Courier 11')
    layout = [
        [sg.Table(chartData[1:], headings=chartData[0], auto_size_columns=True,
            def_col_width=20, enable_events=True, key='-TABLE-', expand_x=True, expand_y=True)],
        [sg.Button('Close', key='-CLOSEREPORT-', size=(25,1)), sg.Button('Save CSV', key='-SAVEREPORT-', size=(25,1))]
    ]
    title = 'SimulationResults (' + str(end) + ' months beginning ' + begin + ')'
    WINDOW = sg.Window(title, layout, resizable=True, finalize=True)
    TABLE = WINDOW['-TABLE-'].Widget
    TABLE.bind('<Double-1>', double_click, add='+')
    TABLE.bind('<Button-1>', click, add='+')
    while True:
        event, values = WINDOW.read()
        if event == sg.WINDOW_CLOSED:
            WINDOW.close()
            break
        elif event == '-TABLE-CLICK-':
            column = values[event]
            # print(f'Click on column {column}')
            # Sort data on the table by the value of column
            sortedCD = []
            if column > 2:
                sortedCD.extend(sorted(chartData[1:], key = lambda x: (int(x[column]), x[0], x[1], x[2])  ) )
            else:
                sortedCD.extend(sorted(chartData[1:], key = lambda x: x[column]))
            # then update window['-TABLE-'].update(values=new_data)
            WINDOW['-TABLE-'].update(values=sortedCD)
        elif event == '-TABLE-DOUBLE-CLICK-':
            column = values[event]
            # print(f'Click on column {column}')
            # Sort data on the table by the value of column
            sortedCD = []
            if column > 2:
                sortedCD.extend(sorted(chartData[1:], reverse=True, key = lambda x: (int(x[column]), x[0], x[1], x[2])  ) )
            else:
                sortedCD.extend(sorted(chartData[1:], reverse=True, key = lambda x: x[column]))
            # then update window['-TABLE-'].update(values=new_data)
            WINDOW['-TABLE-'].update(values=sortedCD)
        elif event == '-SAVEREPORT-':
            with open(os.path.join(CONFIG, "EnvProperties.json"), 'r') as f:
                env = json.load(f)
            STORAGE = os.path.join(env["StorageFolder"])
            myFormats = [('Comma separated values','*.csv')]
            filename = sg.filedialog.asksaveasfilename(filetypes=myFormats, initialdir=STORAGE, defaultextension="*.csv", initialfile=title)
            with open(filename, "w", newline="\n") as f:
                writer = csv.writer(f)
                writer.writerows(chartData)
        elif event == '-CLOSEREPORT-':
            WINDOW.close()
            break


def _render(report, begin, end):
    chartDataII = [["Scenario", "Supplier", "Plan", "Nett(???)", "Bought (kWH)", "Bought(???)", "Sold (kWH)", "Sold(???)", "Standing(???)", "Bonus(???)", "EV load", "Divert HW", "% HW Need", "Divert EV"]]
    for scenario in report:
        for plan in scenario["Plan Costs"]:
            fixed12m = float(plan["Fixed"])
            fixed = float('%.2f' % (fixed12m/12*int(end)))
            total = '%.2f' % (int(plan["Total"]) - fixed12m + fixed)
            percentOfHWNeed = 0
            try: percentOfHWNeed = '%.2f' % ((scenario["Totals"]["totalHWDiv"] / scenario["Totals"]["totalHWDNeed"]) * 100)
            except: pass
            # "{:.2f}".format(5)
            chartDataII.append([scenario["Scenario"], plan["Supplier"], plan["Plan"], float(total), int(scenario["Totals"]["totalBuy"]), 
                                str(int(plan["Buy"])), int(scenario["Totals"]["totalFeed"]), str(int(plan["Sell"])), fixed, plan["Carrot"],
                                int(scenario["Totals"]["totalEV"]), int(scenario["Totals"]["totalHWDiv"]), float(percentOfHWNeed),
                                int(scenario["Totals"]["totalEVDiv"]) ])
    _renderSimpleGUI(chartDataII, begin, end)


def guiMain(config, begin, end):
    global CONFIG
    CONFIG = config
    start = datetime.datetime.strptime(begin, '%Y-%m-%d')
    finish = start + relativedelta(months=int(end)) + datetime.timedelta(days=-1)
    print ("Simulating from " + datetime.datetime.strftime(start, '%Y-%m-%d') + " to " + datetime.datetime.strftime(finish, '%Y-%m-%d'))
    
    env = {}
    with open(os.path.join(CONFIG, "EnvProperties.json"), 'r') as f:
        env = json.load(f)
    dbFile = os.path.join(env["StorageFolder"], env["DBFileName"])
    configLocation = env["ConfigFolder"]

    scenarios = _loadProperties(configLocation)
    pricePlans = _loadPricePlans(configLocation)
    df = _loadDataFrameFromDB(dbFile)
    report = []
    for scenario in scenarios:
        active = False
        try:
            active = scenario["Active"]
        except:
            pass
        if not active: continue
        sName = _loadScenario(scenario)
        res, totals = _simulate(df, start, finish)
        prices = _showMeTheMoney(res, pricePlans)
        report.append({"Scenario": sName, "Totals": totals, "Plan Costs": prices})
    
    _render(report, begin, end)

def main():
    begin = input("Start date (YYYY-MM-DD): ")
    end = input("Number of months to simulate: ")
    guiMain(begin, end)
    
if __name__ == "__main__":
    try:
        CONFIG = sys.argv[1]
    except:
        pass
    print(CONFIG)
    main()