import json
from typing import Any
from datamodel import Listing, Observation, Order, OrderDepth, ProsperityEncoder, Symbol, Trade, TradingState


class Logger:
    def __init__(self) -> None:
        self.logs = ""
        self.max_log_length = 3750

    def print(self, *objects: Any, sep: str = " ", end: str = "\n") -> None:
        self.logs += sep.join(map(str, objects)) + end

    def flush(self, state: TradingState, orders: dict[Symbol, list[Order]], conversions: int, trader_data: str) -> None:
        base_length = len(
            self.to_json([
                self.compress_state(state, ""),
                self.compress_orders(orders),
                conversions,
                "",
                "",
            ])
        )

        max_item_length = (self.max_log_length - base_length) // 3

        print(
            self.to_json([
                self.compress_state(state, self.truncate(state.traderData, max_item_length)),
                self.compress_orders(orders),
                conversions,
                self.truncate(trader_data, max_item_length),
                self.truncate(self.logs, max_item_length),
            ])
        )

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
            self.compress_observations(state.observations),
        ]

    def compress_listings(self, listings: dict[Symbol, Listing]) -> list[list[Any]]:
        return [[l.symbol, l.product, l.denomination] for l in listings.values()]

    def compress_order_depths(self, order_depths: dict[Symbol, OrderDepth]) -> dict[Symbol, list[Any]]:
        return {symbol: [depth.buy_orders, depth.sell_orders] for symbol, depth in order_depths.items()}


    def compress_trades(self, trades: dict[Symbol, list[Trade]]) -> list[list[Any]]:
        return [[t.symbol, t.price, t.quantity, t.buyer, t.seller, t.timestamp] for ts in trades.values() for t in ts]

    def compress_observations(self, obs: Observation) -> list[Any]:
        conv = {p: [o.bidPrice, o.askPrice, o.transportFees, o.exportTariff, o.importTariff, o.sugarPrice, o.sunlightIndex]
                for p, o in obs.conversionObservations.items()}
        return [obs.plainValueObservations, conv]

    def compress_orders(self, orders: dict[Symbol, list[Order]]) -> list[list[Any]]:
        return [[o.symbol, o.price, o.quantity] for os in orders.values() for o in os]

    def to_json(self, value: Any) -> str:
        return json.dumps(value, cls=ProsperityEncoder, separators=(",", ":"))

    def truncate(self, value: str, max_length: int) -> str:
        return value if len(value) <= max_length else value[:max_length - 3] + "..."


logger = Logger()


class Trader:
    def __init__(self):
        self.POSITION_LIMIT = 20

    def run(self, state: TradingState) -> tuple[dict[Symbol, list[Order]], int, str]:
        result = {}
        conversions = 0
        trader_data = ""

        for symbol, order_depth in state.order_depths.items():
            orders = []
            position = state.position.get(symbol, 0)
            buy_orders = order_depth.buy_orders
            sell_orders = order_depth.sell_orders

            if not buy_orders or not sell_orders:
                continue

            best_bid = max(buy_orders)
            best_ask = min(sell_orders)
            fair_price = (best_bid + best_ask) / 2
            spread = best_ask - best_bid

            logger.print(f"{symbol} | Fair={fair_price:.2f} Spread={spread:.2f} Pos={position}")

            # Buy if spread is decent and we aren't overexposed
            if spread > 1:
                if position < self.POSITION_LIMIT:
                    buy_qty = min(3, self.POSITION_LIMIT - position)
                    orders.append(Order(symbol, best_bid + 1, buy_qty))
                if position > -self.POSITION_LIMIT:
                    sell_qty = min(3, self.POSITION_LIMIT + position)
                    orders.append(Order(symbol, best_ask - 1, -sell_qty))

            if orders:
                result[symbol] = orders

        logger.flush(state, result, conversions, trader_data)
        return result, conversions, trader_data
