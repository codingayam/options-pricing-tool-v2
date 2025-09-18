"""Utilities for fetching market data from Interactive Brokers' Client Portal Web API.

The module focuses on fetching option chain information to mirror the
capabilities currently provided through the yfinance integration while also
highlighting the richer real-time data available from Interactive Brokers.
"""
from __future__ import annotations

import datetime as _dt
import os
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import requests

from src.data.models import OptionChain, OptionContract


class InteractiveBrokersAPIError(RuntimeError):
    """Raised when the Interactive Brokers Client Portal Web API returns an error."""


@dataclass
class SnapshotField:
    """Mapping between IB field identifiers and human readable names."""

    code: str
    name: str
    transform: Optional[callable] = None

    def parse(self, value):
        if self.transform is None or value is None:
            return value
        try:
            return self.transform(value)
        except Exception:  # pragma: no cover - defensive, transform is safe
            return value


class InteractiveBrokersClient:
    """Minimal client for the Interactive Brokers Client Portal Web API."""

    DEFAULT_BASE_URL = "https://localhost:5000/v1/api"
    DEFAULT_TIMEOUT = 10.0

    # Snapshot fields documented by Interactive Brokers. The goal is to match the
    # information returned by yfinance while exposing additional real-time data
    # (Greeks, mark price, underlying price, etc.).
    SNAPSHOT_FIELDS: Sequence[SnapshotField] = (
        SnapshotField("31", "bid", float),
        SnapshotField("32", "bid_size", lambda v: int(float(v))),
        SnapshotField("33", "ask_size", lambda v: int(float(v))),
        SnapshotField("84", "last_trade_price", float),
        SnapshotField("85", "change", float),
        SnapshotField("86", "ask", float),
        SnapshotField("87", "last_trade_size", lambda v: int(float(v))),
        SnapshotField("88", "volume", lambda v: int(float(v))),
        SnapshotField("89", "close", float),
        SnapshotField("90", "high", float),
        SnapshotField("91", "low", float),
        SnapshotField("221", "mark_price", float),
        SnapshotField("729", "implied_volatility", float),
        SnapshotField("730", "delta", float),
        SnapshotField("731", "gamma", float),
        SnapshotField("732", "theta", float),
        SnapshotField("733", "vega", float),
        SnapshotField("734", "underlying_price", float),
        SnapshotField("763", "open_interest", lambda v: int(float(v))),
    )

    def __init__(
        self,
        base_url: Optional[str] = None,
        session: Optional[requests.Session] = None,
        verify: Optional[bool] = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.base_url = (base_url or os.getenv("IBKR_API_BASE_URL") or self.DEFAULT_BASE_URL).rstrip("/")
        self.session = session or requests.Session()
        self.timeout = timeout

        if verify is None:
            env_verify = os.getenv("IBKR_API_VERIFY_SSL")
            if env_verify is not None:
                verify = env_verify.lower() not in {"0", "false", "no"}
            else:
                # Interactive Brokers ships the Client Portal Gateway with a
                # self-signed certificate by default. To make local development
                # straightforward we disable certificate validation unless the
                # user explicitly opts in via configuration.
                verify = False
        self.session.verify = verify

        # Construct lookup map for snapshot fields for fast access.
        self._field_map: Dict[str, SnapshotField] = {f.code: f for f in self.SNAPSHOT_FIELDS}

    # ------------------------------------------------------------------
    # HTTP helpers
    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, str]] = None,
        json: Optional[Dict] = None,
        allow_empty: bool = False,
    ) -> Dict:
        url = f"{self.base_url}/{path.lstrip('/')}"
        response = self.session.request(method, url, params=params, json=json, timeout=self.timeout)

        if response.status_code >= 400:
            try:
                payload = response.json()
            except ValueError:
                payload = response.text
            raise InteractiveBrokersAPIError(f"Interactive Brokers API error ({response.status_code}): {payload}")

        if not response.content:
            if allow_empty:
                return {}
            raise InteractiveBrokersAPIError("Interactive Brokers API returned an empty response")

        try:
            return response.json()
        except ValueError as exc:  # pragma: no cover - defensive guard
            raise InteractiveBrokersAPIError("Interactive Brokers API returned invalid JSON") from exc

    # ------------------------------------------------------------------
    # API endpoints
    def ensure_authenticated(self) -> Dict:
        """Return the authentication status. Raises on failure."""

        status = self._request("GET", "iserver/auth/status")
        if not status.get("authenticated"):
            raise InteractiveBrokersAPIError(
                "Interactive Brokers Client Portal Gateway is not authenticated. "
                "Log in via the Client Portal or call /iserver/auth/ssodh."
            )
        return status

    def search_contract(self, symbol: str, sec_type: str = "STK", exchange: Optional[str] = None) -> Dict:
        payload: Dict[str, str] = {"symbol": symbol, "name": True, "secType": sec_type}
        if exchange:
            payload["exchange"] = exchange
        matches = self._request("POST", "iserver/secdef/search", json=payload)
        if not isinstance(matches, list) or not matches:
            raise InteractiveBrokersAPIError(f"No contract information returned for symbol {symbol}")
        return matches[0]

    def get_option_chain_info(self, conid: int, exchange: Optional[str] = None) -> Dict:
        params: Dict[str, str] = {"conid": str(conid)}
        if exchange:
            params["exchange"] = exchange
        return self._request("GET", "iserver/secdef/optionchain", params=params)

    def get_option_strikes(
        self,
        conid: int,
        expiry: str,
        exchange: Optional[str] = None,
        strike_range: Optional[Tuple[float, float]] = None,
    ) -> Dict:
        params: Dict[str, str] = {"conid": str(conid), "expiry": expiry}
        if exchange:
            params["exchange"] = exchange
        if strike_range:
            params["strike"] = f"{strike_range[0]}:{strike_range[1]}"
        return self._request("GET", "iserver/secdef/strikes", params=params)

    def get_market_data_snapshot(self, conids: Sequence[int], fields: Optional[Sequence[str]] = None) -> Dict[int, Dict]:
        if not conids:
            return {}
        params = {
            "conids": ",".join(str(conid) for conid in conids),
            "fields": ",".join(fields or [field.code for field in self.SNAPSHOT_FIELDS]),
        }
        data = self._request("POST", "iserver/marketdata/snapshot", params=params)
        if isinstance(data, dict) and data.get("error"):
            raise InteractiveBrokersAPIError(data["error"])
        if isinstance(data, dict):
            data = [data]
        snapshots: Dict[int, Dict] = {}
        for entry in data:
            try:
                conid = int(entry["conid"])
            except (KeyError, TypeError, ValueError):
                continue
            snapshots[conid] = entry
        return snapshots

    # ------------------------------------------------------------------
    # High level option chain helper
    def fetch_option_chain(
        self,
        symbol: str,
        *,
        expiry: Optional[Sequence[str] | Sequence[_dt.date] | _dt.date | str] = None,
        exchange: Optional[str] = "SMART",
        strike_range: Optional[Tuple[float, float]] = None,
        limit_expirations: Optional[int] = None,
        include_rights: Sequence[str] = ("C", "P"),
        fields: Optional[Sequence[str]] = None,
        ensure_auth: bool = True,
    ) -> OptionChain:
        if ensure_auth:
            self.ensure_authenticated()

        contract = self.search_contract(symbol, sec_type="STK", exchange=exchange)
        underlying_conid = int(contract["conid"])

        chain_info = self.get_option_chain_info(underlying_conid, exchange=exchange)
        expiration_candidates = self._extract_expirations(chain_info)
        requested_expirations = self._select_expirations(expiry, expiration_candidates, limit_expirations)

        option_contracts: List[OptionContract] = []
        conids: List[int] = []

        for expiry_code in requested_expirations:
            strikes_payload = self.get_option_strikes(
                underlying_conid,
                expiry_code,
                exchange=exchange,
                strike_range=strike_range,
            )
            contracts = self._parse_strikes_payload(
                strikes_payload,
                symbol,
                include_rights=tuple(right.upper() for right in include_rights),
            )
            option_contracts.extend(contracts)
            conids.extend(contract.conid for contract in contracts)

        snapshots = self.get_market_data_snapshot(conids, fields=fields)
        for contract in option_contracts:
            if snapshot := snapshots.get(contract.conid):
                self._apply_snapshot(contract, snapshot)

        expirations = [self._parse_expiry(code) for code in requested_expirations]
        option_chain = OptionChain(
            ticker=symbol,
            underlying_conid=underlying_conid,
            options=sorted(option_contracts, key=lambda c: (c.expiry, c.strike, c.right)),
            expirations=expirations,
            multiplier=self._maybe_int(chain_info.get("multiplier")),
            trading_class=chain_info.get("tradingClass"),
            exchanges=self._ensure_list(chain_info.get("exchange")),
            has_mini=chain_info.get("hasMini"),
            additional_data={k: v for k, v in chain_info.items() if k not in {"expirations", "exchange"}},
        )
        return option_chain

    # ------------------------------------------------------------------
    # Helpers
    def _extract_expirations(self, chain_info: Dict) -> List[str]:
        expirations = chain_info.get("expirations") or chain_info.get("expirationDates") or []
        if not isinstance(expirations, list):
            return []
        return [self._normalise_expiry(exp) for exp in expirations]

    def _select_expirations(
        self,
        requested: Optional[Sequence[str] | Sequence[_dt.date] | _dt.date | str],
        available: Sequence[str],
        limit: Optional[int],
    ) -> List[str]:
        if requested is None:
            expirations = list(available)
        else:
            if isinstance(requested, (str, _dt.date)):
                requested_list = [requested]
            else:
                requested_list = list(requested)
            expirations = [self._normalise_expiry(exp) for exp in requested_list]
            expirations = [exp for exp in expirations if exp in set(available)]
            if not expirations:
                raise InteractiveBrokersAPIError(
                    f"Requested expirations {requested_list} are not available. Available expirations: {available}"
                )
        if limit is not None:
            expirations = expirations[:limit]
        return expirations

    def _parse_strikes_payload(
        self,
        payload: Dict,
        symbol: str,
        include_rights: Tuple[str, ...],
    ) -> List[OptionContract]:
        contracts: List[OptionContract] = []
        for item in self._iterate_payload_entries(payload):
            right = item.get("right", "").upper()
            if right not in include_rights:
                continue
            try:
                conid = int(item["conid"])
                strike = float(item.get("strike"))
                expiry = self._parse_expiry(item.get("expiry") or item.get("lastTradingDay"))
            except (KeyError, TypeError, ValueError):
                continue
            contract = OptionContract(
                ticker=symbol,
                conid=conid,
                expiry=expiry,
                strike=strike,
                right=right,
                multiplier=self._maybe_int(item.get("multiplier")),
                exchange=item.get("exchange"),
            )
            contracts.append(contract)
        return contracts

    def _iterate_payload_entries(self, payload: Dict) -> Iterable[Dict]:
        if isinstance(payload, list):
            for part in payload:
                yield from self._iterate_payload_entries(part)
            return
        if not isinstance(payload, dict):
            return
        for key in ("call", "calls", "put", "puts"):
            entries = payload.get(key)
            if isinstance(entries, list):
                for entry in entries:
                    if isinstance(entry, dict):
                        yield entry

    def _apply_snapshot(self, contract: OptionContract, snapshot: Dict) -> None:
        additional: Dict[str, float] = {}
        for field, value in snapshot.items():
            if field == "conid":
                continue
            if field in self._field_map:
                parsed_value = self._field_map[field].parse(value)
                setattr(contract, self._field_map[field].name, parsed_value)
            else:
                additional[field] = value
        if additional:
            contract.additional_fields.update(additional)
        # Maintain backward compatibility with yfinance naming conventions.
        if contract.market_price is None:
            contract.market_price = contract.mark_price or contract.last_trade_price

    def _normalise_expiry(self, expiry: str | _dt.date | None) -> str:
        if expiry is None:
            raise InteractiveBrokersAPIError("Missing expiry in option chain payload")
        if isinstance(expiry, _dt.date):
            return expiry.strftime("%Y%m%d")
        expiry_str = str(expiry)
        if len(expiry_str) == 8 and expiry_str.isdigit():
            return expiry_str
        try:
            parsed = _dt.datetime.strptime(expiry_str, "%Y-%m-%d")
            return parsed.strftime("%Y%m%d")
        except ValueError:
            raise InteractiveBrokersAPIError(f"Unsupported expiry format: {expiry_str}")

    def _parse_expiry(self, expiry: str | _dt.date | None) -> _dt.date:
        if expiry is None:
            raise InteractiveBrokersAPIError("Missing expiry value")
        if isinstance(expiry, _dt.date):
            return expiry
        expiry_str = self._normalise_expiry(expiry)
        return _dt.datetime.strptime(expiry_str, "%Y%m%d").date()

    @staticmethod
    def _maybe_int(value) -> Optional[int]:
        if value in (None, ""):
            return None
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _ensure_list(value) -> Optional[List[str]]:
        if value is None:
            return None
        if isinstance(value, list):
            return value
        return [value]
