"""Auto-record service — continuously records BTC series events.

Reads config from Redis (active durations like ["5m", "15m"]).
For each active duration runs an independent loop:
  discover current/next event → watch tokens → wait for end → archive → repeat.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from app.storage import redis_store

logger = logging.getLogger(__name__)

# Duration → (slug prefix, interval seconds)
_DURATION_MAP: dict[str, tuple[str, int]] = {
    "5m": ("btc-updown-5m", 300),
    "15m": ("btc-updown-15m", 900),
    "30m": ("btc-updown-30m", 1800),
}

VALID_DURATIONS = frozenset(_DURATION_MAP.keys())

_instance: AutoRecorder | None = None


class AutoRecorder:
    """Manages per-duration recording loops driven by Redis config."""

    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task] = {}  # duration → task
        self._watcher_task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    # ── Lifecycle ────────────────────────────────────────────

    async def start(self) -> None:
        self._stop_event.clear()
        self._watcher_task = asyncio.create_task(self._config_watcher())
        logger.info("AutoRecorder started")

    async def stop(self) -> None:
        self._stop_event.set()
        # Cancel all duration tasks
        for dur, task in self._tasks.items():
            task.cancel()
            logger.info("AutoRecorder: cancelled %s loop", dur)
        self._tasks.clear()
        if self._watcher_task:
            self._watcher_task.cancel()
            try:
                await self._watcher_task
            except asyncio.CancelledError:
                pass
        logger.info("AutoRecorder stopped")

    # ── Config watcher (main loop) ──────────────────────────

    async def _config_watcher(self) -> None:
        """Poll Redis config every 10s, start/stop duration tasks accordingly."""
        while not self._stop_event.is_set():
            try:
                config = await redis_store.get_auto_record_config()
                active = set(config) & VALID_DURATIONS

                # Start tasks for newly added durations
                for dur in active:
                    if dur not in self._tasks or self._tasks[dur].done():
                        logger.info("AutoRecorder: starting loop for %s", dur)
                        self._tasks[dur] = asyncio.create_task(
                            self._record_loop(dur),
                        )

                # Stop tasks for removed durations (they'll exit at next config check)
                for dur in list(self._tasks):
                    if dur not in active:
                        logger.info("AutoRecorder: duration %s removed from config", dur)
                        # Don't cancel — let the loop finish its current event gracefully
                        # It will exit when it checks config at the end of the cycle

            except Exception as e:
                logger.warning("AutoRecorder config watcher error: %s", e)

            # Sleep 10s in short increments so we can exit quickly
            for _ in range(10):
                if self._stop_event.is_set():
                    return
                await asyncio.sleep(1)

    # ── Per-duration recording loop ─────────────────────────

    async def _record_loop(self, duration: str) -> None:
        """Main loop for a single duration — find event → record → repeat.

        Lifecycle per event:
          1. Discover current/next event (or use pre-loaded slug)
          2. Watch tokens + subscribe WS
          3. Monitor until event ends
          4. Immediately unsubscribe old tokens + subscribe next event
          5. Archive runs in background (no blocking)
        """
        prefix, interval = _DURATION_MAP[duration]
        # Track tokens we subscribed so we can unsubscribe them later
        current_tokens: list[str] = []

        while not self._stop_event.is_set():
            try:
                # Check if still in config
                if not await self._is_duration_active(duration):
                    logger.info("AutoRecorder: %s no longer in config, exiting loop", duration)
                    await self._unsubscribe_tokens(current_tokens)
                    current_tokens = []
                    await redis_store.delete_auto_record_state(duration)
                    return

                # 1. Discover current or next event
                await self._update_state(duration, status="searching", slug=None)

                from app.services.event_lifecycle import find_current_or_next_event
                result = await find_current_or_next_event(prefix, interval)

                if not result:
                    logger.info("AutoRecorder %s: no event found, retrying in 30s", duration)
                    await self._update_state(duration, status="waiting", slug=None)
                    await self._interruptible_sleep(30)
                    continue

                slug = result["slug"]
                event = result["event"]
                status = result["status"]
                secs = result.get("seconds_remaining")

                # 2. If upcoming, wait until it starts
                if status == "upcoming" and secs is not None and secs > 0:
                    logger.info(
                        "AutoRecorder %s: %s is upcoming, waiting %.0fs",
                        duration, slug, secs,
                    )
                    await self._update_state(
                        duration, status="waiting", slug=slug,
                        seconds_remaining=secs,
                    )
                    await self._interruptible_sleep(secs)
                    # Re-check config after waiting
                    if not await self._is_duration_active(duration):
                        await self._unsubscribe_tokens(current_tokens)
                        current_tokens = []
                        await redis_store.delete_auto_record_state(duration)
                        return
                    continue  # Re-discover — event should now be live

                # 3. Event is LIVE — watch tokens + subscribe WS
                logger.info("AutoRecorder %s: recording %s", duration, slug)
                from app.services.event_lifecycle import watch_event_tokens
                watched = await watch_event_tokens(slug, event)
                logger.info(
                    "AutoRecorder %s: watching %d tokens for %s",
                    duration, len(watched), slug,
                )

                # Unsubscribe previous event tokens before subscribing new ones
                old_tokens = [t for t in current_tokens if t not in watched]
                if old_tokens:
                    await self._unsubscribe_tokens(old_tokens)
                current_tokens = watched

                # Subscribe to WS for real-time data (headless — no frontend needed)
                ws_mgr = self._get_ws_manager()
                if ws_mgr and watched:
                    await ws_mgr.subscribe(watched)
                    await ws_mgr.start_recording(watched)
                    logger.info("AutoRecorder %s: WS subscribed for %s", duration, slug)

                await self._update_state(
                    duration, status="recording", slug=slug,
                )

                # 4. Monitor until event ends
                await self._wait_for_event_end(duration, slug, interval)

                # 5. Pre-resolve next event slug so we can subscribe immediately
                next_slug = f"{prefix}-{self._extract_epoch(slug) + interval}"
                next_result = None
                try:
                    from app.services.event_lifecycle import find_current_or_next_event as _find
                    next_result = await _find(prefix, interval)
                except Exception:
                    pass

                # 6. Subscribe next event tokens BEFORE archiving (zero-gap switch)
                if next_result and next_result.get("status") in ("live", "upcoming"):
                    next_event = next_result["event"]
                    next_watched = await watch_event_tokens(next_result["slug"], next_event)
                    if ws_mgr and next_watched:
                        await ws_mgr.subscribe(next_watched)
                        logger.info(
                            "AutoRecorder %s: pre-subscribed %d tokens for %s",
                            duration, len(next_watched), next_result["slug"],
                        )

                # 7. Unsubscribe old tokens (this event is done)
                await self._unsubscribe_tokens(current_tokens)
                current_tokens = []

                # 8. Archive (non-blocking — trigger and move on)
                await self._update_state(
                    duration, status="archiving", slug=slug,
                )
                await self._wait_for_archive(duration, slug)

                logger.info("AutoRecorder %s: %s archived, moving to next", duration, slug)
                await self._update_state(
                    duration, status="completed", slug=slug,
                )

                # Brief pause before next cycle
                await self._interruptible_sleep(2)

            except asyncio.CancelledError:
                logger.info("AutoRecorder %s: loop cancelled", duration)
                await self._unsubscribe_tokens(current_tokens)
                return
            except Exception as e:
                logger.warning("AutoRecorder %s: error in loop: %s", duration, e)
                await self._interruptible_sleep(10)

        # Clean up state on exit
        await self._unsubscribe_tokens(current_tokens)
        await redis_store.delete_auto_record_state(duration)

    # ── Helpers ──────────────────────────────────────────────

    @staticmethod
    def _get_ws_manager():
        from app.services.ws_manager import get_ws_manager
        try:
            return get_ws_manager()
        except AssertionError:
            return None

    async def _unsubscribe_tokens(self, token_ids: list[str]) -> None:
        """Unsubscribe specific tokens from upstream WS.

        Does NOT call ``stop_recording`` — recording lifecycle is managed
        exclusively by ``archive_event`` → ``complete_recording``.
        """
        if not token_ids:
            return
        ws_mgr = self._get_ws_manager()
        if not ws_mgr:
            return
        try:
            await ws_mgr.unsubscribe(token_ids)
            logger.info("AutoRecorder: unsubscribed %d tokens", len(token_ids))
        except Exception as e:
            logger.warning("AutoRecorder: unsubscribe failed: %s", e)

    @staticmethod
    def _extract_epoch(slug: str) -> int:
        """Extract the unix epoch from a slug like 'btc-updown-5m-1774839900'."""
        try:
            return int(slug.rsplit("-", 1)[-1])
        except (ValueError, IndexError):
            return 0

    async def _is_duration_active(self, duration: str) -> bool:
        config = await redis_store.get_auto_record_config()
        return duration in config

    async def _update_state(
        self,
        duration: str,
        *,
        status: str,
        slug: str | None,
        seconds_remaining: float | None = None,
    ) -> None:
        state = {
            "slug": slug,
            "status": status,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "seconds_remaining": round(seconds_remaining, 1) if seconds_remaining is not None else None,
        }
        await redis_store.set_auto_record_state(duration, json.dumps(state))

    async def _wait_for_event_end(
        self, duration: str, slug: str, interval: int,
    ) -> None:
        """Poll event status until it transitions to ended."""
        from app.services.event_lifecycle import check_event_status

        while not self._stop_event.is_set():
            try:
                st = await check_event_status(slug)
                event_status = st.get("status", "unknown")
                secs = st.get("seconds_remaining")

                if event_status in ("ended", "settled"):
                    return

                await self._update_state(
                    duration, status="recording", slug=slug,
                    seconds_remaining=secs,
                )
            except Exception as e:
                logger.warning("AutoRecorder %s: status check error: %s", duration, e)

            await self._interruptible_sleep(5)

    async def _wait_for_archive(self, duration: str, slug: str) -> None:
        """Wait until archive_ready becomes true (max 60s)."""
        for _ in range(12):
            if self._stop_event.is_set():
                return
            meta = await redis_store.get_archive_meta(slug)
            if meta is not None and not meta.get("deleted"):
                return
            await self._interruptible_sleep(5)
        logger.warning("AutoRecorder %s: archive timeout for %s", duration, slug)

    async def _interruptible_sleep(self, seconds: float) -> None:
        """Sleep that can be interrupted by stop_event."""
        try:
            await asyncio.wait_for(
                self._stop_event.wait(),
                timeout=seconds,
            )
        except asyncio.TimeoutError:
            pass  # Normal — stop_event was not set within timeout


# ── Module-level interface ───────────────────────────────────────────────────


async def start_auto_recorder() -> AutoRecorder:
    global _instance
    _instance = AutoRecorder()
    await _instance.start()
    return _instance


async def stop_auto_recorder() -> None:
    global _instance
    if _instance:
        await _instance.stop()
        _instance = None


def get_auto_recorder() -> AutoRecorder:
    if _instance is None:
        raise RuntimeError("AutoRecorder not started")
    return _instance
