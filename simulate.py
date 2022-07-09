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

def _simulate(df, start, finish):
    res = []
    totalFeed = 0
    totalBuy = 0
    newSOC = STATE_OF_CHARGE_KWH
    
    for r in list(zip(df['NormalLoad'], df['NormalPV'], df['Date'], df['MinuteOfDay'], df['DayOfWeek'])):
        if start <= datetime.datetime.strptime(r[2], '%Y-%m-%d') <= finish:
            cfg, cfgload, newSOC = _getCFG(r[2], r[3], newSOC) # Ignores using solar first if there is spare capacity, so processOneRow does this
            # TODO: Add the car load here
            carload = _getCarLoad(r[2], r[4], r[3])
            newSOC, feed, buy = _processOneRow(newSOC, r[0] + cfgload + carload, r[1], cfg)
            res.append((r[2], r[3], r[4], feed, buy, newSOC)) # Date, MOD, DOW, feed, buy, soc
            totalFeed += feed
            totalBuy += buy
 
    print ("\tBuy: " + str(int(totalBuy)) + " KWh" + "; Sell: " + str(int(totalFeed)) + " KWh")
    return res, int(totalBuy), int(totalFeed)

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
    
    # # Load the CFG configuration
    # cfg_c = data["LoadShift"]
    # _setLoadShift(cfg_c)

    return data["Scenarios"]

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
    ]
    WINDOW = sg.Window('SimulationResults (' + str(end) + ' months, beginning: ' + begin + ')', layout, resizable=True, finalize=True)
    TABLE = WINDOW['-TABLE-'].Widget
    TABLE.bind('<Double-1>', double_click, add='+')
    TABLE.bind('<Button-1>', click, add='+')
    while True:
        event, values = WINDOW.read()
        if event == sg.WINDOW_CLOSED:
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

    WINDOW.close()


def _render(report, begin, end):
    # chartData = {}
    # chartData["Scenario"] = []
    # chartData["Supplier"] = []
    # chartData["Plan"] = []
    # chartData["Nett"] = []
    # chartData["Bought"] = []
    # chartData["Sold"] = []
    # chartData["Descr"] = []
    # chartData["KWH Bought"] = []
    # chartData["KWH Sold"] = []
    # for scenario in report:
    #     for plan in scenario["Plan Costs"]:
    #         chartData["Scenario"].append(scenario["Scenario"])
    #         chartData["Supplier"].append(plan["Supplier"])
    #         chartData["Plan"].append(plan["Plan"])
    #         # chartData["Descr"].append(scenario["Scenario"] + plan["Supplier"] + plan["Plan"]) 
    #         chartData["Nett"].append(plan["Total"])
    #         chartData["Bought"].append(plan["Buy"])
    #         chartData["Sold"].append(plan["Sell"])
    #         chartData["KWH Bought"].append(scenario["KWH Bought"])
    #         chartData["KWH Sold"].append(scenario["KWH Sold"])
    #         descr = scenario["Scenario"] + ", " + plan["Supplier"] + ", " + \
    #             plan["Plan"] + " " 
    #         total = "€" + str(int(plan["Total"])) + " (Buy=" + str(int(plan["Buy"])) + "; Sell=" + str(int(plan["Sell"])) + "; Standing=" + str(int(plan["Fixed"])) + "; Bonus=" + str(int(plan["Carrot"])) + ")"
    #         print (descr + "\n\t" + total)
    chartDataII = [["Scenario", "Supplier", "Plan", "Nett(€)", "KWH Bought", "Bought(€)", "KWH Sold", "Sold(€)", "Standing(€)", "Bonus(€)"]]
    for scenario in report:
        for plan in scenario["Plan Costs"]:
            fixed12m = float(plan["Fixed"])
            fixed = float('%.2f' % (fixed12m/12*int(end)))
            total = '%.2f' % (int(plan["Total"]) - fixed12m + fixed)
            # "{:.2f}".format(5)
            chartDataII.append([scenario["Scenario"], plan["Supplier"], plan["Plan"], float(total), scenario["KWH Bought"], 
                                str(int(plan["Buy"])), scenario["KWH Sold"], str(int(plan["Sell"])), fixed, plan["Carrot"] ])
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
        sName = _loadScenario(scenario)
        res, unitsBought, unitsSold = _simulate(df, start, finish)
        prices = _showMeTheMoney(res, pricePlans)
        report.append({"Scenario": sName, "KWH Bought": unitsBought, "KWH Sold": unitsSold, "Plan Costs": prices})
    
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