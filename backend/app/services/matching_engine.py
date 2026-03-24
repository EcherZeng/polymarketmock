"""Matching engine — simulates order execution against real CLOB orderbook depth."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.models.trading import (
    EstimateResult,
    OrderRequest,
    OrderResult,
    OrderSide,
    OrderStatus,
    OrderType,
)
from app.services.polymarket_proxy import get_midpoint, get_orderbook_raw
from app.storage import redis_store
from app.utils.price_impact import calculate_slippage, calculate_vwap_from_levels


async def estimate_order(req: EstimateResult | OrderRequest, token_id: str | None = None) -> EstimateResult:
    """Estimate execution without actually placing order."""
    tid = token_id or req.token_id
    book = await get_orderbook_raw(tid)
    mid = await get_midpoint(tid)

    if req.side == OrderSide.BUY:
        levels = book.get("asks", [])
    else:
        levels = book.get("bids", [])

    filled, avg_price, total_cost = calculate_vwap_from_levels(levels, req.amount)
    slippage = calculate_slippage(mid, avg_price, req.side.value) if avg_price > 0 else 0.0

    # Complementary token info
    comp_token_id = ""
    comp_price = 0.0
    try:
        from app.storage.redis_store import get_token_market_info
        market_info = await get_token_market_info(tid)
        if market_info:
            token_ids = market_info.get("clobTokenIds", [])
            if isinstance(token_ids, list) and len(token_ids) == 2:
                comp_token_id = token_ids[1] if token_ids[0] == tid else token_ids[0]
                if comp_token_id:
                    try:
                        comp_price = round(await get_midpoint(comp_token_id), 6)
                    except Exception:
                        comp_price = round(1.0 - mid, 6)
        if not comp_token_id:
            comp_price = round(1.0 - mid, 6)
    except Exception:
        comp_price = round(1.0 - mid, 6)

    prob_price = avg_price if avg_price > 0 else mid
    if req.side == OrderSide.BUY:
        profit_per_share = round(1.0 - prob_price, 6)
        loss_per_share = round(prob_price, 6)
    else:
        profit_per_share = round(prob_price, 6)
        loss_per_share = round(1.0 - prob_price, 6)

    return EstimateResult(
        token_id=tid,
        side=req.side,
        estimated_avg_price=round(avg_price, 6),
        estimated_slippage_pct=round(slippage, 4),
        estimated_total_cost=round(total_cost, 6),
        orderbook_depth_available=round(filled, 6),
        probability_price=round(prob_price, 6),
        potential_profit_per_share=profit_per_share,
        potential_loss_per_share=loss_per_share,
        complementary_price=comp_price,
        complementary_token_id=comp_token_id,
    )


async def execute_market_order(req: OrderRequest) -> OrderResult:
    """Execute a market order against live orderbook depth."""
    order_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    book = await get_orderbook_raw(req.token_id)
    mid = await get_midpoint(req.token_id)

    if req.side == OrderSide.BUY:
        levels = book.get("asks", [])
    else:
        levels = book.get("bids", [])

    filled_amount, avg_price, total_cost = calculate_vwap_from_levels(levels, req.amount)
    slippage = calculate_slippage(mid, avg_price, req.side.value) if avg_price > 0 else 0.0

    if filled_amount <= 0:
        result = OrderResult(
            order_id=order_id,
            token_id=req.token_id,
            side=req.side,
            type=OrderType.MARKET,
            status=OrderStatus.CANCELLED,
            requested_amount=req.amount,
            filled_amount=0,
            avg_price=0,
            total_cost=0,
            slippage_pct=0,
            created_at=now,
        )
        await redis_store.save_order(order_id, result.model_dump(mode="json"))
        return result

    # Validate balance / position
    if req.side == OrderSide.BUY:
        balance = await redis_store.get_balance()
        if balance < total_cost:
            result = OrderResult(
                order_id=order_id,
                token_id=req.token_id,
                side=req.side,
                type=OrderType.MARKET,
                status=OrderStatus.CANCELLED,
                requested_amount=req.amount,
                filled_amount=0,
                avg_price=0,
                total_cost=0,
                slippage_pct=0,
                created_at=now,
            )
            await redis_store.save_order(order_id, result.model_dump(mode="json"))
            return result
        await redis_store.adjust_balance(-total_cost)
        await _update_position_buy(req.token_id, filled_amount, avg_price, req.side.value)
    else:
        pos = await redis_store.get_position(req.token_id)
        if not pos or float(pos.get("shares", 0)) < filled_amount:
            result = OrderResult(
                order_id=order_id,
                token_id=req.token_id,
                side=req.side,
                type=OrderType.MARKET,
                status=OrderStatus.CANCELLED,
                requested_amount=req.amount,
                filled_amount=0,
                avg_price=0,
                total_cost=0,
                slippage_pct=0,
                created_at=now,
            )
            await redis_store.save_order(order_id, result.model_dump(mode="json"))
            return result
        await redis_store.adjust_balance(total_cost)
        await _update_position_sell(req.token_id, filled_amount, avg_price)

    status = OrderStatus.FILLED if filled_amount >= req.amount else OrderStatus.PARTIALLY_FILLED

    result = OrderResult(
        order_id=order_id,
        token_id=req.token_id,
        side=req.side,
        type=OrderType.MARKET,
        status=status,
        requested_amount=req.amount,
        filled_amount=round(filled_amount, 6),
        avg_price=round(avg_price, 6),
        total_cost=round(total_cost, 6),
        slippage_pct=round(slippage, 4),
        created_at=now,
        filled_at=now,
    )

    await redis_store.save_order(order_id, result.model_dump(mode="json"))
    # Record trade
    ts = datetime.now(timezone.utc).timestamp()
    trade = {
        "order_id": order_id,
        "token_id": req.token_id,
        "side": req.side.value,
        "type": OrderType.MARKET.value,
        "amount": round(filled_amount, 6),
        "avg_price": round(avg_price, 6),
        "total_cost": round(total_cost, 6),
        "slippage_pct": round(slippage, 4),
        "timestamp": now,
    }
    import json
    await redis_store.add_trade(ts, json.dumps(trade))

    return result


async def place_limit_order(req: OrderRequest) -> OrderResult:
    """Place a limit order (stored as pending, checked periodically)."""
    order_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    if req.price is None:
        raise ValueError("Limit order requires a price")

    # For buy limit: reserve funds
    if req.side == OrderSide.BUY:
        reserved = req.amount * req.price
        balance = await redis_store.get_balance()
        if balance < reserved:
            return OrderResult(
                order_id=order_id,
                token_id=req.token_id,
                side=req.side,
                type=OrderType.LIMIT,
                status=OrderStatus.CANCELLED,
                requested_amount=req.amount,
                filled_amount=0,
                avg_price=0,
                total_cost=0,
                slippage_pct=0,
                created_at=now,
            )
        await redis_store.adjust_balance(-reserved)

    result = OrderResult(
        order_id=order_id,
        token_id=req.token_id,
        side=req.side,
        type=OrderType.LIMIT,
        status=OrderStatus.PENDING,
        requested_amount=req.amount,
        filled_amount=0,
        avg_price=0,
        total_cost=0,
        slippage_pct=0,
        created_at=now,
    )

    order_data = result.model_dump(mode="json")
    order_data["limit_price"] = req.price
    await redis_store.save_order(order_id, order_data)
    await redis_store.save_pending_order(order_id, order_data)

    return result


async def cancel_limit_order(order_id: str) -> OrderResult | None:
    """Cancel a pending limit order and refund reserved funds."""
    order = await redis_store.get_order(order_id)
    if not order or order.get("status") != OrderStatus.PENDING.value:
        return None

    order["status"] = OrderStatus.CANCELLED.value

    # Refund reserved balance for buy limit
    if order.get("side") == OrderSide.BUY.value and order.get("limit_price"):
        refund = order["requested_amount"] * order["limit_price"]
        await redis_store.adjust_balance(refund)

    await redis_store.save_order(order_id, order)
    await redis_store.remove_pending_order(order_id)

    return OrderResult(**{k: v for k, v in order.items() if k != "limit_price"})


async def check_and_fill_limit_orders() -> None:
    """Check pending limit orders against current orderbook and fill if possible."""
    pending = await redis_store.get_pending_orders()
    for order_data in pending:
        token_id = order_data.get("token_id")
        side = order_data.get("side")
        limit_price = order_data.get("limit_price")
        amount = order_data.get("requested_amount", 0)
        order_id = order_data.get("order_id")

        if not token_id or not order_id or not limit_price:
            continue

        try:
            mid = await get_midpoint(token_id)
        except Exception:
            continue

        can_fill = False
        if side == OrderSide.BUY.value and mid <= limit_price:
            can_fill = True
        elif side == OrderSide.SELL.value and mid >= limit_price:
            can_fill = True

        if not can_fill:
            continue

        # Fill at limit price (simplified — exact limit fill)
        now = datetime.now(timezone.utc).isoformat()
        total_cost = amount * limit_price

        if side == OrderSide.BUY.value:
            # Funds already reserved at order placement
            await _update_position_buy(token_id, amount, limit_price, side)
        else:
            pos = await redis_store.get_position(token_id)
            if not pos or float(pos.get("shares", 0)) < amount:
                continue
            await redis_store.adjust_balance(total_cost)
            await _update_position_sell(token_id, amount, limit_price)

        order_data["status"] = OrderStatus.FILLED.value
        order_data["filled_amount"] = amount
        order_data["avg_price"] = limit_price
        order_data["total_cost"] = round(total_cost, 6)
        order_data["slippage_pct"] = 0
        order_data["filled_at"] = now

        await redis_store.save_order(order_id, order_data)
        await redis_store.remove_pending_order(order_id)

        import json
        ts = datetime.now(timezone.utc).timestamp()
        trade = {
            "order_id": order_id,
            "token_id": token_id,
            "side": side,
            "type": OrderType.LIMIT.value,
            "amount": amount,
            "avg_price": limit_price,
            "total_cost": round(total_cost, 6),
            "slippage_pct": 0,
            "timestamp": now,
        }
        await redis_store.add_trade(ts, json.dumps(trade))


# ── Position helpers ─────────────────────────────────────────────────────────

async def _update_position_buy(token_id: str, shares: float, price: float, side: str) -> None:
    pos = await redis_store.get_position(token_id)
    if pos:
        old_shares = float(pos["shares"])
        old_avg = float(pos["avg_cost"])
        new_shares = old_shares + shares
        new_avg = (old_avg * old_shares + price * shares) / new_shares
        await redis_store.set_position(token_id, round(new_shares, 6), round(new_avg, 6), side)
    else:
        await redis_store.set_position(token_id, round(shares, 6), round(price, 6), side)


async def _update_position_sell(token_id: str, shares: float, price: float) -> None:
    pos = await redis_store.get_position(token_id)
    if not pos:
        return
    old_shares = float(pos["shares"])
    old_avg = float(pos["avg_cost"])
    new_shares = old_shares - shares

    # Realised PnL
    realised = (price - old_avg) * shares
    await redis_store.adjust_realized_pnl(realised)

    if new_shares <= 0.000001:
        await redis_store.delete_position(token_id)
    else:
        await redis_store.set_position(token_id, round(new_shares, 6), round(old_avg, 6), pos["side"])
