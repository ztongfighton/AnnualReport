from WindPy import *
import numpy as np
import pandas as pd
import datetime
import math
import re

class Strategy:
    global w
    # 设置回测开始时间
    start_date = '20100101'
    # 设置回测结束时间
    end_date = '20100331'
    #每日日终生成的交易买信号,包含stock_code, stock_name, amount和type等信息
    buy_signal = {}
    sell_signal = {}
    buy_info = []
    sell_info = []
    #策略持仓,包含stock_code, stock_name, amount, cost, trade_date等信息
    position = {}
    #现金(默认初始现金100万）
    cash = 1000000
    #初始资产总值
    initial_asset_value = 0
    #资产总值
    total_asset = []
    #组合持仓数限制
    cap_num = 30
    #手续费
    commission = 0.002
    #策略交易记录,包含date, time, stock_code, market, direction, amount, price等信息
    transaction = []



    def initialize(self):
        self.trade_days = w.tdays(self.start_date, self.end_date, "").Data[0]
        #关注哪年的年报预披露
        self.year = self.trade_days[0].year - 1
        #买入信号生成日期
        self.signal_date = datetime.datetime(self.year + 1, 1, 1)
        self.signal_date = datetime.datetime.strftime(self.signal_date, '%Y%m%d')
        #卖出信号生成日期
        self.last_signal_date = datetime.datetime.strftime(self.trade_days[-2], '%Y%m%d')
        #清盘日
        self.last_exist_date = datetime.datetime.strftime(self.trade_days[-1], '%Y%m%d')
        #沪深300在1月第一个交易日的开盘点位
        initial_day = datetime.datetime.strftime(self.trade_days[0], '%Y%m%d')
        self.hs300_initial = w.wss("000300.SH", "open", "tradeDate=" + initial_day + ";priceAdj=U;cycle=D").Data[0][0]
        #初始化资产净值
        self.initial_asset_value = self.cash


    def order(self, date):
        if not self.buy_signal and not self.sell_signal:
            return

        stock_codes = list(self.buy_signal.keys()) + list(self.sell_signal.keys())
        trade_status = w.wss(stock_codes, "trade_status", "tradeDate=" + date).Data[0]
        maxupordown = w.wss(stock_codes, "maxupordown", "tradeDate=" + date).Data[0]
        trade_status = pd.Series(trade_status, index = stock_codes)
        maxupordown = pd.Series(maxupordown, index = stock_codes)
        open_prices = w.wss(stock_codes, "open", "tradeDate=" + date + ";priceAdj=U;cycle=D").Data[0]
        open_prices = pd.Series(open_prices, index = stock_codes)
        open_prices_f = w.wss(stock_codes, "open", "tradeDate=" + date + ";priceAdj=F;cycle=D").Data[0]
        open_prices_f = pd.Series(open_prices_f, index = stock_codes)
        other_prices = w.wss(stock_codes, "close, high, low", "tradeDate=" + date + ";priceAdj=U;cycle=D").Data
        other_prices = pd.DataFrame(data = np.matrix(other_prices).T, index = stock_codes, columns = ["close", "high", "low"])

        #处理卖信号
        for stock_code in list(self.sell_signal.keys()):
            open_price = open_prices[stock_code]
            high_price = other_prices.at[stock_code, "high"]
            low_price = other_prices.at[stock_code, "low"]
            if trade_status[stock_code] == '交易' and (maxupordown[stock_code] == 0 or (maxupordown[stock_code] != 0 \
            and (open_price != low_price or open_price != high_price))):
                s = self.sell_signal[stock_code]
                stock_name = s[0]
                amount = s[1]
                self.cash = self.cash + open_price * amount * (1 - self.commission)
                del self.sell_signal[stock_code]
                del self.position[stock_code]
                # 记录交易，包括日期、证券代码、交易市场代码、交易方向、交易数量、交易价格
                tmp = stock_code.split('.')
                trade_code = tmp[0]
                market = tmp[1]
                if market == 'SZ':
                    market = 'XSHE'
                else:
                    market = 'XSHG'
                self.transaction.append([date, "09:30:00", trade_code, market, "SELL", '', amount, open_price])

        #处理买信号
        for stock_code in list(self.buy_signal.keys()):
            open_price = open_prices[stock_code]
            high_price = other_prices.at[stock_code, "high"]
            low_price = other_prices.at[stock_code, "low"]

            if trade_status[stock_code] == '交易' and (maxupordown[stock_code] == 0 or (maxupordown[stock_code] != 0 \
            and (open_price != high_price or open_price != low_price))):
                s = self.buy_signal[stock_code]
                stock_name = s[0]
                amount = s[1]
                type = s[-1]
                if amount * open_price * (1 + self.commission) > self.cash:
                    amount = math.floor(self.cash / (1 + self.commission) / open_price / 100) * 100
                if amount > 0:
                    self.cash = self.cash - open_price * amount * (1 + self.commission)
                    self.position[stock_code] = [stock_name, amount, open_prices_f[stock_code], type, date]
                    # 记录交易，包括日期、证券代码、交易市场代码、交易方向、交易数量、交易价格
                    tmp = stock_code.split('.')
                    trade_code = tmp[0]
                    market = tmp[1]
                    if market == 'SZ':
                        market = 'XSHE'
                    else:
                        market = 'XSHG'
                    self.transaction.append([date, "09:30:00", trade_code, market, "BUY", '', amount, open_price])
            #无论买信号执行与否，删除买信号
            del self.buy_signal[stock_code]


    def generateBuySignal(self):
        try:
            data = pd.read_excel("data" + str(self.year + 1) + ".xls")
        except:
            #获取全部A股列表
            sectorconstituent = w.wset("sectorconstituent", "date=" + self.start_date + ";sectorid=a001010100000000;field=wind_code,sec_name")
            stock_codes = sectorconstituent.Data[0]
            stock_names = sectorconstituent.Data[1]

            #提取年报预披露时间
            stm_predict_issuingdate = w.wss(stock_codes, "stm_predict_issuingdate","rptDate=" + str(self.year) + "1231").Data[0]

            #提取去年年报披露时间
            stm_issuingdate = w.wss(stock_codes, "stm_issuingdate","rptDate=" + str(self.year - 1) + "1231").Data[0]

            #提取上市时间
            ipo_date = w.wss(stock_codes, "ipo_date").Data[0]

            #提取三季报EPS
            eps_basic = w.wss(stock_codes, "eps_basic","rptDate=" + str(self.year) + "0930;currencyType=").Data[0]

            #提取三季报归属母公司股东净利润同比增长率
            yoynetprofit = w.wss(stock_codes, "yoynetprofit","rptDate=" + str(self.year) + "0930").Data[0]

            data = pd.DataFrame({"stock_code" : stock_codes, "stock_name" : stock_names, \
                                 "stm_predict_issuingdate" : stm_predict_issuingdate, \
                                 "stm_issuingdate" : stm_issuingdate, "ipo_date" : ipo_date, \
                                 "eps_basic" : eps_basic, "yoynetprofit" : yoynetprofit})


            writer = pd.ExcelWriter("data" + str(self.year + 1) + ".xls")
            data.to_excel(writer, "年报策略数据")
            writer.save()

        data.set_index("stock_code", inplace = True)
        data.dropna(how = "any", inplace = True)
        # 计算年报预披露时间比去年年报实际披露时间提前的天数
        stock_codes = list(data.index)
        n = len(stock_codes)
        days_ahead = [0] * n
        for i in range(n):
            try:
                days_ahead[i] = (data.at[stock_codes[i], "stm_issuingdate"].replace(year=self.year + 1) - \
                                 data.at[stock_codes[i], "stm_predict_issuingdate"]).days
            except:
                days_ahead[i] = (data.at[stock_codes[i], "stm_issuingdate"].replace(year=self.year + 1, day=28) - \
                                 data.at[stock_codes[i], "stm_predict_issuingdate"]).days
        data["days_ahead"] = days_ahead

        '''
        #选出年报预披露时间在2月15日之前，较去年年报实际披露时间提前60日，三季报eps > 0, 归属母公司股东净利润同比增长率 > 10%，非次新股，非退市股
        selected_stocks = data[(data.stm_predict_issuingdate < datetime.datetime(self.year + 1, 2, 15)) & (data.ipo_date < \
                               datetime.datetime(self.year, 1, 1)) & (data.eps_basic > 0) & (data.yoyprofit > 10) & (data.days_ahead >= 60) \
                               & (data.days_ahead < 365)]
        '''

        #选出年报预披露时间在2月15日之前,较去年年报实际披露时间提前60日,非次新的股票
        candidates = data[(data.stm_predict_issuingdate < datetime.datetime(self.year + 1, 2, 15)) & (data.ipo_date < \
                               datetime.datetime(self.year, 1, 1)) & (data.days_ahead >= 60) & (data.days_ahead < 365)]

        #筛选出可能高送转的股票
        high_tran_candidates = self.getHighTranCandidate(candidates)

        #筛选出有ST摘帽预期的股票
        st_stocks = self.getSTStock(candidates)

        #筛选出限售股解禁的股票
        #share_unlock_stocks = self.getShareUnlockStock(selected_stocks)

        #生成买信号
        stock_codes = list(candidates.index)
        n = len(stock_codes)
        close_prices = w.wss(stock_codes, "close", "tradeDate=" + self.signal_date + ";priceAdj=U;cycle=D").Data[0]
        close_prices = dict(zip(stock_codes, close_prices))
        stock_asset = 1.0 * self.initial_asset_value / n
        for stock_code in stock_codes:
            if stock_code in list(high_tran_candidates.index):
                buy_type = 1
            elif stock_code in list(st_stocks.index):
                buy_type = 2
            else:
                buy_type = 0
            stock_name = candidates.at[stock_code, "stock_name"]
            amount = math.floor(stock_asset / close_prices[stock_code] / 100) * 100
            self.buy_signal[stock_code] = [stock_name, amount, "Buy", buy_type]

        writer = pd.ExcelWriter("股票池.xls")
        candidates = candidates.ix[:, ["stock_name", "stm_predict_issuingdate", "stm_issuingdate", "days_ahead", "eps_basic", "yoynetprofit"]]
        candidates.to_excel(writer, "股票池")
        high_tran_candidates.to_excel(writer, "高送转预期股")
        st_stocks.to_excel(writer, "ST摘帽预期股")
        writer.save()

        '''
        selected_stocks["buy_price"] = 0.0
        selected_stocks["sell_price"] = 0.0
        selected_stocks["profit"] = 0.0
        stock_codes = list(selected_stocks.index)
        buy_prices = w.wss(stock_codes, "open", "tradeDate=" + datetime.datetime.strftime(self.trade_days[0],'%Y%m%d') + ";priceAdj=F;cycle=D").Data[0]
        sell_prices = w.wss(stock_codes, "open", "tradeDate=" + datetime.datetime.strftime(self.trade_days[-1],'%Y%m%d') + ";priceAdj=F;cycle=D").Data[0]
        buy_prices = dict(zip(stock_codes, buy_prices))
        sell_prices = dict(zip(stock_codes, sell_prices))

        for stock_code in stock_codes:
            buy_price = buy_prices[stock_code]
            sell_price = sell_prices[stock_code]
            try:
                profit = float('%.2f' % (100 * (sell_price - buy_price) / buy_price))
                selected_stocks.at[stock_code, "buy_price"] = buy_price
                selected_stocks.at[stock_code, "sell_price"] = sell_price
                selected_stocks.at[stock_code, "profit"] = profit
            except:
                continue
        

        columns = ["stock_name", "stm_predict_issuingdate", "stm_issuingdate", "days_ahead", "eps_basic", "yoyprofit", "profit"]
        selected_stocks = selected_stocks.ix[:, columns]
        '''
        '''
        #记录筛选出的股票
        writer = pd.ExcelWriter("买入信号.xls")
        selected_stocks.to_excel(writer, "买入信号生成信息")
        writer.save()

        #生成买入信号,等权构建组合
        stock_codes = list(selected_stocks.index)
        n = len(stock_codes)
        close_prices = w.wss(stock_codes, "close", "tradeDate=" + self.signal_date + ";priceAdj=U;cycle=D").Data[0]
        close_prices = dict(zip(stock_codes, close_prices))
        stock_asset = 1.0 * self.initial_asset_value / n
        for stock_code in stock_codes:
            stock_name = selected_stocks.at[stock_code, "stock_name"]
            amount = math.floor(stock_asset / close_prices[stock_code] / 100) * 100
            self.signal[stock_code] = [stock_name, amount, "Buy"]
        '''

    def generateSellSignal(self, date):
        #无持仓返回
        if not self.position:
            return

        #监控持仓中有高送转预期的股票，如果业绩预告同比增幅<0或者公布的分红预案并非高送转，则立刻生成卖出信号，卖出
        try:
            yoynetprofit_forcast = pd.read_excel("业绩预告" + str(self.year) + ".xls")
        except:
            stock_codes = list(self.position.keys())
            yoynetprofit_forcast = w.wss(stock_codes, "sec_name, profitnotice_changemin, profitnotice_date","rptDate=" + str(self.year) + "1231").Data
            yoynetprofit_forcast = np.vstack((stock_codes, yoynetprofit_forcast)).T
            yoynetprofit_forcast = pd.DataFrame(data=yoynetprofit_forcast,columns=["stock_code", "sec_name","profitnotice_changemin", "profitnotice_date"])
            yoynetprofit_forcast["profitnotice_changemin"] = yoynetprofit_forcast["profitnotice_changemin"].astype(np.float)
            yoynetprofit_forcast.dropna(how='any', inplace=True)

            writer = pd.ExcelWriter("业绩预告" + str(self.year) + ".xls")
            yoynetprofit_forcast.to_excel(writer)
            writer.save()

        #提取当天公布的业绩预告
        yoynetprofit_forcast.set_index("stock_code", inplace=True)
        yoynetprofit_forcast = yoynetprofit_forcast[yoynetprofit_forcast.profitnotice_date == (datetime.datetime.strptime(date, "%Y%m%d") + \
            datetime.timedelta(days=1))]
        for stock_code in list(yoynetprofit_forcast.index):
            if yoynetprofit_forcast.at[stock_code, "profitnotice_changemin"] < 0 and stock_code in list(self.position.keys()):
                p = self.position[stock_code]
                buy_type = p[-2]
                if buy_type == 1:
                    stock_name = p[0]
                    amount = p[1]
                    sell_type = 0
                    sell_info = "业绩预告归属母公司股东净利润同比增长率小于0"
                    self.sell_signal[stock_code] = [stock_name, amount, "Sell",sell_type, sell_info]
                    self.sell_info.append([stock_code, stock_name, amount, "Sell",sell_type, sell_info, date])

        #提取当天公布的分红预案
        try:
            div_plan = pd.read_excel("分红预案" + str(self.year) + ".xls")
        except:
            stock_codes = list(self.position.keys())
            div_plan = w.wss(stock_codes, "sec_name,div_cashbeforetax,div_stock,div_capitalization,div_prelandate,div_preDisclosureDate","rptDate=" + str(self.year) + "1231").Data
            div_plan = np.vstack((stock_codes, div_plan)).T
            div_plan = pd.DataFrame(data = div_plan, columns=["stock_code", "sec_name", "div_cashbeforetax","div_stock","div_capitalization","div_prelandate","div_preDisclosureDate"])
            div_plan["div_cashbeforetax"] = div_plan["div_cashbeforetax"].astype(np.float)
            div_plan["div_stock"] = div_plan["div_stock"].astype(np.float)
            div_plan["div_capitalization"] = div_plan["div_capitalization"].astype(np.float)
            div_plan.dropna(how='any', inplace=True)

            writer = pd.ExcelWriter("分红预案" + str(self.year) + ".xls")
            div_plan.to_excel(writer)
            writer.save()

        prelandate = datetime.datetime.strptime(date, "%Y%m%d") + datetime.timedelta(days=1)
        div_plan.set_index("stock_code", inplace=True)
        div_plan = div_plan[(div_plan.div_prelandate == prelandate) | (div_plan.div_preDisclosureDate == prelandate)]
        for stock_code in list(div_plan.index):
            if div_plan.at[stock_code, "div_stock"] + div_plan.at[stock_code, "div_capitalization"] < 0.5 and stock_code in list(self.position.keys()):
                p = self.position[stock_code]
                buy_type = p[-2]
                if buy_type == 1:
                    stock_name = p[0]
                    amount = p[1]
                    sell_type = 1
                    sell_info = "分红预案并没有高送转"
                    self.sell_signal[stock_code] = [stock_name, amount, "Sell",sell_type, sell_info]
                    self.sell_info.append([stock_code, stock_name, amount, "Sell", sell_type, sell_info, date])

        #监控实际发生了高送转的股票，在股权登记日当日生成卖出信号，在除息除权日当天开盘卖出
        rptDate = str(self.year) + "1231"
        try:
            dividend = pd.read_excel("dividend" + rptDate + ".xls")
        except:
            dividend = w.wss(list(self.position.keys()), "div_cashbeforetax,div_stock,div_capitalization,div_recorddate",
                             "rptDate=" + rptDate)
            dividend = pd.DataFrame(data=np.matrix(dividend.Data).T, index=dividend.Codes,
                                    columns=["div_cashbeforetax", "div_stock", "div_capitalization", "div_recorddate"])
            dividend.dropna(how = 'any', inplace = True)
            writer = pd.ExcelWriter("dividend" + rptDate + ".xls")
            dividend.to_excel(writer, "分红送转数据")
            writer.save()

        dividend = dividend[(dividend.div_recorddate == datetime.datetime.strptime(date, "%Y%m%d")) & \
                            (dividend.div_stock + dividend.div_capitalization > 0.5)]
        for stock_code in list(dividend.index):
            if stock_code in list(self.position.keys()):
                p = self.position[stock_code]
                stock_name = p[0]
                amount = p[1]
                sell_type = 2
                sell_info = "高送转股票股权登记日次日卖出"
                self.sell_signal[stock_code] = [stock_name, amount, "Sell", sell_type, sell_info]
                self.sell_info.append([stock_code, stock_name, amount, "Sell", sell_type, sell_info, date])

        #监控ST摘帽预期股，在摘帽后恢复交易当日卖出
        try:
            st_info = pd.read_excel("ST摘帽" + str(self.year) + ".xls")
        except:
            stock_codes = list(self.position.keys())
            ST_sectorconstituent = w.wset("sectorconstituent", "date=" + str(self.year) + "-12-31;sectorid=1000006526000000;field=wind_code,sec_name").Data[0]
            st_stocks = list(set(stock_codes) & set(ST_sectorconstituent))
            if st_stocks:
                st_info = w.wss(st_stocks, "sec_name,riskadmonition_date").Data
                st_info = np.vstack((st_stocks, st_info)).T
                st_info = pd.DataFrame(data = st_info, columns = ["stock_code", "sec_name", "riskadmonition_date"])
                n = st_info.shape[0]
                for i in range(n):
                    find_date = False
                    riskadmonition_date = st_info.at[i, "riskadmonition_date"]
                    st_related_date_str = riskadmonition_date.split(",")
                    for st_str in st_related_date_str:
                        tmp = st_str.split("：")
                        if "去*ST" in tmp[0] or "去ST" in tmp[0] or "*ST变ST" in tmp[0]:
                            tmp[1] = tmp[1].strip()
                            if tmp[1][0:4] == str(self.year + 1):
                                find_date = True
                                st_info.at[i, "riskadmonition_date"] = tmp[1]
                                break
                    if find_date == False:
                        st_info.drop(i, inplace = True)
            else:
                st_info = pd.DataFrame()
            writer = pd.ExcelWriter("ST摘帽" + str(self.year) + ".xls")
            st_info.to_excel(writer, "ST摘帽")
            writer.save()

        if st_info.empty:
            pass
        else:
            st_info.set_index("stock_code", inplace = True)
            for stock_code in list(st_info.index):
                if stock_code in list(self.position.keys()):
                    riskadmonition_date = datetime.datetime.strptime(str(st_info.at[stock_code, "riskadmonition_date"]), "%Y%m%d") + datetime.timedelta(days=-1)
                    if datetime.datetime.strptime(date, "%Y%m%d") == riskadmonition_date:
                        p = self.position[stock_code]
                        buy_type = p[-2]
                        if buy_type == 2:
                            stock_name = p[0]
                            amount = p[1]
                            sell_type = 3
                            sell_info = "ST股票摘帽复牌当日卖出"
                            self.sell_signal[stock_code] = [stock_name, amount, "Sell", sell_type, sell_info]
                            self.sell_info.append([stock_code, stock_name, amount, "Sell", sell_type, sell_info, date])

        '''
        #计算当前基准距离初始的涨跌
        hs300 = w.wss("000300.SH", "close", "tradeDate=" + date + ";priceAdj=U;cycle=D").Data[0][0]
        hs300 = hs300 / self.hs300_initial

        #如果个股的涨跌向下偏离基准达5%，则生成卖出信号
        stocks_in_position = list(self.position.keys())
        n = len(stocks_in_position)
        close_price_f = w.wss(stocks_in_position, "close", "tradeDate=" + date + ";priceAdj=F;cycle=D").Data[0]
        for i in range(n):
            stock_code = stocks_in_position[i]
            p = self.position[stock_code]
            cost = p[2]
            if close_price_f[i] / cost - hs300 < -0.05:
                stock_name = p[0]
                amount = p[1]
                self.signal[stock_code] = [stock_name, amount, "Sell"]
        '''


    def generateClearSignal(self, date):
        for stock_code, p in self.position.items():
            stock_name = p[0]
            amount = p[1]
            sell_type = -1
            sell_info = "到期清盘卖出"
            self.sell_signal[stock_code] = [stock_name, amount, "Sell", sell_type, sell_info]
            self.sell_info.append([stock_code, stock_name, amount, "Sell", sell_type, sell_info, date])

    def clearInvestCombi(self):
        while len(self.sell_signal) > 0:
            date = w.tdaysoffset(1, self.last_exist_date, "").Data[0][0]
            date = datetime.datetime.strftime(date, '%Y%m%d')
            for stock_code in list(self.sell_signal.keys()):
                trade_info = w.wss(stock_code, "open,high,low,trade_status,maxupordown", "tradeDate=" + date + ";priceAdj=U;cycle=D").Data
                trade_status = trade_info[3][0]
                maxupordown = trade_info[4][0]
                open_price = trade_info[0][0]
                high_price = trade_info[1][0]
                low_price = trade_info[2][0]
                if trade_status == '交易' and (maxupordown == 0 or (maxupordown != 0 and (open_price != low_price or open_price != high_price))):
                    s = self.sell_signal[stock_code]
                    amount = s[1]
                    self.cash = self.cash + open_price * amount * (1 - self.commission)
                    del self.sell_signal[stock_code]
                    del self.position[stock_code]
                    # 记录交易，包括日期、证券代码、交易市场代码、交易方向、交易数量、交易价格
                    tmp = stock_code.split('.')
                    trade_code = tmp[0]
                    market = tmp[1]
                    if market == 'SZ':
                        market = 'XSHE'
                    else:
                        market = 'XSHG'
                    self.transaction.append([date, "09:30:00", trade_code, market, "SELL", '', amount, open_price])

            self.asset_evaluation(date)
            print("Finished process " + date)
            self.last_exist_date = date


    def asset_evaluation(self, date):
        stock_value = 0
        stocks_in_position = list(self.position.keys())
        # 按收盘价对组合估值
        n = len(stocks_in_position)
        if n > 0:
            close_prices = w.wss(stocks_in_position, "close", "tradeDate=" + date + ";priceAdj=U;cycle=D").Data[0]
            for i in range(n):
                stock_code = stocks_in_position[i]
                amount = self.position[stock_code][1]
                close_price = close_prices[i]
                stock_value += close_price * amount

        asset_value = stock_value + self.cash
        self.total_asset.append([date, asset_value / self.initial_asset_value, asset_value, self.cash])

        # 处理持仓股分红送转
        rptDate = str(self.year) + "1231"
        date = datetime.datetime.strptime(date, "%Y%m%d")
        self.processDividend(rptDate, date)


    def processDividend(self, rptDate, date):
        try:
            dividend = pd.read_excel("dividend" + rptDate + ".xls")
        except:
            dividend = w.wss(list(self.position.keys()), "div_cashbeforetax,div_stock,div_capitalization,div_recorddate",
                             "rptDate=" + rptDate)
            dividend = pd.DataFrame(data=np.matrix(dividend.Data).T, index=dividend.Codes,
                                    columns=["div_cashbeforetax", "div_stock", "div_capitalization", "div_recorddate"])
            dividend.dropna(how = 'any', inplace = True)
            writer = pd.ExcelWriter("dividend" + rptDate + ".xls")
            dividend.to_excel(writer, "分红送转数据")
            writer.save()

        for stock_code in self.position.keys():
            if stock_code not in dividend.index:
                continue

            d = dividend.loc[stock_code]
            if date == d["div_recorddate"]:
                p = self.position[stock_code]
                # 确定个人所得税税率
                days_in_position = (d["div_recorddate"] - datetime.datetime.strptime(p[-1], "%Y%m%d")).days
                if days_in_position > 365:
                    tax_ratio = 0.0
                elif days_in_position > 30:
                    tax_ratio = 0.1
                else:
                    tax_ratio = 0.2
                amount = p[1]
                div_cashaftertax = d["div_cashbeforetax"] * amount * (1 - tax_ratio) - d["div_stock"] * tax_ratio * amount
                self.cash += div_cashaftertax
                self.position[stock_code][1] = amount + amount * (d["div_stock"] + d["div_capitalization"])

    def getHighTranCandidate(self, candidates):
        #提取去年三季报每股基本公积，每股留存收益，总股本
        stock_codes = list(candidates.index)
        high_tran_info = w.wss(stock_codes, "sec_name,surpluscapitalps,retainedps,total_shares","rptDate=" + str(self.year) + "0930;unit=1;tradeDate=" + str(self.year) + "1231").Data
        high_tran_info = np.vstack((stock_codes, high_tran_info)).T
        high_tran_info = pd.DataFrame(data = high_tran_info, columns = ["stock_code", "stock_name","surpluscapitalps","retainedps","total_shares"])
        high_tran_info.set_index("stock_code", inplace = True)
        high_tran_info["surpluscapitalps"] = high_tran_info["surpluscapitalps"].astype(np.float)
        high_tran_info["retainedps"] = high_tran_info["retainedps"].astype(np.float)
        high_tran_info["total_shares"] = high_tran_info["total_shares"].astype(np.float)
        #删选出每股资本公积+每股留存收益>3，总股本小于20亿的股票
        high_tran_candidates = high_tran_info[(high_tran_info.surpluscapitalps + high_tran_info.retainedps > 3) & (high_tran_info.total_shares < 20E8)]

        if not high_tran_candidates.empty:
            #提取去年三季报和业绩预告归属母公司股东净利润同比增长率
            stock_codes = list(high_tran_candidates.index)
            yoynetprofit_3rd = w.wss(stock_codes, "yoynetprofit", "rptDate=" + str(self.year) + "0930").Data[0]
            yoynetprofit_3rd = dict(zip(stock_codes, yoynetprofit_3rd))
            yoynetprofit_forcast = w.wss(stock_codes, "profitnotice_changemin, profitnotice_date", "rptDate=" + str(self.year) + "1231").Data
            yoynetprofit_forcast = np.vstack((stock_codes, yoynetprofit_forcast)).T
            yoynetprofit_forcast = pd.DataFrame(data = yoynetprofit_forcast, columns = ["stock_code", "profitnotice_changemin","profitnotice_date"])
            yoynetprofit_forcast.set_index("stock_code", inplace = True)
            yoynetprofit_forcast["profitnotice_changemin"] = yoynetprofit_forcast["profitnotice_changemin"].astype(np.float)
            yoynetprofit_forcast.dropna(how = 'any', inplace = True)
            yoynetprofit_forcast = yoynetprofit_forcast[yoynetprofit_forcast.profitnotice_date <= datetime.datetime(self.year + 1, 1, 1)]

            candidate_list = list(high_tran_candidates.index)
            for stock_code in list(high_tran_candidates.index):
                if stock_code in list(yoynetprofit_forcast.index):
                    if yoynetprofit_forcast.at[stock_code, "profitnotice_changemin"] < 0:
                        candidate_list.remove(stock_code)
                else:
                    if yoynetprofit_3rd[stock_code] < 0:
                        candidate_list.remove(stock_code)
            high_tran_candidates = high_tran_candidates.loc[candidate_list, :]
        return high_tran_candidates

    def getSTStock(self, candidates):
        #找出选出的股票池中的ST股
        ST_sectorconstituent = w.wset("sectorconstituent","date=" + str(self.year) + "-12-31;sectorid=1000006526000000;field=wind_code,sec_name").Data[0]
        st_stocks = []
        for stock_code in list(candidates.index):
            if stock_code in ST_sectorconstituent:
                st_stocks.append(stock_code)
        st_stocks = candidates.loc[st_stocks, :]
        return st_stocks

    def getShareUnlockStock(self, candidates):
        #提取1季度前限售股解禁信息
        stock_codes = list(candidates.index)
        share_unlock_info = w.wss(stock_codes, "sec_name,share_rtd_unlockingdate,share_tradable_current,share_tradable_sharetype","tradeDate=" + str(self.year + 1) + "0331;unit=1").Data
        share_unlock_info = np.vstack((stock_codes, share_unlock_info)).T
        share_unlock_info = pd.DataFrame(data = share_unlock_info, columns = ["stock_code", "sec_name","share_rtd_unlockingdate","share_tradable_current","share_tradable_sharetype"])
        share_unlock_info.set_index("stock_code", inplace = True)
        share_unlock_info["share_tradable_current"] = share_unlock_info["share_tradable_current"].astype(np.float)
        share_unlock_stocks = share_unlock_info[(share_unlock_info.share_rtd_unlockingdate >= datetime.datetime(self.year, 10, 1))]
        #查询解禁股占流通股本的比例，并按该比例从大到小排序
        stock_codes = list(share_unlock_stocks.index)
        float_a_share = w.wss(stock_codes, "float_a_shares", "unit=1;tradeDate=" + str(self.year) + "1231").Data[0]
        float_a_share = dict(zip(stock_codes, float_a_share))
        share_unlock_stocks.loc[:, "ratio"] = 0.0
        for stock_code in stock_codes:
            share_unlock_stocks.at[stock_code, "ratio"] = share_unlock_stocks.at[stock_code, "share_tradable_current"] / float_a_share[stock_code]
        share_unlock_stocks.sort_values(by = "ratio", ascending = False, inplace = True, axis = 0)
        return share_unlock_stocks



