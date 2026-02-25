"""
OctoBot Trade Tracker Service

Polls OctoBot's API to track trade executions and outcomes.
Records results to PostgreSQL for P&L analysis and prediction accuracy.

Features:
- Polls OctoBot every 30 seconds for orders and trades
- Tracks order fills and calculates P&L
- Links trades to prediction signals
- Updates trade outcomes in database
- Prometheus metrics for monitoring

Author: Backend Architect
Date: 2026-01-16
"""

import logging
import os
import time
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional, Dict, List, Any
from uuid import uuid4

import httpx
from prometheus_client import Counter, Gauge, Histogram

logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp":"%(asctime)s","service":"trade-tracker","level":"%(levelname)s","message":"%(message)s"}'
)
logger = logging.getLogger(__name__)

# Prometheus Metrics
OCTOBOT_POLL_TOTAL = Counter(
    'octobot_poll_total',
    'Total OctoBot API poll attempts',
    ['endpoint', 'status']
)
OCTOBOT_ORDERS_TRACKED = Gauge(
    'octobot_orders_tracked',
    'Current number of tracked orders'
)
OCTOBOT_TRADES_RECORDED = Counter(
    'octobot_trades_recorded_total',
    'Total trades recorded from OctoBot'
)
TRADE_TRACKER_LATENCY = Histogram(
    'trade_tracker_poll_duration_seconds',
    'Duration of trade tracker poll cycle',
    buckets=[1, 2, 5, 10, 30]
)

# Configuration
OCTOBOT_URL = os.getenv('OCTOBOT_URL', 'http://localhost:8110')
POLL_INTERVAL_SECONDS = int(os.getenv('TRADE_POLL_INTERVAL', '30'))
HTTP_TIMEOUT = int(os.getenv('OCTOBOT_TIMEOUT', '10'))

# Default fee rates for estimation when exchange doesn't provide data
DEFAULT_TAKER_FEE_RATE = Decimal('0.001')  # 0.1%
DEFAULT_MAKER_FEE_RATE = Decimal('0.0006')  # 0.06%


