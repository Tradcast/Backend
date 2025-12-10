from game.data_preparation import random_token, spike_df_map
from collections import deque
import asyncio


class FuturesWallet:
    def __init__(self, token_selection='somi', leverage: int = 20, capital: float = 1000.0):
        self.leverage = leverage
        self.position_size = 100.0
        self.token_selection = token_selection

        self.capital = float(capital)  # starting capital (constant baseline)

        # balances:
        self.balance_free = float(capital)  # cash not reserved as margin
        self.balance_in_position = 0.0  # margin currently locked in positions
        self.balance_total = float(capital)  # equity (free + in_position + unrealized PnL)

        # position tracking
        self.long_positions = {'average_price': None, 'total_price': 0.0, 'num_pos': 0}
        self.short_positions = {'average_price': None, 'total_price': 0.0, 'num_pos': 0}
        self.direction = None  # "long" or "short" or None when no position

        # async lock for concurrent access from websocket tasks
        self._lock = asyncio.Lock()

        self.long_queue = []
        self.short_queue = []
        self.close_pos_queue = []

        def get_order_packet_send_time():
            ...

        self.binance_packet_sending_time = get_order_packet_send_time()

    # small helper to clear positions without touching balances
    async def _clear_positions(self):
        self.balance_in_position = 0.0
        self.long_positions = {'average_price': None, 'total_price': 0.0, 'num_pos': 0}
        self.short_positions = {'average_price': None, 'total_price': 0.0, 'num_pos': 0}
        self.direction = None

    async def get_wallet_state(self):
        async with self._lock:
            total_profit = (self.balance_total - self.capital) / self.capital
            return {
                "balance_total": self.balance_total,
                "total_profit": total_profit,
                "balance_free": self.balance_free,
                "in_position": self.balance_in_position,
                "long_average": self.long_positions['average_price'],
                "short_average": self.short_positions['average_price'],
                "direction": self.direction
            }

    # open a long (returns True if opened)
    async def add_long(self, index) -> bool:
        async with self._lock:
            if self.short_positions['num_pos'] > 0:
                return False
            if self.balance_free < self.position_size:
                return False
            price = float(spike_df_map[self.token_selection]['close'].iloc[index])
            self.long_positions['total_price'] += price
            self.long_positions['num_pos'] += 1
            self.long_positions['average_price'] = (self.long_positions['total_price'] /
                                                    self.long_positions['num_pos'])

            self.direction = "long"
            self.balance_in_position += self.position_size
            self.balance_free -= self.position_size
            # update total equity after opening (no unrealized PnL yet)
            self.balance_total = self.balance_free + self.balance_in_position
            return True

    async def add_short(self, index) -> bool:
        async with self._lock:
            if self.long_positions['num_pos'] > 0:
                return False
            if self.balance_free < self.position_size:
                return False
            price = float(spike_df_map[self.token_selection]['close'].iloc[index])
            self.short_positions['total_price'] += price
            self.short_positions['num_pos'] += 1
            self.short_positions['average_price'] = (self.short_positions['total_price'] /
                                                     self.short_positions['num_pos'])

            self.direction = "short"
            self.balance_in_position += self.position_size
            self.balance_free -= self.position_size
            self.balance_total = self.balance_free + self.balance_in_position
            return True

    # close fully: release margin and apply realized PnL
    async def close_position_full(self, index) -> bool:
        async with self._lock:
            # choose which position we're closing
            if self.direction == "long":
                positions = self.long_positions
            elif self.direction == "short":
                positions = self.short_positions
            else:
                return False  # nothing to close

            if positions['num_pos'] == 0 or positions['average_price'] is None:
                return False

            cur_price = float(spike_df_map[self.token_selection]['close'].iloc[index])
            change = (cur_price - positions['average_price']) / positions['average_price']  # decimal
            profit = self.balance_in_position * change * self.leverage
            # for short, profit sign is reversed
            if self.direction == "short":
                profit = -profit

            # release margin + realized PnL back to free balance
            self.balance_free += self.balance_in_position + profit

            # clear positions (without overwriting new balance_free)
            await self._clear_positions()

            # set total equity to free balance (no open positions)
            self.balance_total = self.balance_free
            return True

    # handle liquidation: margin is lost (already removed from balance_free at open),
    # so we just clear positions and set balance_total = balance_free
    async def liq_position(self):
        # losing margin (it was already subtracted from balance_free on open)
        await self._clear_positions()
        self.balance_total = self.balance_free

    # called periodically (every 0.4s). computes unrealized pnl and updates balance_total,
    # checks liquidation using decimal thresholds (<= -1 or >= 1)
    async def calculate_final_balance(self, current_index):
        async with self._lock:
            # if no open positions, equity is simply free cash
            if self.direction is None:
                self.balance_total = self.balance_free
                return

            if self.direction == "long":
                positions = self.long_positions
            else:
                positions = self.short_positions

            if positions['num_pos'] == 0 or positions['average_price'] is None:
                self.balance_total = self.balance_free
                return

            cur_price = float(spike_df_map[self.token_selection]['close'].iloc[current_index])
            cur_low = float(spike_df_map[self.token_selection]['low'].iloc[current_index])
            cur_high = float(spike_df_map[self.token_selection]['high'].iloc[current_index])

            entry = positions['average_price']
            change_close = (cur_price - entry) / entry
            change_low = (cur_low - entry) / entry
            change_close_lev = change_close * self.leverage
            change_low_lev = change_low * self.leverage

            if self.direction == "long":
                # liquidation if worst intrabar price -> loss >= margin
                if change_low_lev <= -1.0:
                    await self.liq_position()
                    return
                unrealized = self.balance_in_position * change_close_lev
                self.balance_total = self.balance_free + self.balance_in_position + unrealized
            else:
                change_high = (cur_high - entry) / entry
                change_high_lev = change_high * self.leverage
                if change_high_lev >= 1.0:
                    await self.liq_position()
                    return
                # short unrealized PnL (profit when price goes down -> negative change)
                unrealized = - self.balance_in_position * change_close_lev
                self.balance_total = self.balance_free + self.balance_in_position + unrealized

    async def push_order_long(self, index):
        self.long_queue.append(index)

    async def push_order_short(self, index):
        self.short_queue.append(index)

    async def push_close(self, index):
        self.close_pos_queue.append(index)

    # runs as a task
    async def consume_queue(self):
        # while True:
        for index in self.long_queue:
            await self.add_long(index)

        for index in self.short_queue:
            await self.add_short(index)

        for index in self.close_pos_queue:
            await self.close_position_full(index)

        self.long_queue = []
        self.short_queue = []
        self.close_pos_queue = []


if __name__ == '__main__':
    futures_wallet = FuturesWallet(leverage=20, token_selection=random_token)

