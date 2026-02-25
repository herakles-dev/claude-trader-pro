"""
Order Executor Service - OctoBot Webhook Bridge

Bridges AI predictions to OctoBot webhook execution for automated paper trading.

Features:
- Confidence threshold validation (70% minimum)
- Position sizing (2% of portfolio per trade)
- Maximum order value cap ($1,000)
- Webhook payload generation
- Execution logging and metrics

Author: AI Integration Specialist
Date: 2026-01-18
"""

import logging
import os
import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List
from enum import Enum

import aiohttp
from prometheus_client import Counter, Histogram, Gauge

logger = logging.getLogger(__name__)

# Configuration
OCTOBOT_URL = os.getenv('OCTOBOT_URL', 'http://octobot-claude-trader:5001')
OCTOBOT_WEBHOOK_TOKEN = os.getenv('OCTOBOT_WEBHOOK_TOKEN', 'claude-trader-pro')
OCTOBOT_TIMEOUT = int(os.getenv('OCTOBOT_TIMEOUT', '15'))

# Trading parameters
CONFIDENCE_THRESHOLD = float(os.getenv('EXECUTION_CONFIDENCE_THRESHOLD', '0.70'))
POSITION_SIZE_PCT = float(os.getenv('EXECUTION_POSITION_SIZE_PCT', '0.02'))
MAX_ORDER_VALUE_USD = float(os.getenv('EXECUTION_MAX_ORDER_VALUE', '1000'))
AUTO_EXECUTE_ENABLED = os.getenv('AUTO_EXECUTE_ENABLED', 'true').lower() == 'true'

# Supported trading pairs
SUPPORTED_SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'XRP/USDT', 'BNB/USDT']

# Prometheus metrics
EXECUTION_TOTAL = Counter(
    'order_execution_total',
    'Total order execution attempts',
    ['symbol', 'direction', 'status']
)
EXECUTION_LATENCY = Histogram(
    'order_execution_latency_seconds',
    'Order execution latency in seconds',
    buckets=[0.1, 0.5, 1, 2, 5, 10]
)
EXECUTION_VALUE = Counter(
    'order_execution_value_usd_total',
    'Total value of executed orders in USD',
    ['symbol', 'direction']
)
PORTFOLIO_VALUE = Gauge(
    'octobot_portfolio_value_usd',
    'Current portfolio value in USD'
)


class ExecutionStatus(Enum):
    """Order execution status codes."""
    EXECUTED = "executed"
    SKIPPED = "skipped"
    FAILED = "failed"
    PENDING = "pending"


@dataclass
class ExecutionResult:
    """Result of order execution attempt."""
    status: ExecutionStatus
    executed: bool
    order_id: Optional[str] = None
    symbol: Optional[str] = None
    direction: Optional[str] = None
    position_usd: Optional[float] = None
    reason: Optional[str] = None
    webhook_response: Optional[dict] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)


