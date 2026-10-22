"""Profitul raportat scade taxele de noapte, pe care eToro le da separat de «netProfit» (Eugen, 22 oct)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import broker as broker_mod  # noqa: E402


class Api:
    def trade_history(self, d):
        return [{"positionId": 1, "instrumentId": 1, "netProfit": 0.38, "fees": 0.15, "isBuy": True, "closeTimestamp": "2026-10-16T07:03:42Z"},
                {"positionId": 2, "instrumentId": 1, "netProfit": -8.25, "fees": -0.08, "isBuy": True, "closeTimestamp": "2026-10-18T21:05:10Z"},
                {"positionId": 3, "instrumentId": 1, "netProfit": 1.09, "fees": 0.0, "isBuy": True, "closeTimestamp": "2026-10-19T11:05:14Z"}]


def test_closed_trades_net_includes_overnight_fees():
    b = broker_mod.EToroBroker(Api(), {"EURUSD": 1})
    assert [t["net"] for t in b.closed_trades("2026-10-11")] == [0.23, -8.17, 1.09]
    assert b.closed_trade("1", "2026-10-11")["net"] == 0.23
