"""BTC kline data fetching from Binance — shared by results display and backtest engine."""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

BINANCE_KLINE_URL = "https://api.binance.com/api/v3/klines"

# ── Module-level shared client and cache ─────────────────────────────────────

_shared_client: httpx.AsyncClient | None = None
_kline_cache: dict[tuple[int, int], list[dict]] = {}
_KLINE_CACHE_MAX = 200  # cap to prevent unbounded growth during large batches


def _get_client() -> httpx.AsyncClient:
    """Lazy-init a shared httpx client (connection pooling across requests)."""
    global _shared_client
    if _shared_client is None or _shared_client.is_closed:
        _shared_client = httpx.AsyncClient(
            timeout=15.0,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
    return _shared_client


def clear_kline_cache() -> None:
    """Clear the in-memory kline cache (call between batch runs if needed)."""
    _kline_cache.clear()


async def close_client() -> None:
    """Close the shared httpx client (call during application shutdown)."""
    global _shared_client
    if _shared_client is not None and not _shared_client.is_closed:
        await _shared_client.aclose()
        _shared_client = None


def _iso_to_ms(ts: str) -> int:
    """Convert ISO 8601 timestamp string to milliseconds since epoch.

    Treats naive (no tzinfo) strings as UTC to avoid system-timezone drift.
    """
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _transform_klines(raw: list) -> list[dict]:
    """Transform raw Binance kline arrays to structured dicts."""
    klines: list[dict] = []
    for k in raw:
        klines.append({
            "open_time": k[0],
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
            "close_time": k[6],
            "quote_volume": float(k[7]),
            "trades": k[8],
        })
    return klines


async def fetch_btc_klines(
    start_ts: str,
    end_ts: str,
    interval: str = "1m",
    limit: int = 1000,
) -> list[dict]:
    """Fetch BTC/USDT klines from Binance for the given ISO time range.

    Returns a list of kline dicts with keys:
        open_time, open, high, low, close, volume, close_time, quote_volume, trades
    """
    start_ms = _iso_to_ms(start_ts)
    end_ms = _iso_to_ms(end_ts)

    # Cache hit — many slugs share overlapping time windows
    cache_key = (start_ms, end_ms)
    if cache_key in _kline_cache:
        return _kline_cache[cache_key]

    try:
        client = _get_client()
        resp = await client.get(
            BINANCE_KLINE_URL,
            params={
                "symbol": "BTCUSDT",
                "interval": interval,
                "startTime": start_ms,
                "endTime": end_ms,
                "limit": limit,
            },
        )
        resp.raise_for_status()
        raw = resp.json()
    except httpx.HTTPError as e:
        logger.warning("Binance kline request failed: %s", e)
        raise

    result = _transform_klines(raw)
    # Evict oldest entries if cache is full to prevent OOM during large batches
    if len(_kline_cache) >= _KLINE_CACHE_MAX:
        # Remove ~25% of entries (oldest inserted)
        to_remove = list(_kline_cache.keys())[: _KLINE_CACHE_MAX // 4]
        for k in to_remove:
            del _kline_cache[k]
    _kline_cache[cache_key] = result
    return result


def compute_btc_trend(
    klines: list[dict],
    start_ts: str,
    window_1_min: int,
    window_2_min: int,
    min_momentum: float,
) -> dict:
    """Compute BTC trend filter from kline data.

    Uses **open** prices at three time points so that each price represents
    the market price *at* that exact timestamp (a kline's ``close`` is
    actually the price one interval later):

      P0  = open at session start
      Pw1 = open at start + window_1_min
         Pw2 = open at start + window_2_min          (absolute offset)
 
         Both window offsets are measured from session start, so with
         window_1_min=5 and window_2_min=10 the two windows are [0→5 min]
         and [5→10 min] respectively.
 
         Computes:
             a1 = (Pw1 - P0)  / P0   — momentum over first window
             a2 = (Pw2 - Pw1) / Pw1  — momentum over second window

    Trend passes when: abs(a1 + a2) > min_momentum AND a1 * a2 > 0
    (same direction in both windows with sufficient magnitude)

    Returns dict with keys: a1, a2, passed, p0, p_w1, p_w2, error, factors
    """
    if not klines:
        return {"a1": 0.0, "a2": 0.0, "passed": True, "p0": 0.0, "p_w1": 0.0, "p_w2": 0.0, "error": "no_klines", "factors": _empty_factors()}

    start_ms = _iso_to_ms(start_ts)
    target_w1_ms = start_ms + window_1_min * 60 * 1000
    target_w2_ms = start_ms + window_2_min * 60 * 1000

    def _closest_open(target_ms: int) -> float | None:
        """Find kline whose open_time is closest to target_ms and return its open price."""
        best: dict | None = None
        best_dist = float("inf")
        for k in klines:
            dist = abs(k["open_time"] - target_ms)
            if dist < best_dist:
                best_dist = dist
                best = k
        return best["open"] if best else None

    p0 = _closest_open(start_ms)
    p_w1 = _closest_open(target_w1_ms)
    p_w2 = _closest_open(target_w2_ms)

    if p0 is None or p_w1 is None or p_w2 is None:
        return {"a1": 0.0, "a2": 0.0, "passed": True, "p0": 0.0, "p_w1": 0.0, "p_w2": 0.0, "error": "missing_prices", "factors": _empty_factors()}

    if p0 == 0 or p_w1 == 0:
        return {"a1": 0.0, "a2": 0.0, "passed": True, "p0": p0, "p_w1": p_w1, "p_w2": p_w2, "error": "zero_price", "factors": _empty_factors()}

    a1 = (p_w1 - p0) / p0
    a2 = (p_w2 - p_w1) / p_w1

    passed = abs(a1 + a2) > min_momentum and a1 * a2 > 0

    # ── P0 factors computation ──────────────────────────────────────────
    factors = compute_btc_factors(klines, start_ms, target_w1_ms, target_w2_ms, a1, a2)

    return {
        "a1": round(a1, 8),
        "a2": round(a2, 8),
        "passed": passed,
        "p0": p0,
        "p_w1": p_w1,
        "p_w2": p_w2,
        "error": None,
        "factors": factors,
    }


# ── P0 Factor Computation ────────────────────────────────────────────────────

def compute_btc_factors(
    klines: list[dict],
    start_ms: int,
    target_w1_ms: int,
    target_w2_ms: int,
    a1: float,
    a2: float,
    atr_lookback: int = 20,
    vol_lookback: int = 20,
) -> dict:
    """Compute 5 P0-level factors from 1-min BTC kline data.

    IMPORTANT — look-ahead bias guard:
    A 1-min kline with open_time=T contains data for the interval [T, T+60s).
    Its open price is known at T, but high/low/close/volume are only known at
    T+60s.  To avoid look-ahead bias when predicting price direction AFTER the
    second window ends (target_w2_ms), we must **exclude** any kline whose
    open_time >= target_w2_ms.  The last usable kline has
    open_time = target_w2_ms - 60_000 (its close is known at target_w2_ms,
    which is exactly the boundary — still valid).

    Factors (all raw decimals, not percentages):
      f1_momentum       – directional momentum: a1 + a2
      f2_acceleration   – momentum acceleration: |a2| - |a1|  (>0 means accelerating)
      f2_consistent     – direction consistency: 1 if a1*a2 > 0, else 0
      f3_vol_norm       – volatility-normalized momentum: (a1+a2) / rolling ATR ratio
      f4_volume_z       – volume z-score over lookback window
      f4_volume_dir     – volume z-score * sign(close - open) of latest candle
      f5_body_ratio     – candle body / range ratio of latest candle (0~1)
      f5_wick_imbalance – upper wick minus lower wick, normalized by range (-1~1)

    Also returns per-minute factor time series for charting:
      factor_series: list of {time_ms, atr_ratio, vol_z, body_ratio, wick_imb, momentum}
    """
    if not klines or len(klines) < 2:
        return _empty_factors()

    # Slice klines strictly BEFORE the second window boundary.
    # open_time < target_w2_ms ensures the last included kline's close (at
    # open_time + 60s) is known at or before target_w2_ms — no future data.
    window_klines = [k for k in klines if start_ms <= k["open_time"] < target_w2_ms]
    if len(window_klines) < 2:
        window_klines = klines  # fallback to all available

    # ── f1: Directional momentum ─────────────────────────────────────────
    f1_momentum = round(a1 + a2, 8)

    # ── f2: Acceleration & consistency ───────────────────────────────────
    f2_acceleration = round(abs(a2) - abs(a1), 8)
    f2_consistent = 1 if a1 * a2 > 0 else 0

    # ── f3: Volatility-normalized momentum ───────────────────────────────
    # True Range for each kline, then ATR
    trs: list[float] = []
    for i, k in enumerate(window_klines):
        high_low = k["high"] - k["low"]
        if i > 0:
            prev_close = window_klines[i - 1]["close"]
            tr = max(high_low, abs(k["high"] - prev_close), abs(k["low"] - prev_close))
        else:
            tr = high_low
        trs.append(tr)

    atr_n = min(atr_lookback, len(trs))
    atr = sum(trs[-atr_n:]) / atr_n if atr_n > 0 else 0.0
    mid_price = (window_klines[-1]["open"] + window_klines[-1]["close"]) / 2
    atr_ratio = atr / mid_price if mid_price > 0 else 0.0
    f3_vol_norm = round(f1_momentum / atr_ratio, 6) if atr_ratio > 1e-12 else 0.0

    # ── f4: Volume z-score ───────────────────────────────────────────────
    volumes = [k["volume"] for k in window_klines]
    vol_n = min(vol_lookback, len(volumes))
    vol_slice = volumes[-vol_n:]
    vol_mean = sum(vol_slice) / len(vol_slice) if vol_slice else 0.0
    vol_std = math.sqrt(sum((v - vol_mean) ** 2 for v in vol_slice) / len(vol_slice)) if len(vol_slice) > 1 else 1.0
    latest_vol = volumes[-1] if volumes else 0.0
    f4_volume_z = round((latest_vol - vol_mean) / vol_std, 4) if vol_std > 1e-12 else 0.0

    latest_k = window_klines[-1]
    close_open_sign = 1 if latest_k["close"] >= latest_k["open"] else -1
    f4_volume_dir = round(f4_volume_z * close_open_sign, 4)

    # ── f5: Candle structure (body ratio & wick imbalance) ───────────────
    candle_range = latest_k["high"] - latest_k["low"]
    eps = 1e-12
    body = abs(latest_k["close"] - latest_k["open"])
    f5_body_ratio = round(body / (candle_range + eps), 4)

    upper_wick = latest_k["high"] - max(latest_k["open"], latest_k["close"])
    lower_wick = min(latest_k["open"], latest_k["close"]) - latest_k["low"]
    f5_wick_imbalance = round((upper_wick - lower_wick) / (candle_range + eps), 4)

    # ── Per-minute factor time series for charting ───────────────────────
    factor_series = _build_factor_series(window_klines, atr_lookback, vol_lookback)

    result = {
        "f1_momentum": f1_momentum,
        "f2_acceleration": f2_acceleration,
        "f2_consistent": f2_consistent,
        "f3_vol_norm": f3_vol_norm,
        "f3_atr_ratio": round(atr_ratio, 8),
        "f4_volume_z": f4_volume_z,
        "f4_volume_dir": f4_volume_dir,
        "f5_body_ratio": f5_body_ratio,
        "f5_wick_imbalance": f5_wick_imbalance,
        "factor_series": factor_series,
    }

    # ── Composite prediction ─────────────────────────────────────────────
    result["prediction"] = predict_btc_direction(result)

    return result


def _build_factor_series(
    klines: list[dict],
    atr_lookback: int = 20,
    vol_lookback: int = 20,
) -> list[dict]:
    """Build per-minute factor values for time-series charting."""
    series: list[dict] = []
    trs: list[float] = []
    volumes: list[float] = []

    for i, k in enumerate(klines):
        high_low = k["high"] - k["low"]
        if i > 0:
            prev_close = klines[i - 1]["close"]
            tr = max(high_low, abs(k["high"] - prev_close), abs(k["low"] - prev_close))
        else:
            tr = high_low
        trs.append(tr)
        volumes.append(k["volume"])

        # ATR ratio
        atr_n = min(atr_lookback, len(trs))
        atr_val = sum(trs[-atr_n:]) / atr_n
        mid_p = (k["open"] + k["close"]) / 2
        atr_ratio = round(atr_val / mid_p, 8) if mid_p > 0 else 0.0

        # Volume z-score
        vol_n = min(vol_lookback, len(volumes))
        vol_slice = volumes[-vol_n:]
        vol_mean = sum(vol_slice) / len(vol_slice)
        vol_std = math.sqrt(sum((v - vol_mean) ** 2 for v in vol_slice) / len(vol_slice)) if len(vol_slice) > 1 else 1.0
        vol_z = round((k["volume"] - vol_mean) / vol_std, 4) if vol_std > 1e-12 else 0.0

        # Body ratio & wick imbalance
        eps = 1e-12
        candle_range = k["high"] - k["low"]
        body = abs(k["close"] - k["open"])
        body_ratio = round(body / (candle_range + eps), 4)
        upper_wick = k["high"] - max(k["open"], k["close"])
        lower_wick = min(k["open"], k["close"]) - k["low"]
        wick_imb = round((upper_wick - lower_wick) / (candle_range + eps), 4)

        # Cumulative momentum from first kline
        first_open = klines[0]["open"]
        momentum = round((k["open"] - first_open) / first_open, 8) if first_open > 0 else 0.0

        series.append({
            "time_ms": k["open_time"],
            "atr_ratio": atr_ratio,
            "vol_z": vol_z,
            "body_ratio": body_ratio,
            "wick_imb": wick_imb,
            "momentum": momentum,
        })

    return series


def _empty_factors() -> dict:
    """Return zeroed factor dict when kline data is insufficient."""
    return {
        "f1_momentum": 0.0,
        "f2_acceleration": 0.0,
        "f2_consistent": 0,
        "f3_vol_norm": 0.0,
        "f3_atr_ratio": 0.0,
        "f4_volume_z": 0.0,
        "f4_volume_dir": 0.0,
        "f5_body_ratio": 0.0,
        "f5_wick_imbalance": 0.0,
        "factor_series": [],
        "prediction": _empty_prediction(),
    }


# ── Composite Prediction ─────────────────────────────────────────────────────
#
# Combines all P0 factors into a single probability of BTC price rising
# after the second window ends (right-side entry signal).
#
# Model: Logistic scoring via sigmoid
#
#   raw_score = w1·f1_dir + w2·f2_acc + w3·f2_con + w4·f3_vnorm
#              + w5·f4_vdir + w6·f5_body + w7·f5_wick
#
# where:
#   f1_dir   = sign(f1_momentum) · min(|f1_momentum| / ATR_ratio, 3)
#              → direction-aware, ATR-clipped momentum (-3 ~ +3)
#   f2_acc   = tanh(f2_acceleration / ATR_ratio)
#              → acceleration normalised to (-1, +1)
#   f2_con   = f2_consistent                     (0 or 1)
#   f3_vnorm = tanh(f3_vol_norm)                 (-1 ~ +1)
#   f4_vdir  = tanh(f4_volume_dir)               (-1 ~ +1)
#   f5_body  = f5_body_ratio - 0.5               (-0.5 ~ +0.5)
#   f5_wick  = -f5_wick_imbalance                (flip: upper wick pressure → bearish)
#
#   P(up) = sigmoid(raw_score) = 1 / (1 + exp(-raw_score))
#
# Default weights (prior, tunable via walk-forward):
#   w1=0.35  w2=0.15  w3=0.20  w4=0.15  w5=0.15  w6=0.05  w7=0.05
#   bias = -0.05 (slight bearish tilt to penalise low-conviction entries)
#
# Confidence bands:
#   |P(up) - 0.5| < 0.10  → low confidence (coin-flip zone)
#   |P(up) - 0.5| ≥ 0.25  → high confidence

# Tunable default weights
_PRED_W = {
    "w1": 0.35,    # momentum direction
    "w2": 0.15,    # acceleration
    "w3": 0.20,    # direction consistency bonus
    "w4": 0.15,    # volatility-normalised momentum
    "w5": 0.15,    # volume-direction coupling
    "w6": 0.05,    # candle body decisiveness
    "w7": 0.05,    # wick imbalance (inverted)
    "bias": -0.05, # slight bearish prior
}


def predict_btc_direction(factors: dict) -> dict:
    """Combine P0 factors into a probability prediction for BTC direction.

    Returns dict with:
      prob_up        – probability of price rising (0~1)
      prob_down      – 1 - prob_up
      raw_score      – pre-sigmoid composite score
      confidence     – "high" | "medium" | "low"
      signal         – "bullish" | "bearish" | "neutral"
      components     – per-factor weighted contribution breakdown
      formula        – human-readable formula string
    """
    f1 = factors.get("f1_momentum", 0.0)
    f2_acc = factors.get("f2_acceleration", 0.0)
    f2_con = factors.get("f2_consistent", 0)
    f3_vn = factors.get("f3_vol_norm", 0.0)
    f3_atr = factors.get("f3_atr_ratio", 0.0)
    f4_vd = factors.get("f4_volume_dir", 0.0)
    f5_br = factors.get("f5_body_ratio", 0.0)
    f5_wi = factors.get("f5_wick_imbalance", 0.0)

    w = _PRED_W

    # Normalise inputs to bounded ranges
    atr_safe = max(f3_atr, 1e-8)
    x1 = _sign(f1) * min(abs(f1) / atr_safe, 3.0)  # (-3, +3)
    x2 = math.tanh(f2_acc / atr_safe)                # (-1, +1)
    x3 = float(f2_con)                               # 0 or 1
    x4 = math.tanh(f3_vn)                            # (-1, +1)
    x5 = math.tanh(f4_vd)                            # (-1, +1)
    x6 = f5_br - 0.5                                 # (-0.5, +0.5)
    x7 = -f5_wi                                      # flip sign

    # Weighted sum
    c1 = w["w1"] * x1
    c2 = w["w2"] * x2
    c3 = w["w3"] * x3
    c4 = w["w4"] * x4
    c5 = w["w5"] * x5
    c6 = w["w6"] * x6
    c7 = w["w7"] * x7
    raw_score = c1 + c2 + c3 + c4 + c5 + c6 + c7 + w["bias"]

    # Sigmoid
    prob_up = 1.0 / (1.0 + math.exp(-_clamp(raw_score, -10, 10)))
    prob_down = 1.0 - prob_up

    # Confidence & signal
    deviation = abs(prob_up - 0.5)
    if deviation >= 0.25:
        confidence = "high"
    elif deviation >= 0.10:
        confidence = "medium"
    else:
        confidence = "low"

    if prob_up >= 0.60:
        signal = "bullish"
    elif prob_up <= 0.40:
        signal = "bearish"
    else:
        signal = "neutral"

    components = {
        "momentum_dir":      round(c1, 6),
        "acceleration":      round(c2, 6),
        "consistency_bonus": round(c3, 6),
        "vol_norm":          round(c4, 6),
        "volume_dir":        round(c5, 6),
        "body_decisive":     round(c6, 6),
        "wick_pressure":     round(c7, 6),
        "bias":              w["bias"],
    }

    formula = (
        f"S = {w['w1']}·f1_dir({x1:+.3f}) + {w['w2']}·f2_acc({x2:+.3f}) "
        f"+ {w['w3']}·f2_con({x3:.0f}) + {w['w4']}·f3_vnorm({x4:+.3f}) "
        f"+ {w['w5']}·f4_vdir({x5:+.3f}) + {w['w6']}·f5_body({x6:+.3f}) "
        f"+ {w['w7']}·f5_wick({x7:+.3f}) + bias({w['bias']:+.2f}) "
        f"= {raw_score:+.4f} → P(up) = σ({raw_score:+.4f}) = {prob_up:.4f}"
    )

    return {
        "prob_up": round(prob_up, 6),
        "prob_down": round(prob_down, 6),
        "raw_score": round(raw_score, 6),
        "confidence": confidence,
        "signal": signal,
        "components": components,
        "formula": formula,
    }


def _empty_prediction() -> dict:
    """Return default neutral prediction when factors unavailable."""
    return {
        "prob_up": 0.5,
        "prob_down": 0.5,
        "raw_score": 0.0,
        "confidence": "low",
        "signal": "neutral",
        "components": {},
        "formula": "N/A — insufficient data",
    }


def _sign(x: float) -> float:
    return 1.0 if x > 0 else (-1.0 if x < 0 else 0.0)


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))
