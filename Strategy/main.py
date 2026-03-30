"""Strategy Backtest Engine — standalone process.

Usage:
  python main.py server                         # Start HTTP API (default)
  python main.py list                           # List loaded strategies
  python main.py run <strategy> <slug> [opts]   # CLI single backtest
  python main.py batch <strategy> [slugs] [opts]# CLI batch backtest

Options:
  --balance    Initial balance (default: 10000)
  --config     Strategy config JSON string
  --port       HTTP server port (default: 8072)
  --workers    Concurrency (default: 4)
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# Ensure project root is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config import config
from core.data_scanner import load_token_map
from core.evaluator import evaluate
from core.registry import StrategyRegistry
from core.runner import run_backtest


def cmd_server(args: argparse.Namespace) -> None:
    """Start the HTTP API server."""
    import uvicorn
    port = args.port or config.server_port
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    uvicorn.run("api.app:app", host=config.server_host, port=port, reload=args.reload)


def cmd_list(args: argparse.Namespace) -> None:
    """List registered strategies."""
    load_token_map(config.data_dir)
    reg = StrategyRegistry()
    reg.scan(config.strategies_dir)
    strategies = reg.list_strategies()
    if not strategies:
        print("No strategies found.")
        return
    for s in strategies:
        print(f"  {s['name']} v{s['version']} — {s['description']}")
        if s.get("default_config"):
            print(f"    default_config: {json.dumps(s['default_config'])}")


def cmd_run(args: argparse.Namespace) -> None:
    """Run a single backtest from CLI."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    load_token_map(config.data_dir)
    reg = StrategyRegistry()
    reg.scan(config.strategies_dir)

    user_config = json.loads(args.config) if args.config else {}

    session = run_backtest(
        registry=reg,
        strategy_name=args.strategy,
        slug=args.slug,
        user_config=user_config,
        initial_balance=args.balance,
    )

    if session.status == "failed":
        print(f"FAILED: {session.session_id}")
        sys.exit(1)

    # Evaluate
    metrics = evaluate(session)
    session.metrics = metrics

    print(f"\n{'='*60}")
    print(f"  Strategy:  {session.strategy}")
    print(f"  Slug:      {session.slug}")
    print(f"  Session:   {session.session_id}")
    print(f"  Duration:  {session.duration_seconds:.2f}s")
    print(f"{'='*60}")
    print(f"  Initial:   ${session.initial_balance:,.2f}")
    print(f"  Final:     ${session.final_equity:,.2f}")
    print(f"  PnL:       ${metrics.total_pnl:,.2f} ({metrics.total_return_pct:+.2f}%)")
    print(f"  Trades:    {metrics.total_trades} (Buy: {metrics.buy_count}, Sell: {metrics.sell_count})")
    print(f"  Win Rate:  {metrics.win_rate:.1f}%")
    print(f"  Sharpe:    {metrics.sharpe_ratio:.4f}")
    print(f"  Sortino:   {metrics.sortino_ratio:.4f}")
    print(f"  Max DD:    {metrics.max_drawdown:.2f}%")
    print(f"  Profit F:  {metrics.profit_factor:.2f}")
    print(f"  Avg Slip:  {metrics.avg_slippage:.4f}%")
    print(f"{'='*60}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Strategy Backtest Engine")
    sub = parser.add_subparsers(dest="command")

    # server
    p_server = sub.add_parser("server", help="Start HTTP API server")
    p_server.add_argument("--port", type=int, default=None)
    p_server.add_argument("--reload", action="store_true")

    # list
    sub.add_parser("list", help="List strategies")

    # run
    p_run = sub.add_parser("run", help="Run single backtest")
    p_run.add_argument("strategy", help="Strategy name")
    p_run.add_argument("slug", help="Archive slug")
    p_run.add_argument("--balance", type=float, default=10000)
    p_run.add_argument("--config", type=str, default=None, help="JSON config string")

    # batch (TODO: implement async CLI)
    p_batch = sub.add_parser("batch", help="Run batch backtest")
    p_batch.add_argument("strategy", help="Strategy name")
    p_batch.add_argument("slugs", nargs="+", help="Archive slugs")
    p_batch.add_argument("--balance", type=float, default=10000)
    p_batch.add_argument("--config", type=str, default=None)

    args = parser.parse_args()

    if args.command is None or args.command == "server":
        if args.command is None:
            args.port = None
            args.reload = False
        cmd_server(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "run":
        cmd_run(args)
    elif args.command == "batch":
        print("Batch CLI: use HTTP API for now (python main.py server → POST /batch)")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
