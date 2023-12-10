from collections import defaultdict, deque
from shioaji import BidAskFOPv1, Exchange
import shioaji as sj
import datetime
import pandas as pd
import talib as ta
import time
from math import ceil
import pysimulation

api = sj.Shioaji(simulation=True)
accounts = api.login(
    api_key="5FpXzk4h7mF5PM9eHpP7yJSQK28DS5BAT2kxW6YSud6R",     # 請修改此處
    secret_key="9Qzboqh9dkZ5SVWmJYxx41HaG9tWQ3PiVt4NkLmfqGVk"   # 請修改此處
)

order = pysimulation.order('108062172') # 請改成自己的學號

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
while datetime.datetime.now().time() < datetime.time(13, 40):
    time.sleep(1)


    # this place can add stop or limit order
    self_list_positions = order.list_positions(msg_queue['bidask'][-1])
    self_position = 'None' if len(
        self_list_positions) == 0 else self_list_positions['direction']
    if self_position == 'Buy':
        if msg_queue['bidask'][-1]['ask_price'][0] < sl:
            order.place_order(msg_queue['bidask'][-1], 'Sell', 'Cover')
    if self_position == 'Sell':
        if msg_queue['bidask'][-1]['ask_price'][0] > sl:
            order.place_order(msg_queue['bidask'][-1], 'Buy', 'Cover')

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
            long_sl = 990
            short_sl = 1010
            kd_period = 9
            div = 3
            j_bar = 60
            
            long_bar = 0
            short_bar = 0
            
            dif, dea, hist = ta.MACD(df_5min["Close"], fastperiod=fastperiod, slowperiod=slowperiod, signalperiod=signalperiod)
            k, d = ta.STOCH(df_5min['High'], df_5min['Low'], df_5min['Close'], kd_period, div, div)
            j = 3*k - 2*d
            
            condition1 = datetime.datetime.now().time() < datetime.time(13, 25)
            condition2 = (dif[-2] < dea[-2]) and (dif[-1] > dea[-1])
            condition3 = dif[-1] >= long_bar
            condition4 = j[-1] >= j_bar
            condition5 = (dif[-2] > dea[-2]) and (dif[-1] < dea[-1])
            condition6 = dif[-1] <= short_bar
            condition7 = j[-1] <= j_bar
            condition8 = dif[-1] >= dea[-1]
            condition9 = (dif[-2] < long_bar) and (dif[-1] > long_bar)
            condition11 = dif[-1] <= dea[-1]
            condition12 = (dif[-2] > short_bar) and (dif[-1] < short_bar)
            condition14 = hist[-1] >= 0
            condition15 = hist[-1] <= 0
            condition16 = datetime.datetime.now().time() >= datetime.time(13, 25)
            #condition5 = df_5min['Close'][-1] <= self_min[-1]

            

            self_list_positions = order.list_positions(msg_queue['bidask'][-1])

            self_position = 'None' if len(
                self_list_positions) == 0 else self_list_positions['direction']

            if condition1 and self_position == 'None' and short_low == -1 and long_high == -1:
                if condition2 and condition3 and condition4:    
                    long_high = df_5min['High'][-1]
                    long_low = df_5min['Low'][-1]
                elif condition5 and condition6 and condition7:
                    short_high = df_5min['High'][-1]
                    short_low = df_5min['Low'][-1]
                elif condition8 and condition9 and condition4:    
                    long_high = df_5min['High'][-1]
                    long_low = df_5min['Low'][-1]
                elif condition11 and condition12 and condition7:
                    short_high = df_5min['High'][-1]
                    short_low = df_5min['Low'][-1]
            elif condition1 and self_position == 'None' and long_high != -1:
                if msg_queue['bidask'][-1]['ask_price'][0] >= long_high:
                    order.place_order(
                            msg_queue['bidask'][-1], 'Buy', 'New')
                    sl = df_5min['Low'][-1]
                    long_low = -1
                    long_high = -1
                elif msg_queue['bidask'][-1]['ask_price'][0] <= long_low:
                    long_low = -1
                    long_high = -1
            elif condition1 and self_position == 'None' and short_low != -1:
                if msg_queue['bidask'][-1]['ask_price'][0] <= short_low:
                    order.place_order(
                            msg_queue['bidask'][-1], 'Sell', 'New')
                    sl = df_5min['High'][-1]
                    short_high = -1
                    short_low = -1
                elif msg_queue['bidask'][-1]['ask_price'][0] >= short_high:
                    short_high = -1
                    short_low = -1
            elif (condition16 or ( condition7 and condition15) ) and self_position == 'Buy':
                order.place_order(msg_queue['bidask'][-1], 'Sell', 'Cover')
            elif (condition16 or ( condition4 and condition14) ) and self_position == 'Sell':
                order.place_order(msg_queue['bidask'][-1], 'Buy', 'Cover')


api.quote.unsubscribe(
    contract,
    quote_type=sj.constant.QuoteType.BidAsk,
    version=sj.constant.QuoteVersion.v1
)

api.logout()