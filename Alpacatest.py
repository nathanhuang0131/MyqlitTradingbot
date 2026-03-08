import os
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetAssetsRequest
from alpaca.trading.enums import AssetStatus, AssetClass

key = os.getenv("APCA_API_KEY_ID")
sec = os.getenv("APCA_API_SECRET_KEY")

tc = TradingClient(key, sec, paper=True)

acct = tc.get_account()
print("Account status:", acct.status)

req = GetAssetsRequest(status=AssetStatus.ACTIVE, asset_class=AssetClass.US_EQUITY)
assets = tc.get_all_assets(req)
print("Assets returned:", len(assets))
print("Sample:", [a.symbol for a in assets[:10]])