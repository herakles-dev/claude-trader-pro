"""
OctoBot Sync Service - Synchronizes trade data from OctoBot to PostgreSQL

OctoBot is the single source of truth for all trading data.
This service maintains PostgreSQL as a synced cache for analytics and queries.

Features:
- Periodic sync of closed orders (every 5 minutes)
- Daily reconciliation to ensure data consistency
- Webhook handling for real-time updates
- Discrepancy detection and logging

Author: Backend Architect
Date: 2026-01-18
"""

import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any
from uuid import uuid4

import aiohttp
from prometheus_client import Counter, Gauge, Histogram

logger = logging.getLogger(__name__)

# Configuration
OCTOBOT_URL = os.getenv('OCTOBOT_URL', 'http://octobot-claude-trader:5001')
SYNC_INTERVAL_SECONDS = int(os.getenv('OCTOBOT_SYNC_INTERVAL', '300'))  # 5 minutes
OCTOBOT_TIMEOUT = int(os.getenv('OCTOBOT_TIMEOUT', '15'))

# Prometheus metrics
SYNC_RUNS_TOTAL = Counter(
    'octobot_sync_runs_total',
    'Total number of sync runs',
    ['status']
)
SYNC_ORDERS_SYNCED = Counter(
    'octobot_orders_synced_total',
    'Total number of orders synced from OctoBot',
    ['operation']
)
SYNC_LATENCY = Histogram(
    'octobot_sync_latency_seconds',
    'Sync operation latency in seconds',
    buckets=[0.5, 1, 2, 5, 10, 30]
)
LAST_SYNC_TIMESTAMP = Gauge(
    'octobot_last_sync_timestamp',
    'Timestamp of last successful sync'
)
SYNC_DISCREPANCIES = Counter(
    'octobot_sync_discrepancies_total',
    'Number of discrepancies found during reconciliation',
    ['type']
)


