import schedule
import time
import datetime
from pybit import HTTP

class TradingBot:
    tradeUnit = 0.001
    fallCount = 0
    candleAvg = 0
    botState = 'Idle'
    buyOrderID = ''
    sellOrderID = ''
    candleValue = [0.7,0.7,0.7,0.7,0.7,0.7,0.7,0.7,0.7,0.7,0.7,0.7,0.8,0.8,0.8,0.8,0.8,0.8,0.9,0.9,0.9,1,1,1]

    api_key = ''
    api_secret = ''

    session = HTTP(
        endpoint="https://api.bybit.com",
        api_key=api_key,
        api_secret=api_secret
    )

    def getEntryPrice(self):
        positions = self.session.my_position(
            symbol="BTCUSDT"
        )

        for position in positions['result']:
            if position["symbol"] == "BTCUSDT":
                return float(position['entry_price'])

    def getAmount(self):
        positions = self.session.my_position(
            symbol="BTCUSDT"
        )

        for position in positions['result']:
            if position["symbol"] == "BTCUSDT":
                return float(position['size'])

    def getLeverage(self):
        positions = self.session.my_position(
            symbol="BTCUSDT"
        )

        for position in positions['result']:
            if position["symbol"] == "BTCUSDT":
                return float(position['leverage'])

    def getLastPrice(self):
        trades = self.session.user_trade_records(
            symbol="BTCUSDT"
        )

        for trade in trades['result']['data']:
            if trade['side'] == 'Buy':
                if trade['exec_type'] == 'Trade':
                    return trade['order_price']

    def getOrderStatus(self,id):
        status = self.session.query_active_order(
            symbol="BTCUSDT",
            order_id=id
        )

        return status['result']['order_status']

    def getBalance(self):
        balance = self.session.get_wallet_balance(coin="USDT")
        return balance['result']['USDT']['available_balance']

    def getCurrentPrice(self):
        now = datetime.datetime.now()
        today = datetime.datetime(
            year=now.year,
            month=now.month,
            day=now.day,
            hour=now.hour,
            minute=int(now.minute / 5) * 5,
            second=0
        )

        from_time = time.mktime(today.timetuple())

        result = self.session.query_kline(
            symbol="BTCUSDT",
            interval=5,
            limit=1,
            from_time=from_time
        )

        return result['result'][0]['close']

    def candleAvgInit(self):
        now = datetime.datetime.now()
        today = datetime.datetime(
            year=now.year,
            month=now.month,
            day=now.day,
            hour=now.hour,
            minute=int(now.minute / 5) * 5,
            second=0
        )
        delta = datetime.timedelta(minutes=-5*12)
        dt = today + delta
        from_time = time.mktime(dt.timetuple())

        result = self.session.query_kline(
            symbol="BTCUSDT",
            interval=5,
            limit=12,
            from_time=from_time
        )

        priceList=[]
        sum = 0
        tickers = result['result']

        for ticker in tickers:
            if ticker['open'] > ticker['close']:
                self.fallCount += 1
            elif ticker['open'] < ticker['close']:
                self.fallCount = 0
            priceList.append(abs(ticker['open']-ticker['close']))
            sum += abs(ticker['open']-ticker['close'])

        self.candleAvg = sum/12

        print('[', datetime.datetime.now(), '] 5m candle avg init | candleAvg :', self.candleAvg , '| fallCount :', self.fallCount)

        self.buyOrderID = ''
        self.sellOrderID = ''

        if self.botState == '1PosActive':
            self.botState = 'Idle'

    def makeOrder(self):
        now = datetime.datetime.now()
        today = datetime.datetime(
            year=now.year,
            month=now.month,
            day=now.day,
            hour=now.hour,
            minute=int(now.minute / 5) * 5,
            second=0
        )
        if self.fallCount == 0:
            delta = datetime.timedelta(minutes=-5 * 1)
            dt = today + delta
            from_time = time.mktime(dt.timetuple())

            result = self.session.query_kline(
                symbol="BTCUSDT",
                interval=5,
                limit=2,
                from_time=from_time
            )
        else:
            delta = datetime.timedelta(minutes=-5 * (self.fallCount+1))
            dt = today + delta
            from_time = time.mktime(dt.timetuple())

            result = self.session.query_kline(
                symbol="BTCUSDT",
                interval=5,
                limit=self.fallCount+2,
                from_time=from_time
            )

        self.botState = '1PosActive'
        print('[', datetime.datetime.now(), '] botState :' , self.botState)
        if result['result'][0]['close'] - self.candleAvg * 0.9 < result['result'][-1]['close']:
            self.buyLimitOrder(self.tradeUnit, round(result['result'][0]['close'] - self.candleAvg * 0.9,1))
        else:
            self.buyLimitOrder(self.tradeUnit, self.getBidPrice())
            print('[', datetime.datetime.now(), '] current price order')

    def getBidPrice(self):
        orderbook = self.session.orderbook(symbol="BTCUSDT")

        return orderbook['result'][0]['price']

    def buyLimitOrder(self,size,price):
        if self.buyOrderID != '': self.cancelOrder(self.buyOrderID)
        if self.getBalance() > float(size)*float(price)/float(self.getLeverage()):
            order = self.session.place_active_order(
                symbol="BTCUSDT",
                side="Buy",
                order_type="Limit",
                price=price,
                qty=size,
                time_in_force="PostOnly",
                reduce_only=False,
                close_on_trigger=False
            )

            self.buyOrderID = order['result']['order_id']

            print('[', datetime.datetime.now(), '] limit buy order | size :' , size , '| price :' ,price , '| id :' , order['result']['order_id'])
        else:
            print('[', datetime.datetime.now(), '] cancel due to lack of balance')

    def sellLimitOrder(self,size,price):
        if self.sellOrderID != '': self.cancelOrder(self.sellOrderID)
        order = self.session.place_active_order(
            symbol="BTCUSDT",
            side="Sell",
            order_type="Limit",
            price=price,
            qty=size,
            time_in_force="PostOnly",
            reduce_only=True,
            close_on_trigger=False
        )

        self.sellOrderID = order['result']['order_id']

        print('[', datetime.datetime.now(), '] limit sell order | size :' , size , '| price :' ,price , '| id :' , order['result']['order_id'])

    def cancelAllOrder(self):
        self.session.cancel_all_active_orders(
            symbol="BTCUSDT"
        )

        print('[', datetime.datetime.now(), '] all order cancel')

    def cancelOrder(self,id):
        if self.getOrderStatus(id) == 'New':
            self.session.cancel_active_order(
                symbol="BTCUSDT",
                order_id=id
            )

            print('[', datetime.datetime.now(), ']',id,'order cancel')

    def checkOrder(self):
        if self.botState == 'Idle':
            self.makeOrder()
        elif self.botState == '1PosActive':
            if self.getOrderStatus(self.buyOrderID) == 'Filled':
                self.botState = '1PosFilled'
                print('[', datetime.datetime.now(), '] botState :', self.botState)
                self.buyOrderID = ''
        elif self.botState == '1PosFilled':
            if self.sellOrderID == '' and self.buyOrderID == '':
                if self.getLastPrice() - self.candleAvg * 0.9 < self.getCurrentPrice():
                    self.buyLimitOrder(self.getAmount(), round(self.getLastPrice() - self.candleAvg * 0.9,1))
                else:
                    self.buyLimitOrder(self.getAmount(), self.getBidPrice())
                self.sellLimitOrder(self.getAmount(), round(self.getEntryPrice() * 1.003 , 1))
            if self.buyOrderID != '':
                if self.getOrderStatus(self.buyOrderID) == 'Filled':
                    self.botState = '2+PosFilled'
                    print('[', datetime.datetime.now(), '] botState :', self.botState)
                    self.cancelOrder(self.sellOrderID)
                    self.buyOrderID = ''
                    self.sellOrderID = ''
            if self.sellOrderID != '':
                if self.getOrderStatus(self.sellOrderID) == 'Filled':
                    self.botState = 'Idle'
                    print('[', datetime.datetime.now(), '] botState :', self.botState)
                    self.cancelOrder(self.buyOrderID)
                    self.buyOrderID = ''
                    self.sellOrderID = ''
        elif self.botState == '2+PosFilled':
            if self.sellOrderID == '' and self.buyOrderID == '':
                if self.getLastPrice() - self.candleAvg * 0.9 < self.getCurrentPrice():
                    self.buyLimitOrder(self.getAmount(), round(self.getLastPrice() - self.candleAvg * 0.9,1))
                else:
                    self.buyLimitOrder(self.getAmount(), self.getBidPrice())
                self.sellLimitOrder(self.getAmount() - self.tradeUnit, round(self.getEntryPrice(),1))
            if self.buyOrderID != '':
                if self.getOrderStatus(self.buyOrderID) == 'Filled':
                    self.cancelOrder(self.sellOrderID)
                    self.buyOrderID = ''
                    self.sellOrderID = ''
            if self.sellOrderID != '':
                if self.getOrderStatus(self.sellOrderID) == 'Filled':
                    self.botState = '1PosFilled'
                    print('[', datetime.datetime.now(), '] botState :', self.botState)
                    if self.buyOrderID != '':
                        self.cancelOrder(self.buyOrderID)
                    self.buyOrderID = ''
                    self.sellOrderID = ''



t = TradingBot()

if t.getAmount() == t.tradeUnit:
    t.botState = '1PosFilled'
elif t.getAmount() > t.tradeUnit:
    t.botState = '2+PosFilled'

t.cancelAllOrder()
t.candleAvgInit()


for h in range(24):
    for m in range(0,60,5):
        if h < 10 and m < 10:
            schedule.every().day.at("0"+str(h)+":0"+str(m)+":01").do(t.candleAvgInit)
        elif h < 10 and m >= 10:
            schedule.every().day.at("0" + str(h) + ":" + str(m) + ":01").do(t.candleAvgInit)
        elif h >= 10 and m < 10:
            schedule.every().day.at(str(h) + ":0" + str(m) + ":01").do(t.candleAvgInit)
        elif h >= 10 and m >= 10:
            schedule.every().day.at(str(h) + ":" + str(m) + ":01").do(t.candleAvgInit)

schedule.every(1).seconds.do(t.checkOrder)

while True:
    schedule.run_pending()
    time.sleep(1)