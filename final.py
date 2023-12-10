from collections import defaultdict, deque
from shioaji import BidAskFOPv1, Exchange
import shioaji as sj
import datetime
import pandas as pd
import talib as ta
import time
from math import ceil
import pytrader as pyt

api_key='5FpXzk4h7mF5PM9eHpP7yJSQK28DS5BAT2kxW6YSud6R' # 請修改此處
secret_key='9Qzboqh9dkZ5SVWmJYxx41HaG9tWQ3PiVt4NkLmfqGVk' # 請修改此處

api = sj.Shioaji(simulation=True)
accounts = api.login(
    api_key=api_key,
    secret_key=secret_key
)

# 輸入學號、API_KEY、SECRET_KEY
trader = pyt.pytrader(strategy='108062172', api_key=api_key, secret_key=secret_key) 
# 設定商品
trader.contract('TXF')

contract = min(
    [
        x for x in api.Contracts.Futures.TXF
        if x.code[-2:] not in ["R1", "R2"]
    ],
    key=lambda x: x.delivery_date
)

msg_queue = defaultdict(deque)
api.set_context(msg_queue)


@api.on_bidask_fop_v1(bind=True)
def quote_callback(self, exchange: Exchange, bidask: BidAskFOPv1):
    # append quote to message queue
    self['bidask'].append(bidask)


api.quote.subscribe(
    contract,
    quote_type=sj.constant.QuoteType.BidAsk,
    version=sj.constant.QuoteVersion.v1
)

time.sleep(2.5)

# get maximum strategy kbars to dataframe, extra 30 it's for safety
bars = 26 + 30

# since every day has 60 kbars (only from 8:45 to 13:45), for 5 minuts kbars
days = ceil(bars/60)

df_5min = []
while(len(df_5min) < bars):
    kbars = api.kbars(
        contract=api.Contracts.Futures.TXF.TXFR1,
        start=(datetime.date.today() -
               datetime.timedelta(days=days)).strftime("%Y-%m-%d"),
        end=datetime.date.today().strftime("%Y-%m-%d"),
    )
    df = pd.DataFrame({**kbars})
    df.ts = pd.to_datetime(df.ts)
    df = df.set_index('ts')
    df.index.name = None
    df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
    df = df.between_time('08:44:00', '13:45:01')
    df_5min = df.resample('5T', label='right', closed='right').agg(
        {'Open': 'first',
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum'
         })
    df_5min.dropna(axis=0, inplace=True)
    days += 1

ts = datetime.datetime.now()

sl = 0
long_high = -1
long_low = -1
short_high = -1
short_low = -1
thresholdTimelong = 0
thresholdTimeshort = 0
jbar=60