class OrderExecutorService:
    """
    Bridges AI predictions to OctoBot webhook execution.

    Usage:
        executor = OrderExecutorService()
        result = await executor.execute_signal(prediction)
    """

    def __init__(
        self,
        octobot_url: str = OCTOBOT_URL,
        webhook_token: str = OCTOBOT_WEBHOOK_TOKEN,
        confidence_threshold: float = CONFIDENCE_THRESHOLD,
        position_size_pct: float = POSITION_SIZE_PCT,
        max_order_value: float = MAX_ORDER_VALUE_USD,
        timeout: int = OCTOBOT_TIMEOUT
    ):
        self.octobot_url = octobot_url
        self.webhook_token = webhook_token
        self.confidence_threshold = confidence_threshold
        self.position_size_pct = position_size_pct
        self.max_order_value = max_order_value
        self.timeout = timeout
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )
        return self._session

    async def close(self):
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def get_portfolio_value(self) -> float:
        """
        Get current portfolio value from OctoBot.

        Returns:
            Portfolio value in USD
        """
        try:
            session = await self._get_session()
            async with session.get(
                f"{self.octobot_url}/api/portfolio",
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    # Extract portfolio value from OctoBot response
                    # Format varies by OctoBot version
                    if isinstance(data, dict):
                        # Try to get total value
                        if 'value' in data:
                            value = float(data['value'])
                        elif 'total_value' in data:
                            value = float(data['total_value'])
                        elif 'portfolio' in data:
                            # Calculate from portfolio balances
                            portfolio = data['portfolio']
                            value = sum(
                                float(v.get('value', 0))
                                for v in portfolio.values()
                                if isinstance(v, dict)
                            )
                        else:
                            # Default fallback
                            value = 10000.0

                        PORTFOLIO_VALUE.set(value)
                        return value

                logger.warning(
                    f"Unexpected portfolio response format, using default: {data}"
                )
                return 10000.0  # Default portfolio value

        except Exception as e:
            logger.error(f"Failed to get portfolio value: {e}")
            return 10000.0  # Default fallback

    async def execute_signal(
        self,
        prediction: 'AutomatedPrediction',
        force: bool = False
    ) -> ExecutionResult:
        """
        Execute prediction as OctoBot order if conditions are met.

        Args:
            prediction: AutomatedPrediction object
            force: If True, bypass confidence threshold check

        Returns:
            ExecutionResult with status and details
        """
        import time
        start_time = time.time()

        symbol = prediction.symbol
        confidence = float(prediction.confidence)
        prediction_type = prediction.prediction_type
        cycle_id = getattr(prediction, 'cycle_id', None) or str(prediction.id)

        logger.info(
            f'{{"event":"execute_signal_started",'
            f'"symbol":"{symbol}",'
            f'"confidence":{confidence},'
            f'"prediction_type":"{prediction_type}",'
            f'"force":{force}}}'
        )

        # Validation checks
        if not force and confidence < self.confidence_threshold:
            reason = f"Confidence {confidence:.0%} below threshold {self.confidence_threshold:.0%}"
            EXECUTION_TOTAL.labels(
                symbol=symbol,
                direction=prediction_type,
                status='skipped'
            ).inc()
            logger.info(
                f'{{"event":"execute_signal_skipped",'
                f'"reason":"below_confidence_threshold",'
                f'"confidence":{confidence},'
                f'"threshold":{self.confidence_threshold}}}'
            )
            return ExecutionResult(
                status=ExecutionStatus.SKIPPED,
                executed=False,
                symbol=symbol,
                direction=prediction_type,
                reason=reason
            )

        if symbol not in SUPPORTED_SYMBOLS:
            reason = f"Symbol {symbol} not in supported pairs"
            EXECUTION_TOTAL.labels(
                symbol=symbol,
                direction=prediction_type,
                status='skipped'
            ).inc()
            return ExecutionResult(
                status=ExecutionStatus.SKIPPED,
                executed=False,
                symbol=symbol,
                direction=prediction_type,
                reason=reason
            )

        # Calculate position size
        portfolio_value = await self.get_portfolio_value()
        position_usd = min(
            portfolio_value * self.position_size_pct,
            self.max_order_value
        )

        # Map prediction type to trading signal
        signal = "buy" if prediction_type == "up" else "sell"

        # Build webhook payload (TradingView format for OctoBot)
        payload = self._build_webhook_payload(
            symbol=symbol,
            signal=signal,
            amount_usd=position_usd,
            tag=f"claude-{cycle_id}"
        )

        try:
            # Send to OctoBot webhook
            result = await self._send_webhook(payload)

            latency = time.time() - start_time
            EXECUTION_LATENCY.observe(latency)

            if result.get('success', False):
                order_id = result.get('order_id', f"exec-{int(time.time())}")
                EXECUTION_TOTAL.labels(
                    symbol=symbol,
                    direction=signal,
                    status='executed'
                ).inc()
                EXECUTION_VALUE.labels(
                    symbol=symbol,
                    direction=signal
                ).inc(position_usd)

                logger.info(
                    f'{{"event":"execute_signal_success",'
                    f'"order_id":"{order_id}",'
                    f'"symbol":"{symbol}",'
                    f'"signal":"{signal}",'
                    f'"position_usd":{position_usd:.2f},'
                    f'"latency_seconds":{latency:.3f}}}'
                )

                return ExecutionResult(
                    status=ExecutionStatus.EXECUTED,
                    executed=True,
                    order_id=order_id,
                    symbol=symbol,
                    direction=signal,
                    position_usd=position_usd,
                    webhook_response=result
                )
            else:
                error_msg = result.get('error', 'Unknown webhook error')
                EXECUTION_TOTAL.labels(
                    symbol=symbol,
                    direction=signal,
                    status='failed'
                ).inc()

                logger.error(
                    f'{{"event":"execute_signal_failed",'
                    f'"symbol":"{symbol}",'
                    f'"error":"{error_msg}"}}'
                )

                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    executed=False,
                    symbol=symbol,
                    direction=signal,
                    position_usd=position_usd,
                    reason=error_msg,
                    webhook_response=result
                )

        except Exception as e:
            EXECUTION_TOTAL.labels(
                symbol=symbol,
                direction=signal,
                status='failed'
            ).inc()

            logger.exception(
                f'{{"event":"execute_signal_error",'
                f'"symbol":"{symbol}",'
                f'"error":"{str(e)}"}}'
            )

            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                executed=False,
                symbol=symbol,
                direction=signal,
                reason=str(e)
            )

    def _build_webhook_payload(
        self,
        symbol: str,
        signal: str,
        amount_usd: float,
        tag: str
    ) -> str:
        """
        Build TradingView-compatible webhook payload for OctoBot.

        OctoBot's TradingViewSignalsTradingMode expects a specific format.
        """
        # TradingView webhook format for OctoBot
        payload = f"""TOKEN={self.webhook_token}
EXCHANGE=phemex
TRADING_TYPE=spot
SYMBOL={symbol}
SIGNAL={signal}
ORDER_TYPE=market
VOLUME={amount_usd:.2f}
TAG={tag}"""
        return payload

    async def _send_webhook(self, payload: str) -> dict:
        """
        Send webhook payload to OctoBot.

        Args:
            payload: TradingView-formatted webhook payload

        Returns:
            Response dict with success status and order details
        """
        webhook_url = f"{self.octobot_url}/webhook/trading_view"

        try:
            session = await self._get_session()
            async with session.post(
                webhook_url,
                data=payload,
                headers={"Content-Type": "text/plain"}
            ) as response:
                response_text = await response.text()

                if response.status == 200:
                    # Try to parse as JSON
                    try:
                        import json
                        data = json.loads(response_text)
                        return {
                            'success': True,
                            'order_id': data.get('order_id'),
                            'response': data
                        }
                    except:
                        # Plain text success response
                        return {
                            'success': True,
                            'response': response_text
                        }
                else:
                    return {
                        'success': False,
                        'error': f"HTTP {response.status}: {response_text}"
                    }

        except aiohttp.ClientError as e:
            return {
                'success': False,
                'error': f"Connection error: {str(e)}"
            }
        except Exception as e:
            return {
                'success': False,
                'error': f"Unexpected error: {str(e)}"
            }

    async def check_octobot_health(self) -> dict:
        """
        Check OctoBot container health.

        Note: OctoBot doesn't have a REST API, so we check if the web interface
        is accessible instead.

        Returns:
            Health status dict
        """
        try:
            session = await self._get_session()
            # OctoBot serves HTML on root - check if it responds
            async with session.get(
                f"{self.octobot_url}/",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                if response.status == 200:
                    # OctoBot web UI is responding
                    return {
                        'healthy': True,
                        'status': 'running',
                        'version': 'OctoBot',  # Can't get version from web UI
                        'url': self.octobot_url,
                        'mode': 'paper_trading',
                        'note': 'OctoBot web interface accessible'
                    }
                else:
                    return {
                        'healthy': False,
                        'status': f"HTTP {response.status}",
                        'url': self.octobot_url
                    }
        except Exception as e:
            return {
                'healthy': False,
                'status': 'unreachable',
                'error': str(e),
                'url': self.octobot_url
            }

    async def get_portfolio(self, db=None) -> dict:
        """
        Get paper trading portfolio calculated from synced trade outcomes.

        Note: OctoBot doesn't have a REST API, so we calculate portfolio
        from our synced trade_outcomes table.

        Args:
            db: SQLAlchemy session (optional, will create if not provided)

        Returns:
            Portfolio dict with balances and P&L
        """
        try:
            # Calculate portfolio from trade outcomes
            from app.models import init_database, get_db_session
            from sqlalchemy import func, text

            close_session = False
            if db is None:
                engine = init_database()
                db = get_db_session(engine)
                close_session = True

            try:
                # Get total P&L from trade_outcomes
                result = db.execute(text("""
                    SELECT
                        COALESCE(SUM(pnl), 0) as total_pnl,
                        COUNT(*) as trade_count
                    FROM trading_predictions.trade_outcomes
                    WHERE status = 'closed'
                """)).fetchone()

                total_pnl = float(result[0]) if result else 0.0
                trade_count = int(result[1]) if result else 0

                # Starting capital (paper trading)
                starting_capital = 10000.0
                current_value = starting_capital + total_pnl

                return {
                    'success': True,
                    'portfolio': {
                        'starting_capital': starting_capital,
                        'current_value': current_value,
                        'total_pnl': total_pnl,
                        'pnl_percent': (total_pnl / starting_capital * 100) if starting_capital > 0 else 0,
                        'trade_count': trade_count
                    },
                    'total_value_usd': current_value,
                    'source': 'synced_trades'
                }
            finally:
                if close_session:
                    db.close()

        except Exception as e:
            logger.error(f"Failed to get portfolio: {e}")
            return {
                'success': False,
                'portfolio': None,
                'total_value_usd': None,
                'error': str(e)
            }

    async def get_open_orders(self, db=None) -> dict:
        """
        Get currently open orders from synced trade outcomes.

        Note: OctoBot doesn't have a REST API, so we query our database.

        Returns:
            Open orders list
        """
        try:
            from app.models import init_database, get_db_session
            from sqlalchemy import text

            close_session = False
            if db is None:
                engine = init_database()
                db = get_db_session(engine)
                close_session = True

            try:
                result = db.execute(text("""
                    SELECT
                        id, octobot_order_id, symbol, action, entry_price,
                        quantity, status, executed_at
                    FROM trading_predictions.trade_outcomes
                    WHERE status = 'open'
                    ORDER BY executed_at DESC
                    LIMIT 50
                """)).fetchall()

                orders = []
                for row in result:
                    orders.append({
                        'id': row[0],
                        'octobot_order_id': row[1],
                        'symbol': row[2],
                        'side': row[3],
                        'price': float(row[4]) if row[4] else None,
                        'amount': float(row[5]) if row[5] else None,
                        'status': row[6],
                        'created_at': row[7].isoformat() if row[7] else None
                    })

                return {
                    'success': True,
                    'orders': orders,
                    'count': len(orders),
                    'source': 'synced_trades'
                }
            finally:
                if close_session:
                    db.close()

        except Exception as e:
            logger.error(f"Failed to get open orders: {e}")
            return {
                'success': False,
                'orders': [],
                'error': str(e)
            }

    async def get_closed_orders(self, limit: int = 100, db=None) -> dict:
        """
        Get closed orders from synced trade outcomes.

        Args:
            limit: Maximum number of orders to fetch
            db: SQLAlchemy session (optional)

        Returns:
            Closed orders list with success status
        """
        try:
            from app.models import init_database, get_db_session
            from sqlalchemy import text

            close_session = False
            if db is None:
                engine = init_database()
                db = get_db_session(engine)
                close_session = True

            try:
                result = db.execute(text("""
                    SELECT
                        id, octobot_order_id, symbol, action, entry_price,
                        exit_price, quantity, pnl, status, executed_at, closed_at,
                        was_auto_executed, execution_confidence
                    FROM trading_predictions.trade_outcomes
                    WHERE status = 'closed'
                    ORDER BY closed_at DESC NULLS LAST, executed_at DESC
                    LIMIT :limit
                """), {'limit': limit}).fetchall()

                orders = []
                for row in result:
                    orders.append({
                        'id': row[0],
                        'octobot_order_id': row[1],
                        'symbol': row[2],
                        'side': row[3],
                        'entry_price': float(row[4]) if row[4] else None,
                        'exit_price': float(row[5]) if row[5] else None,
                        'amount': float(row[6]) if row[6] else None,
                        'pnl': float(row[7]) if row[7] else None,
                        'status': row[8],
                        'created_at': row[9].isoformat() if row[9] else None,
                        'closed_at': row[10].isoformat() if row[10] else None,
                        'was_auto_executed': row[11],
                        'execution_confidence': float(row[12]) if row[12] else None
                    })

                return {
                    'success': True,
                    'orders': orders,
                    'count': len(orders),
                    'source': 'synced_trades'
                }
            finally:
                if close_session:
                    db.close()

        except Exception as e:
            logger.error(f"Failed to get closed orders: {e}")
            return {
                'success': False,
                'orders': [],
                'error': str(e)
            }

    async def get_order_by_id(self, order_id: str) -> dict:
        """
        Fetch specific order details from OctoBot.

        Args:
            order_id: OctoBot order ID

        Returns:
            Order details dictionary
        """
        try:
            session = await self._get_session()
            async with session.get(
                f"{self.octobot_url}/api/orders/{order_id}"
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        'success': True,
                        'order': data
                    }
                else:
                    return {
                        'success': False,
                        'error': f"HTTP {response.status}"
                    }
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }

    async def get_trade_history(
        self,
        symbol: str = None,
        days: int = 30
    ) -> dict:
        """
        Fetch complete trade history from OctoBot.

        Args:
            symbol: Optional symbol filter
            days: Number of days of history

        Returns:
            Trade history list with success status
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
                    return {
                        'success': True,
                        'trades': trades,
                        'count': len(trades)
                    }
                else:
                    return {
                        'success': False,
                        'trades': [],
                        'error': f"HTTP {response.status}"
                    }
        except Exception as e:
            return {
                'success': False,
                'trades': [],
                'error': str(e)
            }


# Singleton instance
_executor: Optional[OrderExecutorService] = None


def get_order_executor() -> OrderExecutorService:
    """Get or create the order executor singleton."""
    global _executor
    if _executor is None:
        _executor = OrderExecutorService()
    return _executor


async def cleanup_executor():
    """Cleanup the executor on shutdown."""
    global _executor
    if _executor:
        await _executor.close()
        _executor = None
