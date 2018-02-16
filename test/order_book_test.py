import unittest
from graham_gdax.order_book import OrderBook, Order


class OrderBookTest(unittest.TestCase):
    def test_drop_message(self):
        msg = {'type': 'test'}
        order_book = OrderBook()
        order_book.process_message(msg)
        self.check_order_book_empty(order_book)

    def test_no_type(self):
        msg = {}
        order_book = OrderBook()
        order_book.process_message(msg)
        self.check_order_book_empty(order_book)

    def test_process_open(self):
        order_book, order_id, price, side = self.add_order_to_book()
        self.assertAlmostEqual(1.5, order_book.id_to_order[order_id].quantity, 3)
        self.assertAlmostEqual(1000.0, order_book.id_to_order[order_id].price, 3)
        self.assertEqual('buy', order_book.id_to_order[order_id].side)
        self.assertEqual({order_id}, order_book.side_level_order_ids[side][float(price)])

    def test_process_match(self):
        order_book, order_id, price, side = self.add_order_to_book()
        order = order_book.id_to_order[order_id]
        msg = {'type': 'match', 'order_id': order_id}
        order_book.process_message(msg)
        self.check_order_book_empty(order_book, order=order)

    def test_process_done(self):
        order_book, order_id, price, side = self.add_order_to_book()
        order = order_book.id_to_order[order_id]
        msg = {'type': 'done', 'order_id': order_id}
        order_book.process_message(msg)
        self.check_order_book_empty(order_book, order=order)

    def test_load_seed_book(self):
        mock_seed_book = {'bids': [["1000", "1", "a1b"], ["995", ".5", "b1b"], ["1010", ".4", "c1b"]],
                          'asks': [["2000", "1", "a1a"], ["2095", ".5", "b1a"], ["2010", ".4", "c1a"]]}
        order_book = OrderBook(seed_book=mock_seed_book)
        expected_ids_to_order = {'a1b': Order('buy', "1", "1000"), 'b1b': Order('buy', ".5", "995"),
                                 'c1b': Order('buy', ".4", "1010"), 'a1a': Order('sell', "1", "2000"),
                                 'b1a': Order('sell', ".5", "2095"), 'c1a': Order('sell', ".4", "2010")}
        expected_side_level_order = {'buy': {1000: {'a1b'}, 995: {'b1b'}, 1010: {'c1b'}},
                                     'sell': {2000: {'a1a'}, 2095: {'b1a'}, 2010: {'c1a'}}}
        for order_id, order in expected_ids_to_order.iteritems():
            self.assertEqual(order_book.id_to_order[order_id].quantity, order.quantity)
            self.assertEqual(order_book.id_to_order[order_id].price, order.price)
            self.assertEqual(order_book.id_to_order[order_id].side, order.side)
        for side, price_to_id in expected_side_level_order.iteritems():
            for price, id_set in price_to_id.iteritems():
                self.assertEqual(order_book.side_level_order_ids[side][price], id_set)

    def test_crossing_wipeout(self):
        seed_book = {'bids': [["1000", "1", "a1b"], ["995", ".5", "b1b"], ["1010", ".4", "c1b"]],
                     'asks': [["2000", "1", "a1a"], ["2095", ".5", "b1a"], ["2010", ".4", "c1a"]]}
        order_book = OrderBook(seed_book=seed_book)
        order_id = 'a1e'
        price = '2030.0'
        quantity = '1.5'
        side = 'buy'
        order_book.process_message(
            {'order_id': order_id, 'price': price, 'size': quantity, 'side': side, 'type': 'open'})
        expected_sell = {'b1a': Order('sell', ".5", "2095"), 'a1e': Order(side, quantity, price)}
        expected_sell_level_order = {2095: {'b1a'}}
        for order_id, order in expected_sell.iteritems():
            self.assertEqual(order_book.id_to_order[order_id].quantity, order.quantity)
            self.assertEqual(order_book.id_to_order[order_id].price, order.price)
            self.assertEqual(order_book.id_to_order[order_id].side, order.side)
        for price, id_set in expected_sell_level_order.iteritems():
            self.assertEqual(order_book.side_level_order_ids['sell'][price], id_set)

    def test_remove_quantity_correct(self):
        mock_seed_book = {'bids': [["1000", "1", "a1b"], ["995", ".5", "b1b"], ["1010", ".4", "c1b"],
                                   ["1010", ".4", "d1b"]],
                          'asks': [["2000", "1", "a1a"], ["2095", ".5", "b1a"], ["2010", ".4", "c1a"],
                                   ["2010", "1", "e1a"]]}
        order_book = OrderBook(seed_book=mock_seed_book)
        expected_ids_to_order = {'a1b': Order('buy', "1", "1000"), 'b1b': Order('buy', ".5", "995"),
                                 'c1b': Order('buy', ".4", "1010"), 'a1a': Order('sell', "1", "2000"),
                                 'd1b': Order('buy', ".4", "1010"), 'e1a': Order('sell', "1", "2010"),
                                 'b1a': Order('sell', ".5", "2095"), 'c1a': Order('sell', ".4", "2010")}
        expected_side_level_order = {'buy': {1000: {'a1b'}, 995: {'b1b'}, 1010: {'c1b', 'd1b'}},
                                     'sell': {2000: {'a1a'}, 2095: {'b1a'}, 2010: {'c1a', 'e1a'}}}
        for order_id, order in expected_ids_to_order.iteritems():
            self.assertEqual(order_book.id_to_order[order_id].quantity, order.quantity)
            self.assertEqual(order_book.id_to_order[order_id].price, order.price)
            self.assertEqual(order_book.id_to_order[order_id].side, order.side)
        for side, price_to_id in expected_side_level_order.iteritems():
            for price, id_set in price_to_id.iteritems():
                self.assertEqual(order_book.side_level_order_ids[side][price], id_set)
        expected_order_book = {'sell': [(2000.0, 1.0), (2010.0, 1.4), (2095.0, 0.5)],
                               'buy': [(1010.0, 0.8), (1000.0, 1.0), (995.0, 0.5)]}
        for side, levels in order_book.last_book.iteritems():
            for i, level in enumerate(levels):
                self.assertEqual(expected_order_book[side][i], level)
        msg = {'type': 'match', 'order_id': 'e1a'}
        done_msg = {'type': 'done', 'order_id': 'd1b'}
        expected_ids_to_order = {'a1b': Order('buy', "1", "1000"), 'b1b': Order('buy', ".5", "995"),
                                 'c1b': Order('buy', ".4", "1010"), 'a1a': Order('sell', "1", "2000"),
                                 'b1a': Order('sell', ".5", "2095"), 'c1a': Order('sell', ".4", "2010")}
        expected_side_level_order = {'buy': {1000: {'a1b'}, 995: {'b1b'}, 1010: {'c1b'}},
                                     'sell': {2000: {'a1a'}, 2095: {'b1a'}, 2010: {'c1a'}}}
        order_book.process_message(msg)
        order_book.process_message(done_msg)
        expected_order_book = {'sell': [(2000.0, 1.0), (2010.0, .4), (2095.0, 0.5)],
                               'buy': [(1010.0, 0.4), (1000.0, 1.0), (995.0, 0.5)]}
        for order_id, order in expected_ids_to_order.iteritems():
            self.assertEqual(order_book.id_to_order[order_id].quantity, order.quantity)
            self.assertEqual(order_book.id_to_order[order_id].price, order.price)
            self.assertEqual(order_book.id_to_order[order_id].side, order.side)
        for side, price_to_id in expected_side_level_order.iteritems():
            for price, id_set in price_to_id.iteritems():
                self.assertEqual(order_book.side_level_order_ids[side][price], id_set)
        for side, levels in order_book.last_book.iteritems():
            for i, level in enumerate(levels):
                self.assertEqual(expected_order_book[side][i], level)

    def test_place_and_remove_order(self):
        mock_seed_book = {'bids': [["1000", "1", "a1b"], ["995", ".5", "b1b"], ["1010", ".4", "c1b"]],
                          'asks': [["2000", "1", "a1a"], ["2095", ".5", "b1a"], ["2010", ".4", "c1a"]]}
        order_book = OrderBook(seed_book=mock_seed_book)
        expected_ids_to_order = {'a1b': Order('buy', "1", "1000"), 'b1b': Order('buy', ".5", "995"),
                                 'c1b': Order('buy', ".4", "1010"), 'a1a': Order('sell', "1", "2000"),
                                 'b1a': Order('sell', ".5", "2095"), '111': Order('buy', '1', '1990')}
        expected_side_level_order = {'buy': {1000: {'a1b'}, 995: {'b1b'}, 1010: {'c1b'}, 1990: {'111'}},
                                     'sell': {2000: {'a1a'}, 2095: {'b1a'}, 2010: {'c1a'}}}
        order_id = '111'
        price = '1990'
        quantity = '1'
        side = 'buy'
        msg = {'order_id': order_id, 'price': price, 'size': quantity, 'side': side, 'type': 'open'}
        order_book.process_message(msg)
        expected_order_book = {'sell': [(2000.0, 1.0), (2010.0, .4), (2095.0, 0.5)],
                               'buy': [(1990, 1), (1010.0, 0.4), (1000.0, 1.0), (995.0, 0.5)]}
        for order_id, order in expected_ids_to_order.iteritems():
            self.assertEqual(order_book.id_to_order[order_id].quantity, order.quantity)
            self.assertEqual(order_book.id_to_order[order_id].price, order.price)
            self.assertEqual(order_book.id_to_order[order_id].side, order.side)
        for side, price_to_id in expected_side_level_order.iteritems():
            for price, id_set in price_to_id.iteritems():
                self.assertEqual(order_book.side_level_order_ids[side][price], id_set)
        for side, levels in order_book.last_book.iteritems():
            for i, level in enumerate(levels):
                self.assertEqual(expected_order_book[side][i], level)
        msg = {'type': 'match', 'order_id': '111'}
        order_book.process_message(msg)
        expected_order_book = {'sell': [(2000.0, 1.0), (2010.0, .4), (2095.0, 0.5)],
                               'buy': [(1010.0, 0.4), (1000.0, 1.0), (995.0, 0.5)]}
        for side, levels in order_book.last_book.iteritems():
            for i, level in enumerate(levels):
                self.assertEqual(expected_order_book[side][i], level)

    def add_order_to_book(self):
        order_id = 'a1e'
        price = '1000.0'
        quantity = '1.5'
        side = 'buy'
        msg = {'order_id': order_id, 'price': price, 'size': quantity, 'side': side, 'type': 'open'}
        order_book = OrderBook()
        order_book.process_message(msg)
        return order_book, order_id, price, side

    def check_order_book_empty(self, order_book, order=None):
        self.assertEqual(0, len(order_book.id_to_order))
        if order:
            self.assertEqual(0, len(order_book.side_level_order_ids[order.side][order.price]))


if __name__ == '__main__':
    unittest.main()
