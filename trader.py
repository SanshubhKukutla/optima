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

        # Deserialize traderData
        if state.traderData:
            memory = jsonpickle.decode(state.traderData)
        else:
            memory = {}

        total_value = 0

        for product, order_depth in state.order_depths.items():
            orders: List[Order] = []
            bids = order_depth.buy_orders
            asks = order_depth.sell_orders

            if product not in memory:
                memory[product] = {
                    "recent_prices": deque(maxlen=HISTORY_LENGTH),
                    "cash": 0,
                    "inventory": 0
                }

            best_bid = max(bids.keys()) if bids else None
            best_ask = min(asks.keys()) if asks else None
            book_fair = (best_bid + best_ask) / 2 if best_bid and best_ask else (100 if product == "KELP" else 10)

            for trade in state.market_trades.get(product, []):
                memory[product]["recent_prices"].append(trade.price)

            trade_prices = memory[product]["recent_prices"]
            if trade_prices:
                avg_trade_price = sum(trade_prices) / len(trade_prices)
                fair_price = (book_fair + avg_trade_price) / 2
            else:
                fair_price = book_fair

            print(f"\nTimestamp: {state.timestamp}")
            print(f"{product} | Fair: {fair_price:.2f}, Book Fair: {book_fair:.2f}, Avg Trade: {avg_trade_price if trade_prices else 'N/A'}")
            print(f"Buy Orders: {bids}")
            print(f"Sell Orders: {asks}")

            current_position = state.position.get(product, 0)
            position_limit = POSITION_LIMITS[product]
            inventory = memory[product]["inventory"]
            cash = memory[product]["cash"]

            spread = (best_ask - best_bid) if best_ask and best_bid else 100
            buy_threshold = 0.5 if spread < 5 else 1
            sell_threshold = 0.5 if spread < 5 else 1

            for ask_price, ask_volume in sorted(asks.items()):
                if ask_price < fair_price - buy_threshold:
                    volume = min(-ask_volume, position_limit - current_position)
                    if volume > 0:
                        orders.append(Order(product, ask_price, volume))
                        memory[product]["cash"] -= ask_price * volume
                        memory[product]["inventory"] += volume
                        current_position += volume
                        print(f"Placing BUY: {volume}x @ {ask_price}")

            for bid_price, bid_volume in sorted(bids.items(), reverse=True):
                if bid_price > fair_price + sell_threshold:
                    volume = min(bid_volume, current_position + position_limit)
                    if volume > 0:
                        orders.append(Order(product, bid_price, -volume))
                        memory[product]["cash"] += bid_price * volume
                        memory[product]["inventory"] -= volume
                        current_position -= volume
                        print(f"Placing SELL: {volume}x @ {bid_price}")

            inv = memory[product]["inventory"]
            cash = memory[product]["cash"]
            est_value = inv * fair_price + cash
            print(f"{product} | Inventory: {inv}, Cash: {cash:.2f}, Est. Value: {est_value:.2f}")

            total_value += est_value
            result[product] = orders

        print("\n===== FINAL SUMMARY =====")
        for product in memory:
            inv = memory[product]['inventory']
            cash = memory[product]['cash']
            est_fair = (sum(memory[product]['recent_prices']) / len(memory[product]['recent_prices'])) if memory[product]['recent_prices'] else 0
            value = inv * est_fair + cash
            print(f"{product}: Inventory = {inv}, Cash = {cash:.2f}, Est. Fair = {est_fair:.2f}, Total = {value:.2f}")
        print(f"TOTAL ESTIMATED SEASHELLS: {total_value:.2f}")

        return result, conversions, jsonpickle.encode(memory)