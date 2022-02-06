import schedule
import time
import datetime
from pybit import HTTP

class TradingBot:
    tradeUnit = 0.001
    fallCount = 0
    candleAvg = 0
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

    #==========================Position==========================


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

    #==========================Candle==========================

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

        print('[', datetime.datetime.now(), '] 5분 봉 평균 초기화 | 평균 캔들 :', self.candleAvg , '| fall count :', self.fallCount)

        if self.getAmount() == 0:
            self.makeOrder()

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

        self.cancelAllOrder()
        print('[', datetime.datetime.now(), '] size :', self.getAmount())
        if result['result'][0]['close'] - self.candleAvg * 0.9 < result['result'][-1]['close']:
            self.buyLimitOrder(self.tradeUnit, round(result['result'][0]['close'] - self.candleAvg * 0.9,1))
        else:
            self.buyLimitOrder(self.tradeUnit, self.getBidPrice())
            print('현재 가격으로 매수')

    #==========================Buy,Sell==========================

    def getBidPrice(self):
        orderbook = self.session.orderbook(symbol="BTCUSDT")

        return orderbook['result'][0]['price']

    def buyLimitOrder(self,size,price):
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

            print('[', datetime.datetime.now(), '] 지정가 매수 주문 | size :' , size , '| price :' ,price , '| id :' , order['result']['order_id'])
        else:
            print('[', datetime.datetime.now(), '] 잔액 부족으로 매수 주문 취소')

    def sellLimitOrder(self,size,price):
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

        print('[', datetime.datetime.now(), '] 지정가 매도 주문 | size :' , size , '| price :' ,price , '| id :' , order['result']['order_id'])

    def cancelAllOrder(self):
        self.session.cancel_all_active_orders(
            symbol="BTCUSDT"
        )

        print('[', datetime.datetime.now(), '] 모든 주문 취소')
        self.buyOrderID = ''
        self.sellOrderID = ''

    def cancelOrder(self,id):
        self.session.cancel_active_order(
            symbol="BTCUSDT",
            order_id=id
        )

        print('[', datetime.datetime.now(), '] ',id,'주문 취소')

    #============================

    def checkOrder(self):
        if self.sellOrderID != '' and self.buyOrderID != '':
            buyOrderStatus = self.getOrderStatus(self.buyOrderID)
            sellOrderStatus = self.getOrderStatus(self.sellOrderID)
            if buyOrderStatus == 'Filled' or sellOrderStatus == 'Filled' or buyOrderStatus == 'Cancelled' or sellOrderStatus == 'Cancelled':
                self.cancelAllOrder()
            if sellOrderStatus == 'Filled' and self.getAmount() == 0:
                self.makeOrder()

        if self.getAmount() == self.tradeUnit:
            if self.sellOrderID == '':
                if self.getLastPrice() - self.candleAvg * 0.9 < self.getCurrentPrice():
                    self.buyLimitOrder(self.getAmount(), round(self.getLastPrice() - self.candleAvg * 0.9,1))
                else:
                    self.buyLimitOrder(self.getAmount(), self.getBidPrice())
                self.sellLimitOrder(self.getAmount(), round(self.getEntryPrice() * 1.003 , 1))
        elif self.getAmount() > self.tradeUnit:
            if self.sellOrderID == '' and self.buyOrderID == '':
                if self.getLastPrice() - self.candleAvg * 0.9 < self.getCurrentPrice():
                    self.buyLimitOrder(self.getAmount(), round(self.getLastPrice() - self.candleAvg * 0.9,1))
                else:
                    self.buyLimitOrder(self.getAmount(), self.getBidPrice())
                self.sellLimitOrder(self.getAmount() - self.tradeUnit, round(self.getEntryPrice(),1))



t = TradingBot()
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