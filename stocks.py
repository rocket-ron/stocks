from flask import Flask, jsonify, url_for, make_response
from flask_restful import Resource, Api, reqparse, fields, marshal, abort
from operator import itemgetter
import unittest
import json


"""


POST     http://localhost:5000/buy     Put a bid order for stock
POST     http://localhost:5000/sell    Put a sell order for stock
GET     http://localhost:5000/status/:ordernum              Get the status of an order
GET     http://localhost:5000/info/:symbol                  Get the last transaction for stock


Bid response structure:

{ "symbol": symbol,
  "shares": shares,
  "bid":    bid,
  "ordernum" : ordernum,
  "uri": url
}

Sell response structure:

{ "symbol": symbol,
  "shares": shares,
  "ask":    ask,
  "ordernum" : ordernum,
  "uri": url
}

Status response:

{
    "orderType":    ordertype,
    "orderSymbol":  ordersymbol,
    "orderShares":  ordershares,
    "orderBidAsk":  price,
    "orderStatus":  status,
    "orderClearPrice":  orderClearPrice
}

Stock Transaction response:

{
    "symbol": symbol,
    "averagePrice": averagePrice,
    "sharesPrice" : {
        [
            "shares": shares,
            "price": price
        ]
    }


"""

class StockExchange:

    exchange = {}
    transactions = []

    def __init__(self):
        self.exchange = {'GOOG': {'price': 100.00, 'average': 101.50},
                    'MSFT': {'price': 50.00, 'average': 49.75},
                    'IBM':  {'price': 45.00, 'average': 45.02}}

        self.transactions = []

    def buy(self, symbol, shares, bid):
        transaction = {
            'ordernum': self.get_next_order_number(),
            'symbol'    : symbol.upper(),
            'shares'    : shares,
            'bidask'    : bid,
            'operation' : 'buy',
            'status'    : 'PENDING'
        }
        self.transactions.append(transaction)
        return transaction['ordernum']

    def buy2(self, symbol, shares, bid):
        transaction = {
            'ordernum': self.get_next_order_number(),
            'symbol'    : symbol.upper(),
            'shares'    : shares,
            'bidask'    : bid,
            'operation' : 'buy',
            'status'    : 'PENDING',
            'executions': []
        }

        # find outstanding sell transactions for this symbol that the ask is less than
        # or equal to the bid price
        sell_transactions = [tx for tx in self.transactions if
                             tx['operation'] == 'sell' and tx['symbol'] == symbol.upper()
                             and tx['bidask'] <= bid] and tx['status'] == 'PENDING'

        # sort descending by ask price
        sells_by_ask = sorted(sell_transactions, key=itemgetter('bidask'), reverse=True)

        processed_shares = shares
        highest_ask = 0.0

        for ask in sells_by_ask:
            if ask['bidask'] > highest_ask:
                highest_ask = ask['bidask']
            if ask['shares'] <= processed_shares:
                ask['status'] = 'EXECUTED'
                ask['executions'].append({'buyerOrderNum': transaction['ordernum'],
                                          'price': ask['bidask'],
                                          'qty': ask['shares']})
                transaction['executions'].append({'sellerOrderNum': ask['ordernum'],
                                                  'price': highest_ask,
                                                  'qty': ask['shares']})
            else:
                ask['shares'] -= processed_shares
                ask['executions'].append({'buyerOrderNum': transaction['ordernum'],
                                                  'price': highest_ask,
                                                  'qty': shares})
                transaction['executions'].append({'sellerOrderNum': ask['ordernum'],
                                                  'price': highest_ask,
                                                  'qty': shares})
                transaction['status'] = 'EXECUTED'
                break
        self.transactions.append(transaction)


    def sell(self, symbol, shares, ask):
        transaction = {
            'ordernum': self.get_next_order_number(),
            'symbol'    : symbol.upper(),
            'shares'    : shares,
            'bidask'    : ask,
            'operation' : 'sell',
            'status'    : 'PENDING'
        }
        self.transactions.append(transaction)
        return transaction['ordernum']

    def sell2(self, symbol, shares, ask):
        transaction = {
            'ordernum': self.get_next_order_number(),
            'symbol'    : symbol.upper(),
            'shares'    : shares,
            'bidask'    : ask,
            'operation' : 'sell',
            'status'    : 'PENDING',
            'executions': []
        }

        # find outstanding buy transactions for this symbol that the buy is greater than
        # or equal to the ask price
        buy_transactions = [tx for tx in self.transactions if
                             tx['operation'] == 'buy' and tx['symbol'] == symbol.upper()
                             and tx['bidask'] >= ask] and tx['status'] == 'PENDING'

        # sort ascending by bid price
        buys_by_ask = sorted(buy_transactions, key=itemgetter('bidask'))


        for buy in buys_by_ask:
            if buy['shares'] <= shares:
                buy['status'] = 'EXECUTED'
                buy['executions'].append({'sellerOrderNum': transaction['ordernum'],
                                          'price': ask,
                                          'qty': buy['shares']})
                transaction['executions'].append({'buyerOrderNum': buy['ordernum'],
                                                  'price': ask,
                                                  'qty': buy['shares']})
            else:
                transaction['executions'].append({'buyerOrderNum': buy['ordernum'],
                                                  'price': ask,
                                                  'qty': shares})
                transaction['status'] = 'EXECUTED'
                buy['shares'] -= shares
                buy['executions'].append({'sellerOrderNum': transaction['ordernum'],
                                          'price': ask,
                                          'qty': buy['shares']})

        self.transactions.append(transaction)
        return transaction['ordernum']

    def info(self, symbol):
        if symbol.upper() in self.exchange:
            average_price = self.exchange[symbol.upper()]['average']
        else:
            return 'TICKER NOT FOUND'

        # lookup transactions for this stock symbol
        transaction = [tx for tx in self.transactions if tx['symbol'] == symbol.upper()]
        if len(transaction) > 0:
            return {
                'symbol':   symbol.upper(),
                'avgPrice': average_price,
                'transactions': [{'shares' : tx['shares'], 'price': tx['bidask']} for tx in transaction]
            }
        else:
            return 'NO TRANSACTIONS'

    def status(self, ordernum):
        transaction = [tx for tx in self.transactions if tx['ordernum'] == ordernum]
        if len(transaction) == 0:
            return None
        else:
            return transaction[0]

    def get_next_order_number(self):
        if len(self.transactions) > 0:
            ordernum = self.transactions[-1]['ordernum'] + 1
        else:
            ordernum = 1
        return ordernum

