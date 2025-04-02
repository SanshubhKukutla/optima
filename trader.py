from datamodel import Order, OrderDepth, TradingState
from typing import List, Dict
from collections import deque
import jsonpickle

HISTORY_LENGTH = 20
POSITION_LIMITS = {
    "KELP": 20,
    "RAINFOREST_RESIN": 20
}

class Trader:
    def run(self, state: TradingState) -> tuple[Dict[str, List[Order]], int, str]:
        result = {}
        conversions = 0

        # Load or initialize trader state
        if state.traderData:
            memory = jsonpickle.decode(state.traderData)
        else:
            memory = {}

        for product, order_depth in state.order_depths.items():
            orders: List[Order] = []
            bids = order_depth.buy_orders
            asks = order_depth.sell_orders

            if product not in memory:
                memory[product] = {
                    "recent_prices": deque(maxlen=HISTORY_LENGTH),
                    "cash": 0,
                    "inventory": 0,
                    "pnl": 0
                }

            # Fair price using trade average + book midpoint
            best_bid = max(bids.keys()) if bids else None
            best_ask = min(asks.keys()) if asks else None
            book_fair = (best_bid + best_ask) / 2 if best_bid and best_ask else (100 if product == "KELP" else 10)

            for trade in state.market_trades.get(product, []):
                memory[product]["recent_prices"].append(trade.price)

            recent = memory[product]["recent_prices"]
            avg_trade_price = sum(recent) / len(recent) if recent else book_fair
            fair_price = (book_fair + avg_trade_price) / 2

            position = state.position.get(product, 0)
            inv = memory[product]["inventory"]
            cash = memory[product]["cash"]

            spread = (best_ask - best_bid) if best_bid and best_ask else 1
            buy_edge = fair_price - 1
            sell_edge = fair_price + 1

            # BUY below fair value if we have inventory room
            for ask_price, ask_volume in sorted(asks.items()):
                if ask_price <= buy_edge:
                    volume = min(-ask_volume, POSITION_LIMITS[product] - position)
                    if volume > 0:
                        orders.append(Order(product, ask_price, volume))
                        memory[product]["cash"] -= ask_price * volume
                        memory[product]["inventory"] += volume
                        print(f"BUY {volume}@{ask_price} [{product}]")

            # SELL above fair value if we have inventory
            for bid_price, bid_volume in sorted(bids.items(), reverse=True):
                if bid_price >= sell_edge:
                    volume = min(bid_volume, position + POSITION_LIMITS[product])
                    if volume > 0:
                        orders.append(Order(product, bid_price, -volume))
                        memory[product]["cash"] += bid_price * volume
                        memory[product]["inventory"] -= volume
                        print(f"SELL {volume}@{bid_price} [{product}]")

            # Log final values
            est_val = memory[product]["inventory"] * fair_price + memory[product]["cash"]
            print(f"{product}: Inv={memory[product]['inventory']}, Cash={memory[product]['cash']:.2f}, Fair={fair_price:.2f}, Val={est_val:.2f}")
            result[product] = orders

        # Final summary log
        print("\n===== FINAL SHELL SUMMARY =====")
        total = 0
        for product in memory:
            inv = memory[product]["inventory"]
            cash = memory[product]["cash"]
            fair = sum(memory[product]["recent_prices"]) / len(memory[product]["recent_prices"]) if memory[product]["recent_prices"] else 0
            total_val = inv * fair + cash
            print(f"{product}: Cash={cash:.2f}, Inv={inv}, Fair={fair:.2f}, Total={total_val:.2f}")
            total += total_val
        print(f"TOTAL SHELL VALUE: {total:.2f}")

        return result, conversions, jsonpickle.encode(memory)