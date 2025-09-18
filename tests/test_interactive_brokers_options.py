import datetime as dt
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest

from src.tools.interactive_brokers import (
    InteractiveBrokersAPIError,
    InteractiveBrokersClient,
)


class MockResponse:
    def __init__(self, payload: Any, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code
        if payload is None:
            self._content = b""
        else:
            import json

            self._content = json.dumps(payload).encode("utf-8")
        self.text = self._content.decode("utf-8") if self._content else ""

    @property
    def content(self):
        return self._content

    def json(self):
        return self._payload


@pytest.fixture()
def mock_session():
    session = MagicMock()
    session.verify = True
    return session


def _build_client(mock_session, responses: List[MockResponse]) -> InteractiveBrokersClient:
    mock_session.request.side_effect = responses
    client = InteractiveBrokersClient(base_url="https://example.com/v1/api", session=mock_session, verify=True)
    return client


def test_fetch_option_chain_success(mock_session):
    responses = [
        MockResponse({"authenticated": True}),
        MockResponse([
            {"conid": 265598, "symbol": "AAPL", "description": "Apple Inc", "exchange": "SMART"}
        ]),
        MockResponse(
            {
                "expirations": ["20240119", "20240216"],
                "multiplier": "100",
                "tradingClass": "AAPL",
                "exchange": ["SMART"],
                "hasMini": False,
                "underlyingConid": 265598,
            }
        ),
        MockResponse(
            {
                "call": [
                    {
                        "conid": 1001,
                        "strike": 150,
                        "expiry": "20240119",
                        "right": "C",
                        "exchange": "SMART",
                        "multiplier": "100",
                    }
                ],
                "put": [
                    {
                        "conid": 1002,
                        "strike": 150,
                        "expiry": "20240119",
                        "right": "P",
                        "exchange": "SMART",
                        "multiplier": "100",
                    }
                ],
            }
        ),
        MockResponse(
            [
                {
                    "conid": 1001,
                    "31": "1.2",
                    "32": "5",
                    "33": "7",
                    "84": "1.25",
                    "85": "0.15",
                    "86": "1.3",
                    "87": "10",
                    "88": "120",
                    "729": "0.25",
                    "730": "0.5",
                    "731": "0.12",
                    "732": "-0.05",
                    "733": "0.2",
                    "734": "190",
                    "763": "250",
                    "221": "1.26",
                    "999": "extra-field",
                },
                {
                    "conid": 1002,
                    "31": "1.1",
                    "32": "4",
                    "33": "6",
                    "84": "1.05",
                    "85": "-0.05",
                    "86": "1.15",
                    "87": "12",
                    "88": "90",
                    "729": "0.30",
                    "730": "-0.45",
                    "731": "0.08",
                    "732": "-0.03",
                    "733": "0.18",
                    "734": "190",
                    "763": "300",
                    "221": "1.12",
                },
            ]
        ),
    ]

    client = _build_client(mock_session, responses)
    option_chain = client.fetch_option_chain("AAPL", limit_expirations=1)

    assert option_chain.ticker == "AAPL"
    assert option_chain.underlying_conid == 265598
    assert option_chain.multiplier == 100
    assert option_chain.trading_class == "AAPL"
    assert option_chain.exchanges == ["SMART"]
    assert option_chain.has_mini is False
    assert option_chain.additional_data["underlyingConid"] == 265598
    assert option_chain.expirations == [dt.date(2024, 1, 19)]

    assert len(option_chain.options) == 2
    call_option = next(opt for opt in option_chain.options if opt.right == "C")
    put_option = next(opt for opt in option_chain.options if opt.right == "P")

    assert call_option.conid == 1001
    assert call_option.market_price == pytest.approx(1.26)
    assert call_option.bid == pytest.approx(1.2)
    assert call_option.ask == pytest.approx(1.3)
    assert call_option.bid_size == 5
    assert call_option.ask_size == 7
    assert call_option.volume == 120
    assert call_option.open_interest == 250
    assert call_option.implied_volatility == pytest.approx(0.25)
    assert call_option.delta == pytest.approx(0.5)
    assert call_option.gamma == pytest.approx(0.12)
    assert call_option.theta == pytest.approx(-0.05)
    assert call_option.vega == pytest.approx(0.2)
    assert call_option.underlying_price == pytest.approx(190)
    assert call_option.additional_fields == {"999": "extra-field"}

    assert put_option.conid == 1002
    assert put_option.market_price == pytest.approx(1.12)
    assert put_option.bid_size == 4
    assert put_option.ask_size == 6
    assert put_option.implied_volatility == pytest.approx(0.30)
    assert put_option.delta == pytest.approx(-0.45)

    # Ensure the API was called with the expected endpoints and parameters.
    called_paths = [call.kwargs.get("params", {}) for call in mock_session.request.call_args_list]
    assert any("conids" in params for params in called_paths)


def test_fetch_option_chain_with_invalid_expiry(mock_session):
    responses = [
        MockResponse({"authenticated": True}),
        MockResponse([{"conid": 123, "symbol": "MSFT"}]),
        MockResponse({"expirations": ["20240119"], "tradingClass": "MSFT"}),
    ]
    client = _build_client(mock_session, responses)

    with pytest.raises(InteractiveBrokersAPIError):
        client.fetch_option_chain("MSFT", expiry="20240216")


def test_fetch_option_chain_handles_missing_snapshot(mock_session):
    responses = [
        MockResponse({"authenticated": True}),
        MockResponse([{"conid": 555, "symbol": "TSLA"}]),
        MockResponse({"expirations": ["20240119"], "tradingClass": "TSLA"}),
        MockResponse(
            {
                "call": [
                    {"conid": 2001, "strike": 200, "expiry": "20240119", "right": "C"},
                ],
            }
        ),
        MockResponse([], status_code=200),
    ]

    client = _build_client(mock_session, responses)
    option_chain = client.fetch_option_chain("TSLA", limit_expirations=1)
    assert len(option_chain.options) == 1
    assert option_chain.options[0].market_price is None

