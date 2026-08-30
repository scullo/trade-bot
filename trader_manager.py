import asyncio
from paper_trader import PaperTrader
from live_trader import LiveTrader, load_live_config, save_live_config

class TraderManager:
    """
    Demo (Paper Trading) ve Gercek (Binance Live) ticaret motorlari arasinda
    kusursuz, anlik gecis saglayan birlestirilmis yonetici.
    """
    def __init__(self, paper_trader: PaperTrader, live_trader: LiveTrader):
        self.paper_trader = paper_trader
        self.live_trader = live_trader
        self.config = load_live_config()
        self.mode = self.config.get("mode", "DEMO").upper()

    @property
    def active_trader(self):
        return self.live_trader if self.mode == "LIVE" else self.paper_trader

    @property
    def balance(self) -> float:
        return self.active_trader.balance

    def get_free_balance(self) -> float:
        return self.active_trader.get_free_balance()

    @property
    def open_positions(self) -> dict:
        return self.active_trader.open_positions

    @property
    def history(self) -> list:
        return self.active_trader.history

    def set_mode(self, new_mode: str):
        self.mode = new_mode.upper()
        self.config["mode"] = self.mode
        save_live_config(self.config)
        print(f">> [TICARET MODU DEGISTIRILDI]: {self.mode}")

    async def open_position(self, *args, **kwargs):
        if self.mode == "LIVE":
            return await self.live_trader.open_position(*args, **kwargs)
        else:
            return self.paper_trader.open_position(*args, **kwargs)

    async def close_position(self, *args, **kwargs):
        if self.mode == "LIVE":
            return await self.live_trader.close_position(*args, **kwargs)
        else:
            return self.paper_trader.close_position(*args, **kwargs)

    def save_history(self):
        if hasattr(self.active_trader, 'save_history'):
            return self.active_trader.save_history()
