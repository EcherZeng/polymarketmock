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
    atr_lookback: int = 20,
    vol_lookback: int = 20,
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
    factors = compute_btc_factors(klines, start_ms, target_w1_ms, target_w2_ms, a1, a2, atr_lookback, vol_lookback)

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
    """Compute 5 P0-level factors from BTC kline data.

    IMPORTANT — look-ahead bias guard:
    A kline with open_time=T contains data for the interval [T, T+interval).
    Its open price is known at T, but high/low/close/volume are only known
    after the interval closes.  To avoid look-ahead bias we **exclude** any
    kline whose open_time >= target_w2_ms.

    Factors (all raw decimals, not percentages):
      f1_momentum       – directional momentum: a1 + a2
      f2_acceleration   – momentum acceleration: |a2| - |a1|  (>0 means accelerating)
      f2_consistent     – direction streak: consecutive same-direction closes at window end
      f3_vol_norm       – volatility-normalized momentum: (a1+a2) / rolling ATR ratio
      f4_volume_z       – VWAP deviation: (last_close - VWAP) / VWAP
      f4_volume_dir     – volume ratio: total volume in w2 / total volume in w1
      f5_body_ratio     – window-averaged candle body / range ratio (0~1)
      f5_wick_imbalance – window-averaged (upper_wick - lower_wick) / range (-1~1)

    Also returns per-candle factor time series for charting:
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

    # ── f2: Acceleration & direction streak ──────────────────────────────
    f2_acceleration = round(abs(a2) - abs(a1), 8)
    f2_consistent = _count_streak(window_klines)

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

    # ── f4: VWAP deviation & volume ratio ────────────────────────────────
    total_cv = sum(k["close"] * k["volume"] for k in window_klines)
    total_vol = sum(k["volume"] for k in window_klines)
    vwap = total_cv / total_vol if total_vol > 1e-12 else window_klines[-1]["close"]
    last_close = window_klines[-1]["close"]
    f4_volume_z = round((last_close - vwap) / vwap, 8) if vwap > 0 else 0.0

    # Volume ratio: w2 window total volume / w1 window total volume
    w1_klines = [k for k in window_klines if k["open_time"] < target_w1_ms]
    w2_klines = [k for k in window_klines if k["open_time"] >= target_w1_ms]
    vol_w1 = sum(k["volume"] for k in w1_klines) if w1_klines else 1e-12
    vol_w2 = sum(k["volume"] for k in w2_klines) if w2_klines else 1e-12
    f4_volume_dir = round(vol_w2 / vol_w1, 4) if vol_w1 > 1e-12 else 1.0

    # ── f5: Candle structure — window-averaged ───────────────────────────
    eps = 1e-12
    n_avg = min(vol_lookback, len(window_klines))
    avg_klines = window_klines[-n_avg:]
    body_ratios: list[float] = []
    wick_imbs: list[float] = []
    for k in avg_klines:
        cr = k["high"] - k["low"]
        body_ratios.append(abs(k["close"] - k["open"]) / (cr + eps))
        uw = k["high"] - max(k["open"], k["close"])
        lw = min(k["open"], k["close"]) - k["low"]
        wick_imbs.append((uw - lw) / (cr + eps))
    f5_body_ratio = round(sum(body_ratios) / len(body_ratios), 4) if body_ratios else 0.0
    f5_wick_imbalance = round(sum(wick_imbs) / len(wick_imbs), 4) if wick_imbs else 0.0

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
    remaining_min = (target_w2_ms - start_ms) / 60_000  # total session observed
    # Assume a typical 15-min session; remaining = session_len - observed
    # The caller doesn't pass session length, so we estimate remaining as
    # the same duration as window_2 offset from start (conservative).
    # For w1=5, w2=10, remaining ~5 min.  Caller can override via kwarg later.
    result["prediction"] = predict_btc_direction(result, window_klines, remaining_min)

    return result


def _build_factor_series(
    klines: list[dict],
    atr_lookback: int = 20,
    vol_lookback: int = 20,
) -> list[dict]:
    """Build per-candle factor values for time-series charting."""
    series: list[dict] = []
    trs: list[float] = []
    cum_cv = 0.0
    cum_vol = 0.0
    body_window: list[float] = []
    wick_window: list[float] = []

    for i, k in enumerate(klines):
        high_low = k["high"] - k["low"]
        if i > 0:
            prev_close = klines[i - 1]["close"]
            tr = max(high_low, abs(k["high"] - prev_close), abs(k["low"] - prev_close))
        else:
            tr = high_low
        trs.append(tr)

        # ATR ratio
        atr_n = min(atr_lookback, len(trs))
        atr_val = sum(trs[-atr_n:]) / atr_n
        mid_p = (k["open"] + k["close"]) / 2
        atr_ratio = round(atr_val / mid_p, 8) if mid_p > 0 else 0.0

        # Rolling VWAP deviation
        cum_cv += k["close"] * k["volume"]
        cum_vol += k["volume"]
        vwap = cum_cv / cum_vol if cum_vol > 1e-12 else k["close"]
        vol_z = round((k["close"] - vwap) / vwap, 8) if vwap > 0 else 0.0

        # Rolling-average body ratio & wick imbalance
        eps = 1e-12
        candle_range = k["high"] - k["low"]
        body_window.append(abs(k["close"] - k["open"]) / (candle_range + eps))
        if len(body_window) > vol_lookback:
            body_window.pop(0)
        body_ratio = round(sum(body_window) / len(body_window), 4)

        uw = k["high"] - max(k["open"], k["close"])
        lw = min(k["open"], k["close"]) - k["low"]
        wick_window.append((uw - lw) / (candle_range + eps))
        if len(wick_window) > vol_lookback:
            wick_window.pop(0)
        wick_imb = round(sum(wick_window) / len(wick_window), 4)

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


# ── Composite Prediction (CDF model) ─────────────────────────────────────────
#
# Predicts: P(P_end > P_0) — probability that BTC price at session end is
# higher than at session start (minute 0).
#
# Core insight: at the second window boundary (W2), BTC has already displaced
# by Δ_W2 = P_W2 − P_0 relative to P_0.  For the price to "flip" (end on
# the opposite side of P_0), the remaining minutes must reverse the entire Δ.
#
# Uses **Student-t(df=4)** instead of normal distribution to account for BTC's
# heavy-tailed 1-min return distribution (fat tails, volatility clustering).
#
#   σ_remain = σ₁ · √(remaining_minutes)
#   z_base   = Δ_W2 / σ_remain         (displacement in σ-units)
#
# Factor-adjusted model — P0 factors modify σ_remain via α ∈ (0.5, 1.5):
#
#   α = 1 − β₁·accel − β₂·streak − β₃·vwap_coupling + β₄·wick_pressure
#
#   z_adj = Δ_W2 / (σ_remain · α)
#   P(up) = F_t(z_adj; df=4)     where F_t = Student-t CDF
#
# Student-t(4) gives heavier tails than normal: ≈3.7% probability beyond ±3σ
# (vs 0.3% for normal), better reflecting BTC's actual return distribution.

# Default factor adjustment weights (prior):
_ADJ_BETA = {
    "accel":      0.10,   # |a2|>|a1| → trend sticky → shrink σ
    "consistent": 0.15,   # streak > 0 → same dir     → shrink σ
    "vol_couple": 0.10,   # VWAP confirms direction   → shrink σ
    "wick_press": 0.10,   # wick pressure             → expand σ
    "body_ratio": 0.05,   # strong body               → shrink σ
}

# Student-t degrees of freedom — 4 gives heavier tails than normal,
# capturing BTC's kurtosis in 1-min returns without being too extreme.
_STUDENT_T_DF = 4.0


def _normal_cdf(x: float) -> float:
    """Standard normal CDF via the complementary error function."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _reg_inc_beta(x: float, a: float, b: float, max_iter: int = 200) -> float:
    """Regularized incomplete beta function I_x(a,b) via Lentz continued fraction.

    Implementation follows Numerical Recipes §6.4 (betacf).
    """
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    # Use symmetry: I_x(a,b) = 1 - I_{1-x}(b,a) when x > (a+1)/(a+b+2)
    if x > (a + 1.0) / (a + b + 2.0):
        return 1.0 - _reg_inc_beta(1.0 - x, b, a, max_iter)

    ln_beta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    front = math.exp(a * math.log(x) + b * math.log(1.0 - x) - ln_beta) / a

    TINY = 1e-30
    c = 1.0
    d = 1.0 - (a + b) * x / (a + 1.0)
    if abs(d) < TINY:
        d = TINY
    d = 1.0 / d
    h = d

    for m in range(1, max_iter + 1):
        m2 = 2 * m
        # Even step
        aa = m * (b - m) * x / ((a + m2 - 1.0) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < TINY:
            d = TINY
        c = 1.0 + aa / c
        if abs(c) < TINY:
            c = TINY
        d = 1.0 / d
        h *= d * c

        # Odd step
        aa = -(a + m) * (a + b + m) * x / ((a + m2) * (a + m2 + 1.0))
        d = 1.0 + aa * d
        if abs(d) < TINY:
            d = TINY
        c = 1.0 + aa / c
        if abs(c) < TINY:
            c = TINY
        d = 1.0 / d
        delta = d * c
        h *= delta

        if abs(delta - 1.0) < 1e-12:
            break

    return front * h


def _student_t_cdf(t: float, df: float = 4.0) -> float:
    """CDF of Student-t distribution via regularized incomplete beta."""
    if df <= 0:
        return _normal_cdf(t)
    x = df / (df + t * t)
    ib = _reg_inc_beta(x, df / 2.0, 0.5)
    if t >= 0:
        return 1.0 - 0.5 * ib
    else:
        return 0.5 * ib


def predict_btc_direction(
    factors: dict,
    window_klines: list[dict],
    observed_min: float,
    session_total_min: float = 15.0,
) -> dict:
    """Predict P(P_end > P_0) using displacement / volatility CDF model.

    Args:
        factors:          computed P0 factor dict
        window_klines:    klines within [start, W2) — used to estimate σ₁
        observed_min:     minutes already observed (W2 offset from start)
        session_total_min: assumed total session length in minutes

    Returns dict with:
      prob_up, prob_down, raw_score (z_adj), confidence, signal,
      components (breakdown), formula (human-readable)
    """
    remaining_min = max(session_total_min - observed_min, 1.0)

    # ── Estimate 1-min volatility σ₁ from observed klines ────────────────
    if len(window_klines) >= 2:
        log_returns: list[float] = []
        for i in range(1, len(window_klines)):
            prev_o = window_klines[i - 1]["open"]
            cur_o = window_klines[i]["open"]
            if prev_o > 0 and cur_o > 0:
                log_returns.append(math.log(cur_o / prev_o))
        if log_returns:
            mean_r = sum(log_returns) / len(log_returns)
            var_r = sum((r - mean_r) ** 2 for r in log_returns) / len(log_returns)
            sigma_1 = math.sqrt(var_r) if var_r > 0 else 1e-8
        else:
            sigma_1 = 1e-8
    else:
        sigma_1 = 1e-8

    sigma_remain = sigma_1 * math.sqrt(remaining_min)

    # ── Displacement Δ_W2 = (P_W2 - P_0) / P_0 ─────────────────────────
    delta_w2 = factors.get("f1_momentum", 0.0)  # = a1 + a2 ≈ (P_W2 - P_0)/P_0

    # ── Factor-adjusted α ────────────────────────────────────────────────
    f2_acc = factors.get("f2_acceleration", 0.0)
    f2_con = factors.get("f2_consistent", 0)
    f4_vz = factors.get("f4_volume_z", 0.0)     # VWAP deviation
    f4_vr = factors.get("f4_volume_dir", 1.0)    # volume ratio w2/w1
    f5_wi = factors.get("f5_wick_imbalance", 0.0)
    f5_br = factors.get("f5_body_ratio", 0.0)
    f3_atr = factors.get("f3_atr_ratio", 0.0)

    b = _ADJ_BETA
    atr_safe = max(f3_atr, 1e-8)

    # Normalise adjustments: positive = supports trend continuation
    accel_norm = math.tanh(f2_acc / atr_safe) * _sign(delta_w2)
    # Streak: tanh(streak/3) maps 0→0, 3→0.76, 5→0.93
    consist_val = math.tanh(float(f2_con) / 3.0)
    # VWAP deviation: price above VWAP in trend direction
    vwap_norm = math.tanh(f4_vz / atr_safe) * _sign(delta_w2)
    # Volume ratio: log(w2/w1) > 0 means increasing volume in trend window
    vol_ratio_norm = math.tanh(math.log(max(f4_vr, 0.01))) * _sign(delta_w2)
    vol_couple_norm = (vwap_norm + vol_ratio_norm) / 2.0
    wick_press_norm = f5_wi * _sign(delta_w2)
    body_norm = (f5_br - 0.5) * _sign(delta_w2)

    # α < 1 → trend sticky (lower effective σ → higher |z|)
    # α > 1 → reversal risk higher
    alpha_raw = (
        1.0
        - b["accel"] * accel_norm
        - b["consistent"] * consist_val
        - b["vol_couple"] * vol_couple_norm
        + b["wick_press"] * wick_press_norm
        - b["body_ratio"] * body_norm
    )
    alpha = max(0.5, min(1.5, alpha_raw))

    # ── z-score and CDF ──────────────────────────────────────────────────
    sigma_adj = sigma_remain * alpha
    z_adj = delta_w2 / sigma_adj if sigma_adj > 1e-12 else 0.0
    z_adj = max(-6.0, min(6.0, z_adj))

    prob_up = _student_t_cdf(z_adj, _STUDENT_T_DF)
    prob_down = 1.0 - prob_up

    # ── Confidence & signal ──────────────────────────────────────────────
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

    # ── Component breakdown ──────────────────────────────────────────────
    z_base = delta_w2 / sigma_remain if sigma_remain > 1e-12 else 0.0
    components = {
        "delta_w2":       round(delta_w2, 8),
        "sigma_1":        round(sigma_1, 8),
        "sigma_remain":   round(sigma_remain, 8),
        "alpha":          round(alpha, 4),
        "z_base":         round(z_base, 4),
        "z_adjusted":     round(z_adj, 4),
        "adj_accel":      round(-b["accel"] * accel_norm, 4),
        "adj_consistent": round(-b["consistent"] * consist_val, 4),
        "adj_vol":        round(-b["vol_couple"] * vol_couple_norm, 4),
        "adj_wick":       round(b["wick_press"] * wick_press_norm, 4),
        "adj_body":       round(-b["body_ratio"] * body_norm, 4),
    }

    formula = (
        f"Δ_W2 = {delta_w2:+.6f}  |  σ₁ = {sigma_1:.6f}  |  "
        f"σ_remain = σ₁·√{remaining_min:.0f} = {sigma_remain:.6f}\n"
        f"z_base = Δ_W2/σ_remain = {z_base:+.4f}  |  "
        f"α = {alpha:.4f} (因子调节)\n"
        f"z_adj = z_base/α = {z_adj:+.4f}  →  "
        f"P(P_end > P_0) = F_t({z_adj:+.4f}; df={_STUDENT_T_DF:.0f}) = {prob_up:.4f}"
    )

    return {
        "prob_up": round(prob_up, 6),
        "prob_down": round(prob_down, 6),
        "raw_score": round(z_adj, 6),
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


def _count_streak(klines: list[dict]) -> int:
    """Count consecutive same-direction (close vs open) candles from the end."""
    if not klines:
        return 0
    streak = 0
    last_dir = 1 if klines[-1]["close"] >= klines[-1]["open"] else -1
    for k in reversed(klines):
        d = 1 if k["close"] >= k["open"] else -1
        if d == last_dir:
            streak += 1
        else:
            break
    return streak


# ── High-density analysis (1s klines, on-demand) ─────────────────────────────

async def analyze_btc_hd(
    start_ts: str,
    end_ts: str,
    window_1_min: int = 5,
    window_2_min: int = 10,
    min_momentum: float = 0.001,
) -> dict:
    """High-density BTC factor analysis using 1s klines from Binance.

    Called on-demand from the detail page — provides 60x more data points
    than the default 1m klines used during backtest, giving statistically
    robust factor estimates.
    """
    klines = await fetch_btc_klines(start_ts, end_ts, interval="1s")
    if not klines:
        return {"error": "no_klines", "kline_count": 0, "trend": None}

    # Scale lookbacks for 1s data: 300 bars = 5 min of history
    hd_lookback = 300
    trend = compute_btc_trend(
        klines, start_ts, window_1_min, window_2_min, min_momentum,
        atr_lookback=hd_lookback, vol_lookback=hd_lookback,
    )

    return {
        "interval": "1s",
        "kline_count": len(klines),
        "trend": trend,
    }


# ── Rolling Exit Factor Analysis ─────────────────────────────────────────────
#
# On-demand deep analysis: given a backtest's trade history and BTC 1s klines
# during the holding period, compute rolling top-3 factors (consistent streak,
# acceleration, volume coupling) and derive a composite exit signal timeline.
#
# Weights (normalised from _ADJ_BETA top-3):
#   consistent  0.15 / 0.35 ≈ 0.4286
#   accel       0.10 / 0.35 ≈ 0.2857
#   vol_couple  0.10 / 0.35 ≈ 0.2857
#
# composite_score ∈ [-1, 1]:
#   > 0.3  → hold   (100%)
#   0~0.3  → reduce ( 70%)
#  -0.3~0  → reduce ( 40%)
#   ≤-0.3  → exit   (  0%)

_EXIT_WEIGHTS = {
    "consistent": 0.4286,
    "accel":      0.2857,
    "vol_couple": 0.2857,
}

_EXIT_THRESHOLDS = [
    (0.3,  "hold",   1.0),
    (0.0,  "reduce", 0.7),
    (-0.3, "reduce", 0.4),
]
# Below -0.3 → exit, 0%


def _score_to_action(score: float) -> tuple[str, float]:
    """Map composite score to (action, suggested_position_pct)."""
    for threshold, action, pct in _EXIT_THRESHOLDS:
        if score > threshold:
            return action, pct
    return "exit", 0.0


def compute_rolling_exit_factors(
    klines: list[dict],
    hold_start_ms: int,
    hold_end_ms: int,
    entry_direction: float,
    lookback: int = 60,
) -> list[dict]:
    """Compute per-second exit factor timeline from 1s BTC klines.

    For every 1s kline in the holding period, look back *lookback* seconds
    and compute the top-3 factors over that window.  This gives a decision
    point at every second — no blind spots.

    Args:
        klines:          1s BTC/USDT klines covering the holding period
        hold_start_ms:   epoch ms of first BUY fill
        hold_end_ms:     epoch ms of holding end (slug_end or SELL fill)
        entry_direction: +1.0 if entry was bullish (expecting BTC up),
                         -1.0 if bearish; used to align factor signs
        lookback:        number of 1s klines to look back (default 60)

    Returns:
        List of ExitFactorPoint dicts, one per second.
    """
    if not klines or len(klines) < 2:
        return []

    # Filter klines to holding period
    hold_klines = [k for k in klines if hold_start_ms <= k["open_time"] <= hold_end_ms]
    if len(hold_klines) < 2:
        return []

    lookback_ms = lookback * 1000
    timeline: list[dict] = []

    # Evaluate at every kline after the first *lookback* seconds
    for i, cur in enumerate(hold_klines):
        cursor_ms = cur["open_time"]
        # Need at least some history; skip the very first kline
        if cursor_ms <= hold_start_ms:
            continue

        # Collect lookback window: klines in (cursor - lookback_ms, cursor]
        win = [k for k in hold_klines if (cursor_ms - lookback_ms) < k["open_time"] <= cursor_ms]
        if len(win) < 2:
            continue

        # ── Factor 1: Direction streak ───────────────────────────────────
        streak = _count_streak(win)
        last_dir = 1.0 if win[-1]["close"] >= win[-1]["open"] else -1.0
        streak_aligned = streak * (1.0 if last_dir == entry_direction else -1.0)
        streak_norm = math.tanh(streak_aligned / 3.0)

        # ── Factor 2: Momentum acceleration ──────────────────────────────
        mid_idx = len(win) // 2
        sub_w1 = win[:mid_idx]
        sub_w2 = win[mid_idx:]
        if sub_w1 and sub_w2 and sub_w1[0]["open"] > 0 and sub_w1[-1]["open"] > 0 and sub_w2[-1]["open"] > 0:
            a1 = (sub_w1[-1]["close"] - sub_w1[0]["open"]) / sub_w1[0]["open"]
            a2 = (sub_w2[-1]["close"] - sub_w2[0]["open"]) / sub_w2[0]["open"]
            raw_accel = abs(a2) - abs(a1)
            accel_sign = 1.0 if (a2 * entry_direction) > 0 else -1.0
            accel_norm = math.tanh(raw_accel * 100) * accel_sign
        else:
            raw_accel = 0.0
            accel_norm = 0.0

        # ── Factor 3: Volume coupling (VWAP deviation + volume ratio) ────
        total_cv = sum(k["close"] * k["volume"] for k in win)
        total_vol = sum(k["volume"] for k in win)
        vwap = total_cv / total_vol if total_vol > 1e-12 else win[-1]["close"]
        vwap_dev = (win[-1]["close"] - vwap) / vwap if vwap > 0 else 0.0
        vwap_aligned = vwap_dev * entry_direction

        vol_h1 = sum(k["volume"] for k in sub_w1) if sub_w1 else 1e-12
        vol_h2 = sum(k["volume"] for k in sub_w2) if sub_w2 else 1e-12
        vol_ratio = vol_h2 / vol_h1 if vol_h1 > 1e-12 else 1.0
        vol_ratio_aligned = math.tanh(math.log(max(vol_ratio, 0.01))) * entry_direction

        vol_coupling_norm = (math.tanh(vwap_aligned * 100) + vol_ratio_aligned) / 2.0

        # ── Composite score ──────────────────────────────────────────────
        w = _EXIT_WEIGHTS
        score = (
            w["consistent"] * streak_norm
            + w["accel"] * accel_norm
            + w["vol_couple"] * vol_coupling_norm
        )
        score = max(-1.0, min(1.0, score))

        action, position_pct = _score_to_action(score)

        timeline.append({
            "time_ms": cursor_ms,
            "streak": streak,
            "streak_norm": round(streak_norm, 4),
            "acceleration": round(raw_accel, 8),
            "accel_norm": round(accel_norm, 4),
            "vol_coupling": round(vwap_dev, 8),
            "vol_coupling_norm": round(vol_coupling_norm, 4),
            "composite_score": round(score, 4),
            "action": action,
            "suggested_position_pct": position_pct,
        })

    return timeline


def simulate_factor_exit_equity(
    timeline: list[dict],
    entry_price: float,
    entry_qty: float,
    initial_balance: float,
    price_curve: list[dict],
    token_id: str,
) -> dict:
    """Simulate equity if factor-based exit was followed.

    Walks the factor timeline and whenever suggested_position_pct drops,
    simulates partial sells at the Poly price at that time.

    Returns:
        {
            simulated_equity_curve: [{time_ms, equity, position_pct}],
            final_equity: float,
            first_reduce_ts: int | None,
            first_exit_ts: int | None,
        }
    """
    if not timeline or entry_qty <= 0:
        return {
            "simulated_equity_curve": [],
            "final_equity": initial_balance,
            "first_reduce_ts": None,
            "first_exit_ts": None,
        }

    # Build a time→price lookup from price_curve (Poly prices)
    price_by_ms: dict[int, float] = {}
    for p in price_curve:
        if p.get("token_id") == token_id:
            ts = p.get("timestamp", "")
            if ts:
                ms = _iso_to_ms(ts)
                price_by_ms[ms] = p.get("anchor_price", 0) or p.get("mid_price", 0)

    # Sorted time keys for nearest-price lookup
    sorted_price_times = sorted(price_by_ms.keys())

    def _get_price_at(target_ms: int) -> float:
        """Get Poly price closest to target_ms."""
        if not sorted_price_times:
            return entry_price
        # Binary search for nearest
        lo, hi = 0, len(sorted_price_times) - 1
        while lo < hi:
            mid = (lo + hi) // 2
            if sorted_price_times[mid] < target_ms:
                lo = mid + 1
            else:
                hi = mid
        best = sorted_price_times[lo]
        if lo > 0:
            prev = sorted_price_times[lo - 1]
            if abs(prev - target_ms) < abs(best - target_ms):
                best = prev
        return price_by_ms.get(best, entry_price)

    balance = initial_balance - entry_price * entry_qty  # after buy
    remaining_qty = entry_qty
    current_pct = 1.0
    sim_curve: list[dict] = []
    first_reduce_ts: int | None = None
    first_exit_ts: int | None = None

    for point in timeline:
        t_ms = point["time_ms"]
        new_pct = point["suggested_position_pct"]

        if new_pct < current_pct and remaining_qty > 0:
            # Sell (current_pct - new_pct) fraction of original qty
            sell_frac = current_pct - new_pct
            sell_qty = min(sell_frac * entry_qty, remaining_qty)
            sell_price = _get_price_at(t_ms)
            balance += sell_qty * sell_price
            remaining_qty -= sell_qty
            remaining_qty = max(0.0, remaining_qty)

            if first_reduce_ts is None and new_pct < 1.0:
                first_reduce_ts = t_ms
            if first_exit_ts is None and new_pct <= 0.0:
                first_exit_ts = t_ms

        current_pct = new_pct
        current_price = _get_price_at(t_ms)
        equity = balance + remaining_qty * current_price

        sim_curve.append({
            "time_ms": t_ms,
            "equity": round(equity, 6),
            "position_pct": new_pct,
        })

    # Final equity: remaining position at last known price
    if sim_curve:
        final_eq = sim_curve[-1]["equity"]
    else:
        final_eq = initial_balance

    return {
        "simulated_equity_curve": sim_curve,
        "final_equity": round(final_eq, 6),
        "first_reduce_ts": first_reduce_ts,
        "first_exit_ts": first_exit_ts,
    }