while datetime.datetime.now().time() < datetime.time(13, 40):
    time.sleep(1)

    # this place can add stop or limit order
    if(len(trader.position) == 0):
        self_position = 'None'
    else:
        self_position = 'Buy' if trader.position['is_long'] else 'Sell'
    
    if self_position == 'Buy':    
        if msg_queue['bidask'][-1]['ask_price'][0] < sl:
            trader.sell(size = 1)
    if self_position == 'Sell':
        if msg_queue['bidask'][-1]['ask_price'][0] > sl:
            trader.buy(size = 1)

    # local time > next kbars time
    if(datetime.datetime.now() >= ts):
        if self_position == 'Buy':
            sl = min(df_5min['Low'][-1],df_5min['Low'][-2],df_5min['Low'][-3])
        if self_position == 'Sell':
            sl = max(df_5min['High'][-1],df_5min['High'][-2],df_5min['High'][-3])

        kbars = api.kbars(
            contract=api.Contracts.Futures.TXF.TXFR1,
            start=datetime.date.today().strftime("%Y-%m-%d"),
            end=datetime.date.today().strftime("%Y-%m-%d"),
        )
        df = pd.DataFrame({**kbars})
        df.ts = pd.to_datetime(df.ts)
        df = df.set_index('ts')
        df.index.name = None
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
        df = df.between_time('08:44:00', '13:45:01')
        df = df.resample('5T', label='right', closed='right').agg({
            'Open': 'first',
            'High': 'max',
            'Low': 'min',
            'Close': 'last',
            'Volume': 'sum'})
        df.dropna(axis=0, inplace=True)
        df_5min.update(df)
        to_be_added = df.loc[df.index.difference(df_5min.index)]
        df_5min = pd.concat([df_5min, to_be_added])
        ts = df_5min.iloc[-1].name.to_pydatetime()

        # next kbar time update and local time < next kbar time
        if (datetime.datetime.now().minute != ts.minute):

            df_5min = df_5min[:-1]

            fastperiod = 12
            slowperiod = 26
            signalperiod = 9
            kd_period = 9
            div = 3
            
            
            
            dif, dea, hist = ta.MACD(df_5min["Close"], fastperiod=fastperiod, slowperiod=slowperiod, signalperiod=signalperiod)
            k, d = ta.STOCH(df_5min['High'], df_5min['Low'], df_5min['Close'], kd_period, div, div)
            j = 3*k - 2*d
            ema = ta.EMA(df_5min['Close'], 7)

            condition1 = datetime.datetime.now().time() < datetime.time(13, 25)
            condition2 = (dif[-2] < dea[-2]) and (dif[-1] > dea[-1])
            condition5 = (dif[-2] > dea[-2]) and (dif[-1] < dea[-1])
            condition8 = dif[-1] >= dea[-1]
            condition11 = dif[-1] <= dea[-1]
            condition14 = hist[-1] >= 0
            condition15 = hist[-1] <= 0
            condition16 = datetime.datetime.now().time() >= datetime.time(13, 25)
            
            if(len(trader.position) == 0):
                self_position = 'None'
            else:
                self_position = 'Buy' if trader.position['is_long'] else 'Sell'

            
            if condition1 and self_position == 'None' and short_low == -1 and long_high == -1:
                if  condition2 and ((k[-2] < k[-2]) and (d[-1] > d[-1])) and df_5min['Close'] >= ema[-1]:    
                    trader.buy(size = 1)
                    jbar=60
                elif condition5 and ((d[-2] < d[-2]) and (k[-1] > k[-1])) and df_5min['Close'] <= ema[-1]:
                    trader.sell(size = 1)
                    jbar=60
                elif condition2 and dif[-1] >= -45 and j[-1] >= 45:    
                    long_high = df_5min['High'][-1]
                    long_low = df_5min['Low'][-1]
                    jbar=45
                elif condition5 and dif[-1] <= 10 and j[-1] <= 55:
                    short_high = df_5min['High'][-1]
                    short_low = df_5min['Low'][-1]
                    jbar=55
                elif condition8 and ((dif[-2] < 5) and (dif[-1] > 5)) and j[-1] >= 75: 
                    long_high = df_5min['High'][-1]
                    long_low = df_5min['Low'][-1]
                    jbar=75
                elif condition11 and ((dif[-2] > -25) and (dif[-1] < -25)) and j[-1] <= 60:
                    short_high = df_5min['High'][-1]
                    short_low = df_5min['Low'][-1]
                    jbar=60
            elif condition1 and self_position == 'None' and long_high != -1:
                if msg_queue['bidask'][-1]['ask_price'][0] >= long_high:
                    trader.buy(size = 1)
                    sl = df_5min['Low'][-1]
                    long_low = -1
                    long_high = -1
                    thresholdTimelong = 0
                elif msg_queue['bidask'][-1]['ask_price'][0] <= long_low or thresholdTimelong > 3:
                    long_low = -1
                    long_high = -1
                    thresholdTimelong = 0
                else:
                    thresholdTimelong += 1
            elif condition1 and self_position == 'None' and short_low != -1:
                if msg_queue['bidask'][-1]['ask_price'][0] <= short_low:
                    trader.sell(size = 1)
                    sl = df_5min['High'][-1]
                    short_high = -1
                    short_low = -1
                    thresholdTimeshort = 0
                elif msg_queue['bidask'][-1]['ask_price'][0] >= short_high or thresholdTimeshort > 3:
                    short_high = -1
                    short_low = -1
                    thresholdTimeshort = 0
                else:
                    thresholdTimeshort += 1
            elif (condition16 or (j[-1] <= jbar and condition15) ) and self_position == 'Buy':
                trader.sell(size = 1)
            elif (condition16 or (j[-1] >= jbar and condition14) ) and self_position == 'Sell':
                trader.buy(size = 1)


api.quote.unsubscribe(
    contract,
    quote_type=sj.constant.QuoteType.BidAsk,
    version=sj.constant.QuoteVersion.v1
)

api.logout()
