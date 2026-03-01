# Execution/clients.py
try:
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.trading.client import TradingClient
    ALPACA_AVAILABLE = True
except ModuleNotFoundError:
    StockHistoricalDataClient = TradingClient = object  # type: ignore
    ALPACA_AVAILABLE = False

from qlib_tradingbot.config import API_BASE_URL, API_KEY, API_SECRET

def build_clients(paper: bool = True):
    if not API_KEY or not API_SECRET:
        raise RuntimeError("Missing APCA_API_KEY_ID or APCA_API_SECRET_KEY in environment variables.")

    # alpaca-py primarily uses the 'paper' flag to route to paper vs live.
    # Some versions also accept an explicit base_url; we pass it only when set
    # and when the constructor supports it.
    trade_kwargs = {"api_key": API_KEY, "secret_key": API_SECRET, "paper": paper}
    if API_BASE_URL:
        trade_kwargs["base_url"] = API_BASE_URL

    # StockHistoricalDataClient usually does not need base_url; keep it minimal.
    data_client = StockHistoricalDataClient(api_key=API_KEY, secret_key=API_SECRET)
    try:
        trade_client = TradingClient(**trade_kwargs)
    except TypeError:
        # Older/newer alpaca-py versions may not accept base_url.
        trade_kwargs.pop("base_url", None)
        trade_client = TradingClient(**trade_kwargs)
    return data_client, trade_client
