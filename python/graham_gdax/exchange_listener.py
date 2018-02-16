#!/usr/bin/python

from gdax import WebsocketClient, PublicClient
from order_book import OrderBook


# I want this class to contain all of the gdax dependency so theoretically the OrderBook could be reused for another
# exchange. I think the Order object could provide the cross exchange abstraction.
class ExchangeListener(WebsocketClient):

    def __init__(self):
        super(ExchangeListener, self).__init__()
        # So I don't love having the public client call here but it seems like a reasonable place to init the book
        # using the level 3 feed to seed the order book
        public_client = PublicClient()
        seed_book = public_client.get_product_order_book('BTC-USD', level=3)
        self.order_book = OrderBook(seed_book=seed_book)

    def on_message(self, msg):
        self.order_book.process_message(msg)

if __name__ == '__main__':
    wsc = ExchangeListener()
    wsc.start()