class OctoBotTradeTracker:
    """
    Tracks trades from OctoBot and records outcomes to PostgreSQL.

    Flow:
    1. Poll /api/orders for current order status
    2. Poll /api/trades for filled trades
    3. Match trades to signals using timestamp/symbol
    4. Record trade outcomes with P&L calculation
    5. Update existing open trades when closed
    """

    def __init__(self, db_session_factory=None):
        """
        Initialize trade tracker.

        Args:
            db_session_factory: SQLAlchemy session factory for database access
        """
        self.octobot_url = OCTOBOT_URL
        self.db_session_factory = db_session_factory
        self.tracked_orders: Dict[str, Dict[str, Any]] = {}
        self.last_poll_time: Optional[datetime] = None
        self.http_client = httpx.Client(timeout=HTTP_TIMEOUT)

        logger.info(f'{{"event":"tracker_initialized","octobot_url":"{self.octobot_url}"}}')

    async def poll_octobot_orders(self) -> List[Dict[str, Any]]:
        """
        Fetch current orders from OctoBot.

        Returns:
            List of order dictionaries from OctoBot API
        """
        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                response = await client.get(f"{self.octobot_url}/api/orders")
                response.raise_for_status()

                orders = response.json()
                OCTOBOT_POLL_TOTAL.labels(endpoint='orders', status='success').inc()
                OCTOBOT_ORDERS_TRACKED.set(len(orders))

                logger.info(f'{{"event":"orders_fetched","count":{len(orders)}}}')
                return orders

        except httpx.HTTPError as e:
            logger.error(f'{{"event":"orders_fetch_failed","error":"{str(e)}"}}')
            OCTOBOT_POLL_TOTAL.labels(endpoint='orders', status='error').inc()
            return []
        except Exception as e:
            logger.exception(f'{{"event":"orders_fetch_exception","error":"{str(e)}"}}')
            OCTOBOT_POLL_TOTAL.labels(endpoint='orders', status='error').inc()
            return []

    async def poll_octobot_trades(self) -> List[Dict[str, Any]]:
        """
        Fetch executed trades from OctoBot.

        Returns:
            List of trade dictionaries from OctoBot API
        """
        try:
            async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
                response = await client.get(f"{self.octobot_url}/api/trades")
                response.raise_for_status()

                trades = response.json()
                OCTOBOT_POLL_TOTAL.labels(endpoint='trades', status='success').inc()

                logger.info(f'{{"event":"trades_fetched","count":{len(trades)}}}')
                return trades

        except httpx.HTTPError as e:
            logger.error(f'{{"event":"trades_fetch_failed","error":"{str(e)}"}}')
            OCTOBOT_POLL_TOTAL.labels(endpoint='trades', status='error').inc()
            return []
        except Exception as e:
            logger.exception(f'{{"event":"trades_fetch_exception","error":"{str(e)}"}}')
            OCTOBOT_POLL_TOTAL.labels(endpoint='trades', status='error').inc()
            return []

    def get_current_signal_id(self, symbol: str) -> str:
        """
        Get the current signal ID based on 4-hour cycle.

        Args:
            symbol: Trading pair symbol

        Returns:
            Signal ID in format YYYY-MM-DD_HH-HH
        """
        now = datetime.now(timezone.utc)
        hour_start = (now.hour // 4) * 4
        cycle_start = now.replace(hour=hour_start, minute=0, second=0, microsecond=0)
        cycle_end = cycle_start + timedelta(hours=4)
        return f"{cycle_start.strftime('%Y-%m-%d_%H')}-{cycle_end.strftime('%H')}"

    def parse_order_type(self, order_type: str) -> str:
        """
        Parse OctoBot order type to action.

        Args:
            order_type: OctoBot order type string (e.g., "SELL LIMIT", "BUY MARKET")

        Returns:
            Action string: "buy" or "sell"
        """
        order_type_upper = order_type.upper()
        if 'BUY' in order_type_upper:
            return 'buy'
        elif 'SELL' in order_type_upper:
            return 'sell'
        return 'unknown'

    def extract_fee_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract fee data from CCXT order/trade response.

        CCXT fee structure:
        {
            'fee': {
                'cost': 0.95,         # Fee amount in fee currency
                'currency': 'USDT',   # Fee currency
                'rate': 0.001,        # Fee rate (0.1%)
                'type': 'taker'       # maker or taker
            }
        }

        Args:
            data: Order or trade dictionary from OctoBot/CCXT

        Returns:
            Dictionary with fee_cost, fee_rate, fee_type (all may be None)
        """
        fee_data = data.get('fee', {}) or {}

        fee_cost = fee_data.get('cost')
        fee_rate = fee_data.get('rate')
        fee_type = fee_data.get('type')  # 'maker' or 'taker'

        # Convert to Decimal if present
        if fee_cost is not None:
            fee_cost = Decimal(str(fee_cost))
        if fee_rate is not None:
            fee_rate = Decimal(str(fee_rate))

        return {
            'fee_cost': fee_cost,
            'fee_rate': fee_rate,
            'fee_type': fee_type
        }

    def estimate_fee(
        self,
        price: Decimal,
        quantity: Decimal,
        fee_type: str = 'taker'
    ) -> Dict[str, Any]:
        """
        Estimate fee when exchange doesn't provide actual data.

        Uses default rates:
        - Taker: 0.1% (market orders)
        - Maker: 0.06% (limit orders)

        Args:
            price: Trade price
            quantity: Trade quantity
            fee_type: 'maker' or 'taker'

        Returns:
            Dictionary with estimated fee_cost, fee_rate, fee_type
        """
        rate = DEFAULT_TAKER_FEE_RATE if fee_type == 'taker' else DEFAULT_MAKER_FEE_RATE
        cost = price * quantity * rate

        return {
            'fee_cost': cost,
            'fee_rate': rate,
            'fee_type': fee_type
        }

    async def process_orders(self, orders: List[Dict[str, Any]]) -> int:
        """
        Process orders and create/update trade outcomes.

        Args:
            orders: List of order dictionaries from OctoBot

        Returns:
            Number of orders processed
        """
        if not self.db_session_factory:
            logger.warning('{"event":"no_db_session","message":"Cannot record trades without database"}')
            return 0

        from app.models.trade_outcome import TradeOutcome

        processed = 0
        session = self.db_session_factory()

        try:
            for order in orders:
                order_id = order.get('id')
                symbol = order.get('symbol', 'BTC/USDT')
                price = Decimal(str(order.get('price', 0)))
                amount = Decimal(str(order.get('amount', 0)))
                order_type = order.get('type', '')
                exchange = order.get('exchange', 'binance')
                order_time = order.get('time', 0)

                # Skip if already tracked with same data
                if order_id in self.tracked_orders:
                    existing = self.tracked_orders[order_id]
                    if existing.get('price') == str(price):
                        continue

                action = self.parse_order_type(order_type)
                if action == 'unknown':
                    continue

                # Generate signal_id based on cycle
                signal_id = self.get_current_signal_id(symbol)

                # Check if trade outcome already exists
                existing_trade = session.query(TradeOutcome).filter(
                    TradeOutcome.octobot_order_id == order_id
                ).first()

                if existing_trade:
                    # Update existing trade if needed
                    self.tracked_orders[order_id] = {
                        'price': str(price),
                        'updated_at': datetime.now(timezone.utc).isoformat()
                    }
                    continue

                # Create new trade outcome
                executed_at = datetime.fromtimestamp(order_time, tz=timezone.utc) if order_time else datetime.now(timezone.utc)

                # Extract entry fee from order data
                fee_info = self.extract_fee_data(order)
                entry_fee_cost = fee_info['fee_cost']
                entry_fee_rate = fee_info['fee_rate']
                entry_fee_type = fee_info['fee_type']

                # If no fee data from exchange, estimate with taker rate
                if entry_fee_cost is None:
                    estimated = self.estimate_fee(price, amount, 'taker')
                    entry_fee_cost = estimated['fee_cost']
                    entry_fee_rate = estimated['fee_rate']
                    entry_fee_type = estimated['fee_type']

                trade_outcome = TradeOutcome(
                    signal_id=signal_id,
                    symbol=symbol,
                    action=action,
                    entry_price=price,
                    quantity=amount,
                    status='open',
                    executed_at=executed_at,
                    octobot_order_id=order_id,
                    exchange=exchange,
                    # Entry fee data
                    entry_fee_cost=entry_fee_cost,
                    entry_fee_rate=entry_fee_rate,
                    entry_fee_type=entry_fee_type
                )

                session.add(trade_outcome)

                self.tracked_orders[order_id] = {
                    'price': str(price),
                    'created_at': datetime.now(timezone.utc).isoformat()
                }

                processed += 1
                OCTOBOT_TRADES_RECORDED.inc()

                logger.info(
                    f'{{"event":"trade_recorded",'
                    f'"order_id":"{order_id}",'
                    f'"symbol":"{symbol}",'
                    f'"action":"{action}",'
                    f'"price":{price},'
                    f'"quantity":{amount},'
                    f'"signal_id":"{signal_id}"}}'
                )

            session.commit()

        except Exception as e:
            session.rollback()
            logger.exception(f'{{"event":"process_orders_error","error":"{str(e)}"}}')
        finally:
            session.close()

        return processed

    async def process_closed_trades(self, trades: List[Dict[str, Any]]) -> int:
        """
        Process filled trades and update trade outcomes with P&L.

        Args:
            trades: List of trade dictionaries from OctoBot

        Returns:
            Number of trades updated
        """
        if not self.db_session_factory or not trades:
            return 0

        from app.models.trade_outcome import TradeOutcome

        updated = 0
        session = self.db_session_factory()

        try:
            for trade in trades:
                trade_id = trade.get('id')
                symbol = trade.get('symbol', 'BTC/USDT')
                price = Decimal(str(trade.get('price', 0)))
                amount = Decimal(str(trade.get('amount', 0)))

                # Find open trade for this symbol
                open_trade = session.query(TradeOutcome).filter(
                    TradeOutcome.symbol == symbol,
                    TradeOutcome.status == 'open'
                ).order_by(TradeOutcome.executed_at.desc()).first()

                if not open_trade:
                    continue

                # Calculate gross P&L
                entry_price = float(open_trade.entry_price)
                exit_price = float(price)
                quantity = float(open_trade.quantity)

                if open_trade.action == 'buy':
                    gross_pnl = (exit_price - entry_price) * quantity
                else:  # sell
                    gross_pnl = (entry_price - exit_price) * quantity

                pnl_percent = ((exit_price - entry_price) / entry_price) * 100
                if open_trade.action == 'sell':
                    pnl_percent = -pnl_percent

                # Extract exit fee from trade data
                fee_info = self.extract_fee_data(trade)
                exit_fee_cost = fee_info['fee_cost']
                exit_fee_rate = fee_info['fee_rate']
                exit_fee_type = fee_info['fee_type']

                # If no fee data from exchange, estimate with taker rate
                if exit_fee_cost is None:
                    estimated = self.estimate_fee(price, Decimal(str(quantity)), 'taker')
                    exit_fee_cost = estimated['fee_cost']
                    exit_fee_rate = estimated['fee_rate']
                    exit_fee_type = estimated['fee_type']

                # Calculate total fees and net P&L
                entry_fee = float(open_trade.entry_fee_cost or 0)
                exit_fee = float(exit_fee_cost or 0)
                total_fees = entry_fee + exit_fee
                net_pnl = gross_pnl - total_fees

                # Calculate net P&L percent (relative to entry value including entry fee)
                entry_value = entry_price * quantity
                net_pnl_percent = (net_pnl / entry_value) * 100 if entry_value > 0 else 0

                # Update trade outcome with gross and net P&L
                open_trade.exit_price = price
                open_trade.pnl = Decimal(str(round(gross_pnl, 8)))
                open_trade.pnl_percent = round(pnl_percent, 4)
                open_trade.exit_fee_cost = exit_fee_cost
                open_trade.exit_fee_rate = exit_fee_rate
                open_trade.exit_fee_type = exit_fee_type
                open_trade.total_fees = Decimal(str(round(total_fees, 8)))
                open_trade.net_pnl = Decimal(str(round(net_pnl, 8)))
                open_trade.net_pnl_percent = round(net_pnl_percent, 4)
                open_trade.status = 'closed'
                open_trade.closed_at = datetime.now(timezone.utc)

                updated += 1

                logger.info(
                    f'{{"event":"trade_closed",'
                    f'"trade_id":"{open_trade.id}",'
                    f'"symbol":"{symbol}",'
                    f'"entry_price":{entry_price},'
                    f'"exit_price":{exit_price},'
                    f'"gross_pnl":{gross_pnl:.2f},'
                    f'"total_fees":{total_fees:.4f},'
                    f'"net_pnl":{net_pnl:.2f},'
                    f'"net_pnl_percent":{net_pnl_percent:.2f}}}'
                )

            session.commit()

        except Exception as e:
            session.rollback()
            logger.exception(f'{{"event":"process_trades_error","error":"{str(e)}"}}')
        finally:
            session.close()

        return updated

    async def poll_and_update(self) -> Dict[str, Any]:
        """
        Main polling function - fetches data from OctoBot and updates database.

        Returns:
            Dictionary with poll results
        """
        start_time = time.time()

        try:
            # Fetch orders and trades in parallel
            orders = await self.poll_octobot_orders()
            trades = await self.poll_octobot_trades()

            # Process orders (creates new trade outcomes)
            orders_processed = await self.process_orders(orders)

            # Process trades (updates existing outcomes with P&L)
            trades_updated = await self.process_closed_trades(trades)

            duration = time.time() - start_time
            TRADE_TRACKER_LATENCY.observe(duration)

            self.last_poll_time = datetime.now(timezone.utc)

            result = {
                'success': True,
                'orders_fetched': len(orders),
                'orders_processed': orders_processed,
                'trades_fetched': len(trades),
                'trades_updated': trades_updated,
                'duration_seconds': round(duration, 3),
                'timestamp': self.last_poll_time.isoformat()
            }

            logger.info(f'{{"event":"poll_complete","result":{result}}}')
            return result

        except Exception as e:
            duration = time.time() - start_time
            TRADE_TRACKER_LATENCY.observe(duration)

            logger.exception(f'{{"event":"poll_failed","error":"{str(e)}"}}')
            return {
                'success': False,
                'error': str(e),
                'duration_seconds': round(duration, 3),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }

    def get_status(self) -> Dict[str, Any]:
        """
        Get current tracker status.

        Returns:
            Status dictionary
        """
        return {
            'octobot_url': self.octobot_url,
            'poll_interval_seconds': POLL_INTERVAL_SECONDS,
            'tracked_orders': len(self.tracked_orders),
            'last_poll_time': self.last_poll_time.isoformat() if self.last_poll_time else None,
            'status': 'active' if self.last_poll_time else 'idle'
        }


# Global tracker instance
_tracker: Optional[OctoBotTradeTracker] = None


def get_tracker() -> OctoBotTradeTracker:
    """Get or create the global trade tracker instance."""
    global _tracker
    if _tracker is None:
        _tracker = OctoBotTradeTracker()
    return _tracker


def initialize_tracker(db_session_factory) -> OctoBotTradeTracker:
    """
    Initialize the trade tracker with database access.

    Args:
        db_session_factory: SQLAlchemy session factory

    Returns:
        Initialized OctoBotTradeTracker instance
    """
    global _tracker
    _tracker = OctoBotTradeTracker(db_session_factory)
    logger.info('{"event":"tracker_ready","message":"Trade tracker initialized with database access"}')
    return _tracker


async def run_poll_cycle():
    """
    Run a single poll cycle - called by scheduler.
    """
    tracker = get_tracker()
    await tracker.poll_and_update()


def run_poll_cycle_sync():
    """
    Synchronous wrapper for scheduler.
    """
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If already in an async context, create a task
            asyncio.create_task(run_poll_cycle())
        else:
            loop.run_until_complete(run_poll_cycle())
    except RuntimeError:
        # No event loop, create one
        asyncio.run(run_poll_cycle())
