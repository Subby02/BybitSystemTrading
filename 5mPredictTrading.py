import schedule
import time
import datetime
from pybit import HTTP


#1. 주문 취소 하고 다시 넣는 버그 고쳐야됨
#2. 손절 로직 짜야됨
#3. 1일봉으로 전봉 종가 위에 있을 경우 매수 진행 하도록 로직 짜야됨

class TradingBot:
    tradeUnit = 0.002
    notBuyRate = 0.999
    takeProfitRate = 1.005

    candleAvg = 0
    botState = 'Idle'
    buyOrderID = ''
    sellOrderID = ''

    api_key = ''
    api_secret = ''

    session = HTTP(
        endpoint="https://api.bybit.com",
        api_key=api_key,
        api_secret=api_secret
    )

    def getClosePrice(self):
        now = datetime.datetime.now()
        today = datetime.datetime(
            year=now.year,
            month=now.month,
            day=now.day,
            hour=now.hour,
            minute=int(now.minute / 5) * 5,
            second=0
        )
        delta = datetime.timedelta(minutes=-5 * 2)
        dt = today + delta
        from_time = time.mktime(dt.timetuple())

        result = self.session.query_kline(
            symbol="BTCUSDT",
            interval=5,
            limit=2,
            from_time=from_time
        )

        return result['result'][1]['close']

    def getEntryPrice(self):
        positions = self.session.my_position(
            symbol="BTCUSDT"
        )

        for position in positions['result']:
            if position["symbol"] == "BTCUSDT":
                return float(position['entry_price'])

    def getLastPrice(self):
        trades = self.session.user_trade_records(
            symbol="BTCUSDT"
        )

        for trade in trades['result']['data']:
            if trade['side'] == 'Buy':
                if trade['exec_type'] == 'Trade':
                    return trade['order_price']

    def getAmount(self):
        positions = self.session.my_position(
            symbol="BTCUSDT"
        )

        for position in positions['result']:
            if position["symbol"] == "BTCUSDT":
                return float(position['size'])

    def getBalance(self):
        balance = self.session.get_wallet_balance(coin="USDT")

        return balance['result']['USDT']['available_balance']

    def getLeverage(self):
        positions = self.session.my_position(
            symbol="BTCUSDT"
        )

        for position in positions['result']:
            if position["symbol"] == "BTCUSDT":
                return float(position['leverage'])

    def getOrderPrice(self,id):
        status = self.session.query_active_order(
            symbol="BTCUSDT",
            order_id=id
        )

        return status['result']['price']

    def getOrderSize(self,id):
        status = self.session.query_active_order(
            symbol="BTCUSDT",
            order_id=id
        )

        return status['result']['qty']

    def getOrderStatus(self,id):
        status = self.session.query_active_order(
            symbol="BTCUSDT",
            order_id=id
        )

        return status['result']['order_status']

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
        delta = datetime.timedelta(minutes=-5*6)
        dt = today + delta
        from_time = time.mktime(dt.timetuple())

        result = self.session.query_kline(
            symbol="BTCUSDT",
            interval=5,
            limit=6,
            from_time=from_time
        )

        sum = 0
        tickers = result['result']

        for ticker in tickers:
            sum += abs(ticker['open']-ticker['low'])

        self.candleAvg = int(sum/6/0.5)*0.5

        print('[', datetime.datetime.now(), '] 5m candle avg init | candleAvg :', self.candleAvg )

        if self.buyOrderID != '':
            self.cancelOrder(self.buyOrderID)

        if self.getAmount() == 0:
            self.buyLimitOrder(self.tradeUnit, tickers[-1]['close'] - self.candleAvg)
            self.botState = '1PosActive'
        else:
            if self.getEntryPrice()*self.notBuyRate > tickers[-1]['close'] - self.candleAvg:
                self.buyLimitOrder(self.getAmount(), tickers[-1]['close'] - self.candleAvg)

    def buyLimitOrder(self, size, price):
        if self.getBalance() > float(size) * float(price) / float(self.getLeverage()):
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

            print('[', datetime.datetime.now(), '] limit buy order | size :', size, '| price :', price, '| id :',
                  order['result']['order_id'])
        else:
            print('[', datetime.datetime.now(), '] cancel due to lack of balance')

    def sellLimitOrder(self, size, price):
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

        print('[', datetime.datetime.now(), '] limit sell order | size :', size, '| price :', price, '| id :',
              order['result']['order_id'])

    def cancelAllOrder(self):
        self.session.cancel_all_active_orders(
            symbol="BTCUSDT"
        )

        print('[', datetime.datetime.now(), '] all order cancel')

    def cancelOrder(self, id):
        if self.getOrderStatus(id) == 'New':
            self.session.cancel_active_order(
                symbol="BTCUSDT",
                order_id=id
            )

            print('[', datetime.datetime.now(), ']', id, 'order cancel')

    def checkOrder(self):
        if self.botState == '1PosActive':
            if self.buyOrderID != '':
                if self.getOrderStatus(self.buyOrderID) == 'Filled':
                    self.botState = '1PosFilled'
                    print('[', datetime.datetime.now(), '] botState :', self.botState)

                    price = int(self.getEntryPrice() * self.takeProfitRate / 0.5) * 0.5
                    self.sellLimitOrder(self.getAmount(), price)
                    self.buyOrderID = ''
        elif self.botState == '1PosFilled':
            if self.sellOrderID != '':
                if self.getOrderStatus(self.sellOrderID) == 'Filled':
                    self.botState = 'Idle'
                    print('[', datetime.datetime.now(), '] botState :', self.botState)
                    if self.buyOrderID != '':
                        if self.getOrderStatus(self.buyOrderID) == 'New':
                            self.cancelOrder(self.buyOrderID)

                    self.buyLimitOrder(self.tradeUnit, self.getClosePrice() - self.candleAvg)
                    self.sellOrderID = ''
            if self.buyOrderID != '':
                if self.getOrderStatus(self.buyOrderID) == 'Filled':
                    self.botState = '2+PosFilled'
                    print('[', datetime.datetime.now(), '] botState :', self.botState)
                    self.cancelOrder(self.sellOrderID)
                    entryPrice = int(self.getEntryPrice() / 0.5) * 0.5
                    self.sellLimitOrder(self.getAmount() - self.tradeUnit, entryPrice)
                    self.buyOrderID = ''
        elif self.botState == '2+PosFilled':
            if self.sellOrderID != '':
                if self.getOrderStatus(self.sellOrderID) == 'Filled':
                    self.botState = '1PosFilled'
                    print('[', datetime.datetime.now(), '] botState :', self.botState)

                    price = int(self.getEntryPrice() * self.takeProfitRate / 0.5) * 0.5
                    self.sellLimitOrder(self.getAmount(), price)
                    if self.buyOrderID != '':
                        if self.getOrderStatus(self.buyOrderID) == 'New':
                            self.cancelOrder(self.buyOrderID)

                    if self.getEntryPrice() * self.notBuyRate > self.getClosePrice() - self.candleAvg:
                        self.buyLimitOrder(self.getAmount(), self.getClosePrice() - self.candleAvg)
            if self.buyOrderID != '':
                if self.getOrderStatus(self.buyOrderID) == 'Filled':
                    self.cancelOrder(self.sellOrderID)
                    entryPrice = int(self.getEntryPrice() / 0.5) * 0.5
                    self.sellLimitOrder(self.getAmount() - self.tradeUnit, entryPrice)
                    self.buyOrderID = ''

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
