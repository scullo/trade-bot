import asyncio
from paper_trader import PaperTrader
from live_trader import LiveTrader, load_live_config, save_live_config

class TraderManager:
    """
    Demo (Paper Trading) ve Gerçek (Binance Live) ticaret motorları arasında
    kusursuz, anlık geçiş sağlayan birleştirilmiş yönetici.
    Aktif motorda tanımlı tüm özellik ve metotları saydam olarak iletir (__getattr__).
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

    async def initialize(self):
        """Uygulama açılışında veya mod değişiminde canlı tüccarı hazırlar."""
        if hasattr(self.live_trader, 'initialize'):
            await self.live_trader.initialize()

    def set_mode(self, new_mode: str):
        self.mode = new_mode.upper()
        self.config["mode"] = self.mode
        save_live_config(self.config)
        print(f">> [TİCARET MODU DEĞİŞTİRİLDİ]: {self.mode}")
        if self.mode == "LIVE":
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self.live_trader.initialize())
            except Exception as e:
                print(f">> [TRADER MANAGER] Canlı başlatma görevi oluşturulamadı: {e}")

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

    def save_local_history(self):
        if hasattr(self.active_trader, 'save_local_history'):
            return self.active_trader.save_local_history()

    def update_tick_telemetry(self, *args, **kwargs):
        if hasattr(self.active_trader, 'update_tick_telemetry'):
            return self.active_trader.update_tick_telemetry(*args, **kwargs)

    def update_position_levels(self, *args, **kwargs):
        if hasattr(self.active_trader, 'update_position_levels'):
            return self.active_trader.update_position_levels(*args, **kwargs)

    def __getattr__(self, name):
        """
        TraderManager üzerinde doğrudan tanımlanmamış tüm metot ve özellikleri
        aktif tüccara (PaperTrader ya da LiveTrader) yönlendirir.
        """
        return getattr(self.active_trader, name)
