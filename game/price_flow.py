from game.data_preparation import spike_df_map, random_token, pd
from fastapi import WebSocket
import asyncio


class PriceFlow:
    def __init__(self, window_size=60, token_selection='somi'):
        self.window_size = window_size
        self.token_selection = token_selection
        self.total_rows = len(spike_df_map[self.token_selection])
        self.window = []
        self.current_index = 0

    @staticmethod
    def serialize_row(row):
        """Convert a DataFrame row to a JSON-serializable dict"""
        row_dict = row.to_dict()
        return {k: (v.isoformat() if isinstance(v, pd.Timestamp) else v)
                for k, v in row_dict.items()}

    async def initialize_dict(self):
        # restart window
        self.window = []
        for i in range(self.window_size):
            self.window.append(self.serialize_row(spike_df_map[self.token_selection].iloc[i]))

        return self.window

    async def handle_websocket_flow(self, websocket: WebSocket):  # , futures_wallet: FuturesWallet):
        # Start sliding
        for i in range(self.window_size, self.total_rows):
            self.current_index = i
            self.window.pop(0)
            self.window.append(self.serialize_row(spike_df_map[self.token_selection].iloc[i]))
            await websocket.send_json({
                "type": "prices",
                "count": i + 1,
                "window": self.window,
                # "wallet": await futures_wallet.get_wallet_state()
            })
            await asyncio.sleep(1)

        for i in range(self.window_size, self.total_rows):
            self.current_index = i
            self.window.pop(0)
            self.window.append(self.serialize_row(spike_df_map[self.token_selection].iloc[i]))
            await websocket.send_json({
                "type": "prices",
                "count": i + 1,
                "window": self.window,
                # "wallet": await futures_wallet.get_wallet_state()
            })

            await asyncio.sleep(1)


if __name__ == '__main__':
    price_flow = PriceFlow()