app = Flask(__name__)
api = Api(app)
stockExchange = StockExchange()


buy_fields = {
    'ordernum': fields.String,
    'uri': fields.Url('buy')
}


class StockBuy(Resource):
    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument('symbol', location='json',
                                   required=True, help='Stock symbol is required')
        self.reqparse.add_argument('shares', location='json',
                                   required=True, help='Number of shares is required')
        self.reqparse.add_argument('bid', type=float, location='json',
                                   required=True, help='Bid amount is required')
        super(StockBuy, self).__init__()

    def make_error(self, status_code,  message):
        response = jsonify({
            'status': status_code,
            'message': message
        })
        response.status_code = status_code
        return response

    def post(self):
        args = self.reqparse.parse_args()
        try:
            ordernum = stockExchange.buy(args['symbol'], args['shares'], args['bid'])
        except:
            return self.make_error(500, "ORDER FAILED")

        return jsonify({ "ordernum": ordernum,
                         "uri": url_for('status', ordernum=ordernum, _external=False)
                    })


class StockSell(Resource):
    def __init__(self):
        self.reqparse = reqparse.RequestParser()
        self.reqparse.add_argument('symbol', location='json',
                                   required=True, help='Stock symbol is required')
        self.reqparse.add_argument('shares', location='json',
                                   required=True, help='Number of shares is required')
        self.reqparse.add_argument('ask', type=float, location='json',
                                   required=True, help='Ask amount is required')
        super(StockSell, self).__init__()

    def post(self):
        args = self.reqparse.parse_args()
        ordernum = stockExchange.sell(args['symbol'], args['shares'], args['ask'])
        order = {
            'ordernum': ordernum
        }
        return jsonify({"ordernum": ordernum,
                        "uri": url_for('status', ordernum=ordernum, _external=False)
                        })

class OrderStatus(Resource):
    def get(self, ordernum):
        print type(ordernum)
        status = stockExchange.status(ordernum)
        if not status:
            abort(404)
        else:
            return jsonify({"ordernum": ordernum,
                            "OrderType": status['operation'].upper(),
                            "OrderSymbol": status['symbol'].upper(),
                            "OrderShares": status['shares'],
                            "OrderBidOrAsk": status['bidask'],
                            "OrderStatus": status['status'],
                            "uri": url_for('status', ordernum=ordernum, _external=False)
                        })


class StockInfo(Resource):
    def make_error(self, status_code,  message):
        response = jsonify({
            'status': status_code,
            'message': message
        })
        response.status_code = status_code
        return response

    def get(self, symbol):
        status = stockExchange.info(symbol)
        if type(status) == str:
            return self.make_error(404, status)
        else:
            return jsonify(status)