class OctoBotSyncService:
    """
    Synchronizes trade data from OctoBot to PostgreSQL.
    OctoBot is the single source of truth.
    """

    def __init__(
        self,
        octobot_url: str = OCTOBOT_URL,
        timeout: int = OCTOBOT_TIMEOUT
    ):
        self.octobot_url = octobot_url
        self.timeout = timeout
        self._session: Optional[aiohttp.ClientSession] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._last_sync: Optional[datetime] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session, handling event loop changes."""
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        # Recreate session if closed OR if event loop changed
        needs_new_session = (
            self._session is None or
            self._session.closed or
            self._loop != current_loop
        )

        if needs_new_session:
            # Close old session if exists and not closed
            if self._session and not self._session.closed:
                try:
                    await self._session.close()
                except Exception:
                    pass  # Ignore close errors on stale session

            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )
            self._loop = current_loop

        return self._session

    async def close(self):
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def get_closed_orders(self, limit: int = 100) -> List[dict]:
        """
        Fetch closed orders from OctoBot.

        Args:
            limit: Maximum number of orders to fetch

        Returns:
            List of closed order dictionaries
        """
        try:
            session = await self._get_session()
            async with session.get(
                f"{self.octobot_url}/api/orders/closed",
                params={'limit': limit}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    # OctoBot may return orders directly or nested
                    orders = data if isinstance(data, list) else data.get('orders', [])
                    logger.info(
                        f'{{"event":"octobot_closed_orders_fetched",'
                        f'"count":{len(orders)}}}'
                    )
                    return orders
                else:
                    logger.error(
                        f'{{"event":"octobot_closed_orders_error",'
                        f'"status":{response.status}}}'
                    )
                    return []
        except Exception as e:
            logger.error(
                f'{{"event":"octobot_closed_orders_exception",'
                f'"error":"{str(e)}"}}'
            )
            return []

    async def get_all_orders(self) -> List[dict]:
        """
        Fetch all orders (open + closed) from OctoBot.

        Returns:
            List of all order dictionaries
        """
        try:
            session = await self._get_session()

            # Fetch both open and closed orders
            orders = []

            # Closed orders
            async with session.get(
                f"{self.octobot_url}/api/orders/closed",
                params={'limit': 500}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    closed = data if isinstance(data, list) else data.get('orders', [])
                    orders.extend(closed)

            # Open orders
            async with session.get(
                f"{self.octobot_url}/api/orders/open"
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    open_orders = data if isinstance(data, list) else data.get('orders', [])
                    orders.extend(open_orders)

            return orders

        except Exception as e:
            logger.error(
                f'{{"event":"octobot_all_orders_exception",'
                f'"error":"{str(e)}"}}'
            )
            return []

    async def get_trade_history(
        self,
        symbol: Optional[str] = None,
        days: int = 30
    ) -> List[dict]:
        """
        Fetch complete trade history from OctoBot.

        Args:
            symbol: Optional symbol filter
            days: Number of days of history to fetch

        Returns:
            List of trade dictionaries
        """
        try:
            session = await self._get_session()
            params = {'days': days}
            if symbol:
                params['symbol'] = symbol

            async with session.get(
                f"{self.octobot_url}/api/trades/history",
                params=params
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    trades = data if isinstance(data, list) else data.get('trades', [])
                    return trades
                else:
                    return []
        except Exception as e:
            logger.error(
                f'{{"event":"octobot_trade_history_exception",'
                f'"error":"{str(e)}"}}'
            )
            return []

    async def sync_closed_orders(self, db_session) -> Dict[str, int]:
        """
        Fetch closed orders from OctoBot and update PostgreSQL.

        Args:
            db_session: SQLAlchemy database session

        Returns:
            Dictionary with sync statistics
        """
        import time
        start_time = time.time()

        stats = {
            'created': 0,
            'updated': 0,
            'unchanged': 0,
            'errors': 0
        }

        try:
            from app.models.trade_outcome import TradeOutcome

            orders = await self.get_closed_orders(limit=200)

            for order in orders:
                try:
                    order_id = order.get('id') or order.get('order_id')
                    if not order_id:
                        continue

                    # Check if this order exists in PostgreSQL
                    existing = db_session.query(TradeOutcome).filter(
                        TradeOutcome.octobot_order_id == str(order_id)
                    ).first()

                    if not existing:
                        # New order from OctoBot - create record
                        new_trade = self._create_trade_from_octobot(order)
                        if new_trade:
                            db_session.add(new_trade)
                            stats['created'] += 1
                            SYNC_ORDERS_SYNCED.labels(operation='create').inc()
                    else:
                        # Check if update needed
                        order_status = order.get('status', 'closed')
                        if existing.status != order_status:
                            self._update_trade_from_octobot(existing, order)
                            stats['updated'] += 1
                            SYNC_ORDERS_SYNCED.labels(operation='update').inc()
                        else:
                            stats['unchanged'] += 1

                except Exception as order_error:
                    logger.error(
                        f'{{"event":"sync_order_error",'
                        f'"order_id":"{order.get("id")}",'
                        f'"error":"{str(order_error)}"}}'
                    )
                    stats['errors'] += 1

            db_session.commit()

            latency = time.time() - start_time
            SYNC_LATENCY.observe(latency)
            SYNC_RUNS_TOTAL.labels(status='success').inc()
            LAST_SYNC_TIMESTAMP.set(time.time())
            self._last_sync = datetime.now(timezone.utc)

            logger.info(
                f'{{"event":"sync_completed",'
                f'"created":{stats["created"]},'
                f'"updated":{stats["updated"]},'
                f'"unchanged":{stats["unchanged"]},'
                f'"errors":{stats["errors"]},'
                f'"latency_seconds":{latency:.2f}}}'
            )

            return stats

        except Exception as e:
            SYNC_RUNS_TOTAL.labels(status='error').inc()
            logger.exception(
                f'{{"event":"sync_failed",'
                f'"error":"{str(e)}"}}'
            )
            db_session.rollback()
            raise

    def _create_trade_from_octobot(self, order: dict) -> Optional['TradeOutcome']:
        """
        Create TradeOutcome from OctoBot order data.

        Args:
            order: OctoBot order dictionary

        Returns:
            TradeOutcome instance or None
        """
        from app.models.trade_outcome import TradeOutcome

        try:
            order_id = order.get('id') or order.get('order_id')
            symbol = order.get('symbol', 'UNKNOWN')
            side = order.get('side', order.get('type', 'buy')).lower()

            # Map OctoBot side to our action
            action = 'buy' if side in ['buy', 'long'] else 'sell'

            # Extract prices
            entry_price = order.get('price') or order.get('entry_price') or order.get('average', 0)
            exit_price = order.get('exit_price') or order.get('close_price')
            amount = order.get('amount') or order.get('quantity') or order.get('filled', 0)

            # Extract PnL if available
            pnl = order.get('pnl') or order.get('realized_pnl') or order.get('profit')

            # Calculate PnL percent if we have the data
            pnl_percent = None
            if pnl is not None and entry_price and amount and float(entry_price) > 0:
                entry_value = float(entry_price) * float(amount)
                if entry_value > 0:
                    pnl_percent = (float(pnl) / entry_value) * 100

            # Parse timestamps
            executed_at = order.get('timestamp') or order.get('created_at')
            if isinstance(executed_at, (int, float)):
                executed_at = datetime.fromtimestamp(executed_at / 1000 if executed_at > 1e12 else executed_at, tz=timezone.utc)
            elif isinstance(executed_at, str):
                executed_at = datetime.fromisoformat(executed_at.replace('Z', '+00:00'))
            else:
                executed_at = datetime.now(timezone.utc)

            closed_at = order.get('closed_at') or order.get('close_timestamp')
            if isinstance(closed_at, (int, float)):
                closed_at = datetime.fromtimestamp(closed_at / 1000 if closed_at > 1e12 else closed_at, tz=timezone.utc)
            elif isinstance(closed_at, str):
                closed_at = datetime.fromisoformat(closed_at.replace('Z', '+00:00'))

            # Extract fees
            fees = order.get('fees') or order.get('fee') or {}
            total_fees = None
            if isinstance(fees, dict):
                total_fees = fees.get('cost') or fees.get('total')
            elif isinstance(fees, (int, float)):
                total_fees = fees

            # Determine if this was auto-executed
            tag = order.get('tag', '') or ''
            was_auto = 'claude-' in tag.lower() or order.get('was_auto_executed', False)

            # Extract confidence from tag if present
            confidence = order.get('execution_confidence')

            trade = TradeOutcome(
                id=uuid4(),
                signal_id=f"octobot-{order_id}",
                symbol=symbol,
                action=action,
                entry_price=Decimal(str(entry_price)) if entry_price else Decimal('0'),
                exit_price=Decimal(str(exit_price)) if exit_price else None,
                quantity=Decimal(str(amount)) if amount else Decimal('0'),
                pnl=Decimal(str(pnl)) if pnl is not None else None,
                pnl_percent=pnl_percent,
                status=order.get('status', 'closed'),
                executed_at=executed_at,
                closed_at=closed_at,
                octobot_order_id=str(order_id),
                total_fees=Decimal(str(total_fees)) if total_fees is not None else None,
                was_auto_executed=was_auto,
                execution_confidence=confidence,
                octobot_synced_at=datetime.now(timezone.utc),
                octobot_raw_data=order
            )

            return trade

        except Exception as e:
            logger.error(
                f'{{"event":"create_trade_from_octobot_error",'
                f'"order":"{order}",'
                f'"error":"{str(e)}"}}'
            )
            return None

    def _update_trade_from_octobot(self, trade: 'TradeOutcome', order: dict) -> None:
        """
        Update existing TradeOutcome from OctoBot order data.

        Args:
            trade: Existing TradeOutcome to update
            order: OctoBot order dictionary with new data
        """
        try:
            # Update status
            new_status = order.get('status', trade.status)
            trade.status = new_status

            # Update exit price if now available
            exit_price = order.get('exit_price') or order.get('close_price')
            if exit_price and trade.exit_price is None:
                trade.exit_price = Decimal(str(exit_price))

            # Update PnL if now available
            pnl = order.get('pnl') or order.get('realized_pnl')
            if pnl is not None:
                trade.pnl = Decimal(str(pnl))
                # Recalculate percentage
                if trade.entry_price and trade.quantity and float(trade.entry_price) > 0:
                    entry_value = float(trade.entry_price) * float(trade.quantity)
                    if entry_value > 0:
                        trade.pnl_percent = (float(pnl) / entry_value) * 100

            # Update closed timestamp
            closed_at = order.get('closed_at') or order.get('close_timestamp')
            if closed_at:
                if isinstance(closed_at, (int, float)):
                    trade.closed_at = datetime.fromtimestamp(
                        closed_at / 1000 if closed_at > 1e12 else closed_at,
                        tz=timezone.utc
                    )
                elif isinstance(closed_at, str):
                    trade.closed_at = datetime.fromisoformat(closed_at.replace('Z', '+00:00'))

            # Update fees
            fees = order.get('fees') or order.get('fee') or {}
            if isinstance(fees, dict) and fees.get('cost'):
                trade.total_fees = Decimal(str(fees['cost']))
            elif isinstance(fees, (int, float)):
                trade.total_fees = Decimal(str(fees))

            # Update sync metadata
            trade.octobot_synced_at = datetime.now(timezone.utc)
            trade.octobot_raw_data = order

        except Exception as e:
            logger.error(
                f'{{"event":"update_trade_from_octobot_error",'
                f'"trade_id":"{trade.id}",'
                f'"error":"{str(e)}"}}'
            )

    async def reconcile(self, db_session) -> Dict[str, Any]:
        """
        Ensure PostgreSQL matches OctoBot state.

        Detects:
        - Orphaned records (in DB but not in OctoBot)
        - Missing records (in OctoBot but not in DB)
        - Status mismatches

        Args:
            db_session: SQLAlchemy database session

        Returns:
            Reconciliation report
        """
        from app.models.trade_outcome import TradeOutcome

        report = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'octobot_count': 0,
            'db_count': 0,
            'missing_in_db': [],
            'orphaned_in_db': [],
            'status_mismatches': [],
            'auto_fixed': 0
        }

        try:
            # Get all orders from OctoBot
            octobot_orders = await self.get_all_orders()
            octobot_ids = {
                str(o.get('id') or o.get('order_id'))
                for o in octobot_orders if o.get('id') or o.get('order_id')
            }
            report['octobot_count'] = len(octobot_ids)

            # Get all trades from PostgreSQL with OctoBot order IDs
            db_trades = db_session.query(TradeOutcome).filter(
                TradeOutcome.octobot_order_id.isnot(None)
            ).all()
            db_ids = {t.octobot_order_id for t in db_trades}
            report['db_count'] = len(db_ids)

            # Find missing in DB (in OctoBot but not synced)
            missing_ids = octobot_ids - db_ids
            if missing_ids:
                report['missing_in_db'] = list(missing_ids)[:10]  # Limit for report
                SYNC_DISCREPANCIES.labels(type='missing_in_db').inc(len(missing_ids))
                logger.warning(
                    f'{{"event":"reconciliation_missing",'
                    f'"count":{len(missing_ids)},'
                    f'"sample":"{list(missing_ids)[:3]}"}}'
                )

            # Find orphaned in DB (synced but no longer in OctoBot)
            # This is usually not an issue - OctoBot may have purged old data
            orphaned_ids = db_ids - octobot_ids
            if orphaned_ids:
                report['orphaned_in_db'] = list(orphaned_ids)[:10]
                # Log but don't delete - historical data is valuable
                logger.info(
                    f'{{"event":"reconciliation_orphaned",'
                    f'"count":{len(orphaned_ids)},'
                    f'"note":"Historical data retained"}}'
                )

            # Check status mismatches for recent orders
            octobot_status_map = {
                str(o.get('id') or o.get('order_id')): o.get('status', 'unknown')
                for o in octobot_orders
            }

            for trade in db_trades:
                if trade.octobot_order_id in octobot_status_map:
                    octobot_status = octobot_status_map[trade.octobot_order_id]
                    if trade.status != octobot_status:
                        report['status_mismatches'].append({
                            'id': str(trade.id),
                            'octobot_order_id': trade.octobot_order_id,
                            'db_status': trade.status,
                            'octobot_status': octobot_status
                        })
                        SYNC_DISCREPANCIES.labels(type='status_mismatch').inc()

                        # Auto-fix status mismatches
                        trade.status = octobot_status
                        trade.octobot_synced_at = datetime.now(timezone.utc)
                        report['auto_fixed'] += 1

            db_session.commit()

            logger.info(
                f'{{"event":"reconciliation_completed",'
                f'"octobot_count":{report["octobot_count"]},'
                f'"db_count":{report["db_count"]},'
                f'"missing":{len(report["missing_in_db"])},'
                f'"orphaned":{len(report["orphaned_in_db"])},'
                f'"mismatches":{len(report["status_mismatches"])},'
                f'"auto_fixed":{report["auto_fixed"]}}}'
            )

            return report

        except Exception as e:
            logger.exception(
                f'{{"event":"reconciliation_failed",'
                f'"error":"{str(e)}"}}'
            )
            db_session.rollback()
            report['error'] = str(e)
            return report

    def get_sync_status(self) -> Dict[str, Any]:
        """
        Get current sync service status.

        Returns:
            Status dictionary with sync metadata
        """
        return {
            'service': 'octobot_sync',
            'octobot_url': self.octobot_url,
            'last_sync': self._last_sync.isoformat() if self._last_sync else None,
            'sync_interval_seconds': SYNC_INTERVAL_SECONDS,
            'status': 'healthy' if self._last_sync else 'awaiting_first_sync'
        }


# Singleton instance
_sync_service: Optional[OctoBotSyncService] = None


def get_sync_service() -> OctoBotSyncService:
    """Get or create the sync service singleton."""
    global _sync_service
    if _sync_service is None:
        _sync_service = OctoBotSyncService()
    return _sync_service


async def cleanup_sync_service():
    """Cleanup the sync service on shutdown."""
    global _sync_service
    if _sync_service:
        await _sync_service.close()
        _sync_service = None


# Synchronous wrapper for APScheduler
def run_sync_cycle_sync():
    """
    Synchronous wrapper for sync job (for APScheduler).
    Creates event loop and runs async sync.
    """
    import asyncio
    from app.services.scheduler_service import get_db_session

    logger.info('{"event":"sync_cycle_starting"}')

    try:
        session = get_db_session()
        sync_service = get_sync_service()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(
                sync_service.sync_closed_orders(session)
            )
            logger.info(
                f'{{"event":"sync_cycle_completed",'
                f'"stats":{result}}}'
            )
        finally:
            loop.close()

    except Exception as e:
        logger.exception(
            f'{{"event":"sync_cycle_error",'
            f'"error":"{str(e)}"}}'
        )
    finally:
        session.close()


def run_reconciliation_sync():
    """
    Synchronous wrapper for reconciliation job.
    Runs daily to ensure data consistency.
    """
    import asyncio
    from app.services.scheduler_service import get_db_session

    logger.info('{"event":"reconciliation_starting"}')

    try:
        session = get_db_session()
        sync_service = get_sync_service()

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(
                sync_service.reconcile(session)
            )
            logger.info(
                f'{{"event":"reconciliation_completed",'
                f'"report":{result}}}'
            )
        finally:
            loop.close()

    except Exception as e:
        logger.exception(
            f'{{"event":"reconciliation_error",'
            f'"error":"{str(e)}"}}'
        )
    finally:
        session.close()
