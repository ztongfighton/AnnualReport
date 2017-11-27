import numpy as np
import datetime
import matplotlib as mpl
import matplotlib.dates as dt
import matplotlib.pyplot as plt
import xlrd



#判断股票是否停牌
def isTrading(w, stock_code, date):
    trade_status = w.wss(stock_code, "trade_status", "tradeDate=" + date).Data[0][0]
    if trade_status == "交易":
        return True
    else:
        return False

#判断个股是否开盘涨停或跌停
def isMaxUpOrDown(w, stock_code, date):
    maxupordown = w.wss(stock_code, "maxupordown", "tradeDate=" + date).Data[0][0]
    open_price = w.wsd(stock_code, 'open', date, date, "Fill=Previous").Data[0][0]
    close_price = w.wsd(stock_code, 'close', date, date, "Fill=Previous").Data[0][0]
    low_price = w.wsd(stock_code, 'low', date, date, "Fill=Previous").Data[0][0]
    high_price = w.wsd(stock_code, 'high', date, date, "Fill=Previous").Data[0][0]

    if maxupordown == 0 or (maxupordown != 0 and (open_price != close_price or open_price != high_price or open_price != low_price)):
        return False
    else:
        return True


#组合净值与沪深300的对比图
def plotComparison(w, start_date, end_date):
    #计算沪深300指数收益率
    hs300 = np.array(w.wsd("000300.SH", "close", start_date, end_date, "").Data[0])
    hs300 = hs300 / w.wss("000300.SH", "open", "tradeDate=" + start_date + ";priceAdj=U;cycle=D").Data[0][0]

    #计算组合净值
    total_asset = xlrd.open_workbook(r"净值.xls").sheet_by_index(0).col_values(1)
    total_asset = np.array(total_asset[1:])
    #total_asset = total_asset[1:] / total_asset[0]

    trade_days = w.tdays(start_date, end_date, "").Data[0]
    x = dt.date2num(trade_days)

    mpl.rcParams["font.sans-serif"] = ["Microsoft YaHei"]  # 用来正常显示中文标签
    fig = plt.figure()
    plt.xlabel('日期')
    plt.ylabel('净值')
    plt.plot_date(x, hs300, fmt='g--', xdate=True, ydate=False, label="沪深300")
    plt.plot_date(x, total_asset, fmt='r-', xdate=True, ydate=False, label="策略")
    plt.legend(loc='upper left')
    fig.autofmt_xdate()
    #plt.show()
    plt.savefig("result.png")

def compareStockWithHS300(w, stock_code, start_date, end_date):
    trade_days = w.tdays(start_date, end_date, "").Data[0]
    initial_day = datetime.datetime.strftime(trade_days[0], '%Y%m%d')

    hs300 = np.array(w.wsd("000300.SH", "close", start_date, end_date, "").Data[0])
    hs300 = hs300 / w.wss("000300.SH", "open", "tradeDate=" + initial_day + ";priceAdj=U;cycle=D").Data[0][0]

    wind_A = np.array(w.wsd("881001.WI", "close", start_date, end_date, "").Data[0])
    wind_A = wind_A / w.wss("881001.WI", "open", "tradeDate=" + initial_day + ";priceAdj=U;cycle=D").Data[0][0]

    close_price = np.array(w.wsd(stock_code, "close", start_date, end_date, "PriceAdj=F").Data[0])
    close_price = close_price / w.wss(stock_code, "open", "tradeDate=" + initial_day + ";priceAdj=F;cycle=D").Data[0][0]

    x = dt.date2num(trade_days)

    mpl.rcParams["font.sans-serif"] = ["Microsoft YaHei"]  # 用来正常显示中文标签
    fig = plt.figure()
    plt.xlabel('日期')
    plt.ylabel('净值')
    plt.plot_date(x, hs300, fmt='g--', xdate=True, ydate=False, label="沪深300")
    plt.plot_date(x, wind_A, fmt='b--', xdate=True, ydate=False, label="wind全A")
    plt.plot_date(x, close_price, fmt='r-', xdate=True, ydate=False, label=stock_code)
    plt.legend(loc='upper left')
    fig.autofmt_xdate()
    plt.show()
    #plt.savefig(stock_code + ".png")