api.add_resource(StockBuy, '/buy', endpoint='buy')
api.add_resource(StockSell, '/sell', endpoint='sell')
api.add_resource(OrderStatus, '/status/<int:ordernum>', endpoint='status')
api.add_resource(StockInfo, '/info/<symbol>', endpoint='info')


#if __name__ == '__main__':
#    app.run(debug=True)


"""

Unit tests

"""


class StockBuyTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        pass

    @classmethod
    def tearDownClass(cls):
        pass

    def setUp(self):
        # creates a Flask test client
        self.app = app.test_client()
        # propagate the exceptions to the test client
        self.app.testing = True

    def tearDown(self):
        pass

    def test_buy(self):
        # construct a buy request JSON object
        buy = {"symbol": "GOOG", "shares": 10, "bid": 10.0}
        buy_json = json.dumps(buy)
        # sends HTTP POST request for the buy happy path
        result = self.app.post('/buy', data=buy_json, content_type='application/json')
        response = json.loads(result.data)
        self.assertIn("ordernum", response, "Missing ordernum in response")
        self.assertEqual(result.status_code, 200)

    def test_buy_parameter(self):
        # construct a buy request JSON object
        buy = {"stock": "GOOG", "shares": 10, "bid": 10.0}
        buy_json = json.dumps(buy)
        # sends HTTP POST request for the buy happy path
        result = self.app.post('/buy', data=buy_json, content_type='application/json')

        self.assertEqual(result.status_code, 400)

    def test_buy_no_json(self):
        # construct a buy request JSON object
        buy_json = ""
        # sends HTTP POST request for the buy happy path
        result = self.app.post('/buy', data=buy_json, content_type='application/json')

        self.assertEqual(result.status_code, 400)

#    def test_post_list(self):
#        # sends HTTP POST request for the task list
#        task = {'title': 'Test task', 'description': 'write more unit tests'}
#        task_str = json.dumps(task)
#        result = self.app.post('/buy', data=task_str, content_type='application/json')
#        self.assertEqual(result.status_code, 201)


class StockSellTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        pass

    @classmethod
    def tearDownClass(cls):
        pass

    def setUp(self):
        # creates a Flask test client
        self.app = app.test_client()
        # propagate the exceptions to the test client
        self.app.testing = True

    def tearDown(self):
        pass

    def test_sell(self):
        # construct a buy request JSON object
        buy = {"symbol": "GOOG", "shares": 10, "ask": 10.0}
        buy_json = json.dumps(buy)
        # sends HTTP POST request for the buy happy path
        result = self.app.post('/sell', data=buy_json, content_type='application/json')

        self.assertEqual(result.status_code, 200)

    def test_sell_parameter(self):
        # construct a buy request JSON object
        buy = {"stock": "GOOG", "shares": 10, "bid": 10.0}
        buy_json = json.dumps(buy)
        # sends HTTP POST request for the buy happy path
        result = self.app.post('/sell', data=buy_json, content_type='application/json')

        self.assertEqual(result.status_code, 400)

    def test_sell_no_json(self):
        # construct a buy request JSON object
        buy_json = ""
        # sends HTTP POST request for the buy happy path
        result = self.app.post('/sell', data=buy_json, content_type='application/json')

        self.assertEqual(result.status_code, 400)

class StatusTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        pass

    @classmethod
    def tearDownClass(cls):
        pass

    def setUp(self):
        # creates a Flask test client
        self.app = app.test_client()
        # propagate the exceptions to the test client
        self.app.testing = True

    def tearDown(self):
        pass

    def test_status_noordernum(self):
        result = self.app.get('/status/1000')
        self.assertEqual(result.status_code )

    def test_status_withordernum(self):
        # construct a buy request JSON object
        buy = {"symbol": "GOOG", "shares": 10, "bid": 10.0}
        buy_json = json.dumps(buy)
        # sends HTTP POST request so there is at least 1 transaction
        self.app.post('/buy', data=buy_json, content_type='application/json')
        result = self.app.get('/status/1')
        self.assertEqual(result.status_code, 200)


class BasicRestTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        pass

    @classmethod
    def tearDownClass(cls):
        pass

    def setUp(self):
        # creates a Flask test client
        self.app = app.test_client()
        # propagate the exceptions to the test client
        self.app.testing = True

    def tearDown(self):
        pass

    def test_root_status_code(self):
        # sends HTTP GET request to the '/'
        result = self.app.get('/')

        # assert the status code of the response
        self.assertEqual(result.status_code, 404)

if __name__ == '__main__':
    unittest.main()