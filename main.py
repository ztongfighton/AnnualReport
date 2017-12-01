from WindPy import *
import pandas as pd
import datetime
import strategy
import strategy_lib

w.start()
strategy_lib.plotComparison(w, "20120104", "20120405")


s = strategy.Strategy()
s.initialize()
#生成买入信号
s.generateBuySignal()

for trade_day in s.trade_days:
    date = datetime.datetime.strftime(trade_day, '%Y%m%d')
    # 执行前一交易日生成的买卖信号
    s.order(date)
    if trade_day == s.trade_days[0]:
        s.initial_asset_value -= s.cash
        s.cash = 0
    s.asset_evaluation(date)
    if date == s.last_signal_date:
        s.generateClearSignal(date)
    else:
        s.generateSellSignal(date)
    print("Finished process " + date)

#二次清盘
s.clearInvestCombi()

#生成净值文件
writer = pd.ExcelWriter("净值.xls")
total_asset = pd.DataFrame(s.total_asset, columns = ["日期", "单位净值", "资产规模", "现金"])
total_asset.set_index(["日期"], inplace = True)
total_asset.sort_index(axis = 0, ascending = True, inplace = True)
total_asset.to_excel(writer, "净值")
writer.save()

#生成交易文件
writer = pd.ExcelWriter("交易.xls")
transaction = pd.DataFrame(s.transaction, columns = ["日期", "成交时间", "证券代码", "交易市场代码", "交易方向", "投保", "交易数量", "交易价格"])
transaction.to_excel(writer, "交易", index = False)
writer.save()

#生成卖出信号文件
writer = pd.ExcelWriter("卖出信息.xls")
sell_info = pd.DataFrame(s.sell_info, columns = ["代码", "简称", "数量", "交易方向", "卖出类型", "卖出原因", "日期"])
sell_info.to_excel(writer, "卖出信息", index = False)
writer.save()

print("Done!")









