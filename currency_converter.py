"""
Currency Conversion Engine
============================
Provides real-time and fallback currency conversion.
Supports major currencies with live exchange rate fetching.

Source: exchangerate-api.com (free tier, no auth needed for limited use)
"""

import requests
import time
from typing import Dict, Tuple, Optional


# ─── Fallback exchange rates (updated Q1 2025) ──────────────────────────────
FALLBACK_RATES = {
    "USD": 1.0,
    "CAD": 1.38,
    "EUR": 0.92,
    "GBP": 0.79,
    "AUD": 1.55,
    "JPY": 149.50,
    "INR": 83.10,
    "SGD": 1.34,
    "CHF": 0.88,
    "SEK": 10.45,
    "NOK": 10.60,
    "DKK": 6.88,
    "NZD": 1.63,
    "BRL": 4.97,
    "MXN": 17.15,
    "KRW": 1320.0,
    "HKD": 7.82,
    "TWD": 31.50,
    "ZAR": 18.60,
    "AED": 3.67,
}

CURRENCY_SYMBOLS = {
    "USD": "$", "CAD": "C$", "EUR": "\u20ac", "GBP": "\u00a3",
    "AUD": "A$", "JPY": "\u00a5", "INR": "\u20b9", "SGD": "S$",
    "CHF": "CHF", "SEK": "kr", "NOK": "kr", "DKK": "kr",
    "NZD": "NZ$", "BRL": "R$", "MXN": "MX$", "KRW": "\u20a9",
    "HKD": "HK$", "TWD": "NT$", "ZAR": "R", "AED": "AED",
}

CURRENCY_NAMES = {
    "USD": "US Dollar", "CAD": "Canadian Dollar", "EUR": "Euro",
    "GBP": "British Pound", "AUD": "Australian Dollar", "JPY": "Japanese Yen",
    "INR": "Indian Rupee", "SGD": "Singapore Dollar", "CHF": "Swiss Franc",
    "SEK": "Swedish Krona", "NOK": "Norwegian Krone", "DKK": "Danish Krone",
    "NZD": "New Zealand Dollar", "BRL": "Brazilian Real", "MXN": "Mexican Peso",
    "KRW": "South Korean Won", "HKD": "Hong Kong Dollar", "TWD": "Taiwan Dollar",
    "ZAR": "South African Rand", "AED": "UAE Dirham",
}

# Cache for live rates (in-memory, session-scoped)
_rate_cache: Dict = {}
_cache_timestamp: float = 0
CACHE_TTL_SECONDS = 3600  # 1 hour


def fetch_live_rates(base: str = "USD") -> Tuple[Dict, bool, str]:
    """
    Fetch live exchange rates from free API.
    Returns (rates_dict, is_live, status_message).
    """
    global _rate_cache, _cache_timestamp

    # Check cache
    if _rate_cache and (time.time() - _cache_timestamp) < CACHE_TTL_SECONDS:
        return _rate_cache, True, "Cached live rates"

    try:
        url = f"https://open.er-api.com/v6/latest/{base}"
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("result") == "success":
                rates = data.get("rates", {})
                # Filter to supported currencies
                filtered = {k: v for k, v in rates.items() if k in FALLBACK_RATES}
                _rate_cache = filtered
                _cache_timestamp = time.time()
                return filtered, True, f"Live rates from {data.get('provider', 'API')}"
        return FALLBACK_RATES.copy(), False, f"API returned HTTP {resp.status_code}"
    except requests.exceptions.Timeout:
        return FALLBACK_RATES.copy(), False, "API timeout — using fallback rates"
    except Exception as e:
        return FALLBACK_RATES.copy(), False, f"API error — using fallback rates"


def convert(amount: float, from_currency: str = "USD",
            to_currency: str = "USD", rates: Optional[Dict] = None) -> float:
    """Convert amount between currencies."""
    if from_currency == to_currency:
        return amount

    if rates is None:
        rates = FALLBACK_RATES

    from_rate = rates.get(from_currency, 1.0)
    to_rate = rates.get(to_currency, 1.0)

    # Convert to USD first, then to target
    usd_amount = amount / from_rate
    return round(usd_amount * to_rate, 2)


def get_symbol(currency: str) -> str:
    """Get currency symbol."""
    return CURRENCY_SYMBOLS.get(currency, currency)


def get_multiplier(currency: str, rates: Optional[Dict] = None) -> float:
    """Get multiplier from USD to target currency."""
    if rates is None:
        rates = FALLBACK_RATES
    return rates.get(currency, 1.0)


def format_currency(amount: float, currency: str = "USD",
                    rates: Optional[Dict] = None) -> str:
    """Format amount with currency symbol."""
    converted = convert(amount, "USD", currency, rates)
    symbol = get_symbol(currency)

    if currency in ("JPY", "KRW"):
        return f"{symbol}{converted:,.0f}"
    return f"{symbol}{converted:,.2f}"


def get_supported_currencies() -> Dict[str, str]:
    """Return dict of currency code -> display name."""
    return {k: f"{k} ({CURRENCY_SYMBOLS[k]}) — {CURRENCY_NAMES[k]}"
            for k in CURRENCY_SYMBOLS}
