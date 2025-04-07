import json
from collections import deque
from typing import Any

from datamodel import Listing, Observation, Order, OrderDepth, ProsperityEncoder, Symbol, Trade, TradingState


class Logger:
    def __init__(self) -> None:
        self.logs = ""
        self.max_log_length = 3750

    def print(self, *objects: Any, sep: str = " ", end: str = "\n") -> None:
        self.logs += sep.join(map(str, objects)) + end

    def flush(self, state: TradingState, orders: dict[Symbol, list[Order]], conversions: int, trader_data: str) -> None:
        base_length = len(self.to_json([
            self.compress_state(state, ""),
            self.compress_orders(orders),
            conversions,
            "",
            ""
        ]))
        max_item_length = (self.max_log_length - base_length) // 3

        print(self.to_json([
            self.compress_state(state, self.truncate(state.traderData, max_item_length)),
            self.compress_orders(orders),
            conversions,
            self.truncate(trader_data, max_item_length),
            self.truncate(self.logs, max_item_length)
        ]))
        self.logs = ""

    def compress_state(self, state: TradingState, trader_data: str) -> list[Any]:
        return [
            state.timestamp,
            trader_data,
            self.compress_listings(state.listings),
            self.compress_order_depths(state.order_depths),
            self.compress_trades(state.own_trades),
            self.compress_trades(state.market_trades),
            state.position,
            self.compress_observations(state.observations)
        ]

    def compress_listings(self, listings: dict[Symbol, Listing]) -> list[list[Any]]:
        return [[l.symbol, l.product, l.denomination] for l in listings.values()]

    def compress_order_depths(self, order_depths: dict[Symbol, OrderDepth]) -> dict[Symbol, list[Any]]:
        return {symbol: [depth.buy_orders, depth.sell_orders] for symbol, depth in order_depths.items()}

    def compress_trades(self, trades: dict[Symbol, list[Trade]]) -> list[list[Any]]:
        return [[t.symbol, t.price, t.quantity, t.buyer, t.seller, t.timestamp] for ts in trades.values() for t in ts]

    def compress_observations(self, obs: Observation) -> list[Any]:
        conv = {
            p: [
                o.bidPrice, o.askPrice, o.transportFees,
                o.exportTariff, o.importTariff, o.sugarPrice, o.sunlightIndex
            ]
            for p, o in obs.conversionObservations.items()
        }
        return [obs.plainValueObservations, conv]

    def compress_orders(self, orders: dict[Symbol, list[Order]]) -> list[list[Any]]:
        return [[o.symbol, o.price, o.quantity] for os in orders.values() for o in os]

    def to_json(self, value: Any) -> str:
        return json.dumps(value, cls=ProsperityEncoder, separators=(",", ":"))

    def truncate(self, value: str, max_length: int) -> str:
        return value if len(value) <= max_length else value[:max_length - 3] + "..."


logger = Logger()


class Trader:
    POSITION_LIMIT = 20

    def __init__(self):
        self.kelp_mid_prices = deque(maxlen=50)
        self.last_resin_order_prices = set()

    def run(self, state: TradingState) -> tuple[dict[Symbol, list[Order]], int, str]:
        result = {}
        conversions = 0
        trader_data = ""
        position = state.position.copy()
        self.last_resin_order_prices.clear()

        for symbol, depth in state.order_depths.items():
            if not depth.buy_orders or not depth.sell_orders:
                continue

            orders = []
            best_bid = max(depth.buy_orders)
            best_ask = min(depth.sell_orders)
            mid_price = (best_bid + best_ask) / 2
            spread = best_ask - best_bid
            pos = position.get(symbol, 0)

            logger.print(f"{symbol} | Fair={mid_price:.2f} Spread={spread:.2f} Pos={pos}")

            # === KELP ===
            if symbol == "KELP":
                self.kelp_mid_prices.append(mid_price)

                if state.timestamp > 950_000:
                    if pos > 0:
                        orders.append(Order(symbol, best_ask, -pos))
                    elif pos < 0:
                        orders.append(Order(symbol, best_bid, -pos))
                elif len(self.kelp_mid_prices) >= 10:
                    avg = sum(self.kelp_mid_prices) / len(self.kelp_mid_prices)
                    delta = mid_price - avg

                    if delta < -4 and pos < self.POSITION_LIMIT:
                        orders.append(Order(symbol, best_bid + 1, min(5, self.POSITION_LIMIT - pos)))
                    elif delta > 4 and pos > -self.POSITION_LIMIT:
                        orders.append(Order(symbol, best_ask - 1, -min(5, self.POSITION_LIMIT + pos)))

                    if pos > 15:
                        orders.append(Order(symbol, best_ask - 3, -5))
                    elif pos < -15:
                        orders.append(Order(symbol, best_bid + 3, 5))

            # === RAINFOREST_RESIN ===
            elif symbol == "RAINFOREST_RESIN":
                if state.timestamp > 950_000:
                    if pos > 0:
                        orders.append(Order(symbol, best_ask, -pos))
                    elif pos < 0:
                        orders.append(Order(symbol, best_bid, -pos))
                else:
                    # Adaptive bands based on spread
                    if spread >= 10:
                        buy_levels = [9995, 9996]
                        sell_levels = [10004, 10005]
                        size = 8
                    elif spread >= 6:
                        buy_levels = [9996, 9997]
                        sell_levels = [10003, 10004]
                        size = 5
                    else:
                        buy_levels = [9998]
                        sell_levels = [10002]
                        size = 3

                    for price in buy_levels:
                        if pos < self.POSITION_LIMIT and price not in self.last_resin_order_prices:
                            qty = min(size, self.POSITION_LIMIT - pos)
                            orders.append(Order(symbol, price, qty))
                            self.last_resin_order_prices.add(price)
                            pos += qty

                    for price in sell_levels:
                        if pos > -self.POSITION_LIMIT and price not in self.last_resin_order_prices:
                            qty = min(size, self.POSITION_LIMIT + pos)
                            orders.append(Order(symbol, price, -qty))
                            self.last_resin_order_prices.add(price)
                            pos -= qty

            if orders:
                result[symbol] = orders

        logger.flush(state, result, conversions, trader_data)
        return result, conversions, trader_data
