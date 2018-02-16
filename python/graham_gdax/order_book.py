from collections import defaultdict
import math


class OrderBook(object):
    def __init__(self, seed_book=None, book_depth=5):
        # I like this kind of function map cause it avoids a string of if statements to decide which function to call
        # based on the type
        self.function_dispatch_map = {'done': self._process_done, 'open': self._process_open,
                                      'match': self._process_match}
        # This is really just configurable for display purposes
        self.book_depth = book_depth
        # Basically these two maps left joined will give you everything about the current state of the book.
        # I need to keep id_to_order in order to find the order id that needs to be removed in "done" and "match" cases
        self.id_to_order = {}
        self.side_level_order_ids = defaultdict(lambda: defaultdict(set))
        # This will be used as a cache of the last book and only updated if I think the book changed
        self.last_book = {'buy': [], 'sell': []}
        if seed_book is not None:
            self.load_seed_book(seed_book)

    def load_seed_book(self, seed_book):
        for bid_ask in ['bids', 'asks']:
            side = 'buy' if bid_ask == 'bids' else 'sell'
            for raw_order in seed_book[bid_ask]:
                order = Order(side, raw_order[1], raw_order[0])
                order_id = raw_order[2]
                self.id_to_order[order_id] = order
                self.side_level_order_ids[side][order.price].add(order_id)
        self.rebuild_top_of_book()
        print "seed display"
        self.display_book()

    def process_message(self, msg):
        # This shouldn't happen but who knows. Can't trust exchanges
        if 'type' not in msg:
            print 'ERROR: Invalid message, type is not included in message'
            return
        msg_type = msg['type']
        if msg_type in self.function_dispatch_map:
            self.function_dispatch_map[msg_type](msg)
        else:
            pass
            # print 'Message type "{}" not necessary for maintaining book'.format(msg_type)

    def _process_open(self, msg):
        order = Order.from_msg(msg)
        # This check has to be done before the new order is processed. There is a potential race condition here
        # but I am kind of ignoring it for simplicities sake at the moment.
        self.check_valid_book(order)
        self.id_to_order[msg['order_id']] = order
        self.side_level_order_ids[order.side][order.price].add(msg['order_id'])

        # This if statement is designed to decide whether we need to rebuild the book based on the new order
        last_prices = [price for price, _ in self.last_book[order.side]]
        if len(last_prices) > 0 and ((order.side == 'buy' and order.price > min(last_prices)) or \
                                             (order.side == 'sell' and order.price < max(last_prices))):
            self.rebuild_top_of_book()
            self.display_book()

    # This is separate from process match though their logic is the same because I might want to keep fills
    def _process_done(self, msg):
        self.remove_order(msg)

    def _process_match(self, msg):
        self.remove_order(msg)

    def remove_order(self, msg):
        order_id = msg['order_id'] if 'order_id' in msg else msg['taker_order_id']
        # order_id could not be in the current order book if this started after the book was cleared
        if order_id in self.id_to_order:
            order = self.id_to_order.pop(order_id)
        else:
            return
        order_book_prices = {price for price, _ in self.last_book[order.side]}
        if order_id in self.side_level_order_ids[order.side][order.price]:
            self.side_level_order_ids[order.side][order.price].remove(order_id)
        if order.price in order_book_prices:
            self.rebuild_top_of_book()
            self.display_book()

    def check_valid_book(self, order):
        # So assigning lambdas is typically an anti-pattern but I think it makes sense as opposed to duplicating
        # any logic here
        crossed_side = 'buy' if order.side == 'sell' else 'sell'
        crossed_order_prices = [price for price in self.side_level_order_ids[crossed_side].keys()
                                if (order.side == 'buy' and order.price > price)
                                or (order.side == 'sell' and order.price < price)]
        # The logic here is find all crossed orders and then remove them from the book. The assumption is that if we
        # see a crossed order then we must have missed a match or something that took the top of the book.
        # Remove all crossed order_ids from the order book
        if len(crossed_order_prices) > 0:
            for price in crossed_order_prices:
                if price in self.side_level_order_ids[crossed_side]:
                    crossed_order_ids = self.side_level_order_ids[crossed_side].pop(price)
                    for crossed_order_id in crossed_order_ids:
                        del self.id_to_order[crossed_order_id]

    def rebuild_top_of_book(self):
        buy_book, sell_book = self.get_books()
        self.last_book['buy'] = buy_book
        self.last_book['sell'] = sell_book

    def get_books(self):
        buy_lines = self.get_book_top('buy')
        sell_lines = self.get_book_top('sell')
        return buy_lines, sell_lines

    def get_book_top(self, side):
        # top_prices = sorted([price for price, order_ids in self.side_level_order_ids[side].iteritems()
        #                      if len(order_ids) > 0], reverse=side == 'buy')[:self.book_depth]
        top_prices = sorted([price for price, order_ids in self.side_level_order_ids[side].iteritems()
                             if len(order_ids) > 0], reverse=side == 'buy')[:self.book_depth]
        return [(price, math.fsum((self.id_to_order[order_id].quantity
                                   for order_id in self.side_level_order_ids[side][price])))
                for price in top_prices]

    # For writing to stdout
    def display_book(self):
        buy_lines, sell_lines = self.get_books()
        self.print_book_tuples(sell_lines[::-1])
        print '-' * 21
        self.print_book_tuples(buy_lines)
        print '\n\n\n'

    # for writing to a file
    def write_book(self):
        buy_lines, sell_lines = self.get_books()
        with open('books.txt', 'a+') as fl:
            self.write_book_tuples(fl, sell_lines)
            fl.write('-' * 21 + '\n')
            self.write_book_tuples(fl, buy_lines)
            fl.write('\n\n\n')

    def print_book_tuples(self, book_tuples):
        for price, quantity in book_tuples:
            print '{} @ {}'.format(quantity, price)

    def write_book_tuples(self, fl, book_tuples):
        for price, quantity in book_tuples:
            fl.write('{} @ {}'.format(quantity, price))


# Basic Representation of an order
class Order(object):
    def __init__(self, side, quantity, price):
        self.side = side
        self.quantity = float(quantity)
        self.price = float(price)

    @classmethod
    def from_msg(cls, msg):
        size = msg['size'] if 'size' in msg else msg['remaining_size']
        return Order(msg['side'], size, msg['price'])
