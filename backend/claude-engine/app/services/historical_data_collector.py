"""
Historical Data Collector for OctoBot Backtesting

Collects and maintains OHLCV historical data for backtesting validation.
Outputs OctoBot-compatible JSON files to $OCTOBOT_DATA_DIR (default: ./octobot/backtesting/data_files/)

Features:
- Fetches 6 months of 1H OHLCV data from Binance via CCXT
- Saves in OctoBot-compatible format
- Incremental updates (only fetches new data)
- Scheduled weekly refresh

Author: Backend Architect
Date: 2026-01-16
"""

import os
import json
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path

import ccxt.async_support as ccxt

logger = logging.getLogger(__name__)

# Configuration
OCTOBOT_DATA_DIR = Path(os.getenv("OCTOBOT_DATA_DIR", "./octobot/backtesting/data_files"))
DEFAULT_SYMBOLS = ["BTC/USDT", "ETH/USDT"]
DEFAULT_TIMEFRAME = "1h"
DEFAULT_MONTHS = 6
EXCHANGE_ID = "binance"


class HistoricalDataCollector:
    """
    Collects and maintains historical OHLCV data for OctoBot backtesting.
    """

    def __init__(
        self,
        symbols: List[str] = None,
        timeframe: str = DEFAULT_TIMEFRAME,
        months: int = DEFAULT_MONTHS
    ):
        self.symbols = symbols or DEFAULT_SYMBOLS
        self.timeframe = timeframe
        self.months = months
        self.exchange: Optional[ccxt.Exchange] = None
        self.data_dir = OCTOBOT_DATA_DIR

        # Ensure data directory exists
        self.data_dir.mkdir(parents=True, exist_ok=True)

    async def __aenter__(self):
        """Async context manager entry"""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()

    async def initialize(self):
        """Initialize the CCXT exchange connection"""
        try:
            self.exchange = ccxt.binance({
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'spot'
                }
            })
            await self.exchange.load_markets()
            logger.info(f"Initialized {EXCHANGE_ID} exchange connection")
        except Exception as e:
            logger.error(f"Failed to initialize exchange: {e}")
            raise

    async def close(self):
        """Close the exchange connection"""
        if self.exchange:
            await self.exchange.close()
            logger.info("Closed exchange connection")

    def _get_data_file_path(self, symbol: str) -> Path:
        """
        Generate the file path for a symbol's data.

        Args:
            symbol: Trading pair (e.g., "BTC/USDT")

        Returns:
            Path to the data file
        """
        # Convert symbol to filename format: BTC/USDT -> BTC_USDT_1h.json
        filename = f"{symbol.replace('/', '_')}_{self.timeframe}.json"
        return self.data_dir / filename

    def _load_existing_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Load existing data file for a symbol if it exists.

        Args:
            symbol: Trading pair

        Returns:
            Existing data dict or None
        """
        file_path = self._get_data_file_path(symbol)

        if file_path.exists():
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    logger.info(f"Loaded existing data for {symbol}: {len(data.get('data', []))} candles")
                    return data
            except Exception as e:
                logger.warning(f"Failed to load existing data for {symbol}: {e}")

        return None

    def _save_data(self, symbol: str, data: Dict[str, Any]) -> bool:
        """
        Save data to file in OctoBot format.

        Args:
            symbol: Trading pair
            data: Data dict to save

        Returns:
            True if successful
        """
        file_path = self._get_data_file_path(symbol)

        try:
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Saved data for {symbol}: {len(data.get('data', []))} candles to {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save data for {symbol}: {e}")
            return False

    async def fetch_ohlcv(
        self,
        symbol: str,
        since: Optional[int] = None,
        limit: int = 1000
    ) -> List[List]:
        """
        Fetch OHLCV data from exchange.

        Args:
            symbol: Trading pair
            since: Start timestamp in milliseconds
            limit: Maximum candles per request

        Returns:
            List of OHLCV candles [[timestamp, open, high, low, close, volume], ...]
        """
        if not self.exchange:
            raise RuntimeError("Exchange not initialized")

        all_candles = []
        current_since = since

        # Calculate target end time
        now = datetime.now(timezone.utc)
        target_end = int(now.timestamp() * 1000)

        # Calculate timeframe duration in milliseconds
        tf_ms = self._timeframe_to_ms(self.timeframe)

        while True:
            try:
                # Fetch batch
                candles = await self.exchange.fetch_ohlcv(
                    symbol,
                    timeframe=self.timeframe,
                    since=current_since,
                    limit=limit
                )

                if not candles:
                    break

                all_candles.extend(candles)
                logger.debug(f"Fetched {len(candles)} candles for {symbol}, total: {len(all_candles)}")

                # Check if we've reached current time
                last_timestamp = candles[-1][0]
                if last_timestamp >= target_end - tf_ms:
                    break

                # Move to next batch
                current_since = last_timestamp + tf_ms

                # Rate limiting
                await asyncio.sleep(0.5)

            except Exception as e:
                logger.error(f"Error fetching OHLCV for {symbol}: {e}")
                break

        return all_candles

    def _timeframe_to_ms(self, timeframe: str) -> int:
        """
        Convert timeframe string to milliseconds.

        Args:
            timeframe: Timeframe string (e.g., "1h", "4h", "1d")

        Returns:
            Duration in milliseconds
        """
        multipliers = {
            'm': 60 * 1000,
            'h': 60 * 60 * 1000,
            'd': 24 * 60 * 60 * 1000,
            'w': 7 * 24 * 60 * 60 * 1000
        }

        unit = timeframe[-1]
        value = int(timeframe[:-1])

        return value * multipliers.get(unit, 60 * 60 * 1000)

    async def collect_symbol_data(self, symbol: str, force_full: bool = False) -> Dict[str, Any]:
        """
        Collect historical data for a single symbol.

        Args:
            symbol: Trading pair
            force_full: If True, fetch full history even if data exists

        Returns:
            Complete data dict in OctoBot format
        """
        logger.info(f"Collecting data for {symbol}...")

        # Check existing data for incremental update
        existing_data = None if force_full else self._load_existing_data(symbol)

        # Calculate start time
        if existing_data and existing_data.get('data'):
            # Incremental: start from last candle
            last_timestamp = existing_data['data'][-1][0]
            since = last_timestamp + self._timeframe_to_ms(self.timeframe)
            logger.info(f"Incremental update for {symbol} from {datetime.fromtimestamp(since/1000, tz=timezone.utc)}")
        else:
            # Full fetch: go back N months
            since = int((datetime.now(timezone.utc) - timedelta(days=self.months * 30)).timestamp() * 1000)
            logger.info(f"Full fetch for {symbol} from {datetime.fromtimestamp(since/1000, tz=timezone.utc)}")

        # Fetch new data
        new_candles = await self.fetch_ohlcv(symbol, since=since)

        # Merge with existing data
        if existing_data and existing_data.get('data') and new_candles:
            # Deduplicate by timestamp
            existing_timestamps = {c[0] for c in existing_data['data']}
            unique_new = [c for c in new_candles if c[0] not in existing_timestamps]
            all_candles = existing_data['data'] + unique_new
            all_candles.sort(key=lambda x: x[0])
            logger.info(f"Merged {len(unique_new)} new candles for {symbol}")
        elif new_candles:
            all_candles = new_candles
        elif existing_data:
            all_candles = existing_data.get('data', [])
        else:
            all_candles = []

        # Build OctoBot-compatible data structure
        data = {
            "exchange": EXCHANGE_ID,
            "symbol": symbol,
            "time_frame": self.timeframe,
            "data": all_candles,
            "metadata": {
                "collected_at": datetime.now(timezone.utc).isoformat(),
                "candle_count": len(all_candles),
                "start_time": datetime.fromtimestamp(all_candles[0][0]/1000, tz=timezone.utc).isoformat() if all_candles else None,
                "end_time": datetime.fromtimestamp(all_candles[-1][0]/1000, tz=timezone.utc).isoformat() if all_candles else None
            }
        }

        return data

    async def collect_all(self, force_full: bool = False) -> Dict[str, Any]:
        """
        Collect historical data for all configured symbols.

        Args:
            force_full: If True, fetch full history for all symbols

        Returns:
            Summary of collection results
        """
        results = {
            "success": [],
            "failed": [],
            "total_candles": 0,
            "collected_at": datetime.now(timezone.utc).isoformat()
        }

        for symbol in self.symbols:
            try:
                data = await self.collect_symbol_data(symbol, force_full=force_full)

                if self._save_data(symbol, data):
                    results["success"].append({
                        "symbol": symbol,
                        "candles": len(data.get("data", [])),
                        "file": str(self._get_data_file_path(symbol))
                    })
                    results["total_candles"] += len(data.get("data", []))
                else:
                    results["failed"].append({
                        "symbol": symbol,
                        "reason": "Failed to save data"
                    })

            except Exception as e:
                logger.exception(f"Failed to collect data for {symbol}: {e}")
                results["failed"].append({
                    "symbol": symbol,
                    "reason": str(e)
                })

        logger.info(f"Collection complete: {len(results['success'])} success, {len(results['failed'])} failed")
        return results

    def get_data_summary(self) -> Dict[str, Any]:
        """
        Get summary of existing data files.

        Returns:
            Summary dict with file info
        """
        summary = {
            "data_directory": str(self.data_dir),
            "files": []
        }

        for symbol in self.symbols:
            file_path = self._get_data_file_path(symbol)

            if file_path.exists():
                data = self._load_existing_data(symbol)
                if data:
                    summary["files"].append({
                        "symbol": symbol,
                        "file": str(file_path),
                        "candles": len(data.get("data", [])),
                        "start": data.get("metadata", {}).get("start_time"),
                        "end": data.get("metadata", {}).get("end_time"),
                        "last_updated": data.get("metadata", {}).get("collected_at")
                    })
            else:
                summary["files"].append({
                    "symbol": symbol,
                    "file": str(file_path),
                    "status": "not_collected"
                })

        return summary


async def run_collection(force_full: bool = False) -> Dict[str, Any]:
    """
    Run data collection (entry point for scheduler).

    Args:
        force_full: If True, fetch full history

    Returns:
        Collection results
    """
    async with HistoricalDataCollector() as collector:
        return await collector.collect_all(force_full=force_full)


def get_data_summary() -> Dict[str, Any]:
    """
    Get summary of existing backtesting data.

    Returns:
        Summary dict
    """
    collector = HistoricalDataCollector()
    return collector.get_data_summary()


# CLI interface for manual testing
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Historical Data Collector for OctoBot")
    parser.add_argument("--full", action="store_true", help="Force full historical fetch")
    parser.add_argument("--summary", action="store_true", help="Show data summary")
    parser.add_argument("--symbols", nargs="+", help="Symbols to collect (default: BTC/USDT ETH/USDT)")
    parser.add_argument("--months", type=int, default=6, help="Months of history to collect")

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    if args.summary:
        summary = get_data_summary()
        print(json.dumps(summary, indent=2))
    else:
        async def main():
            symbols = args.symbols if args.symbols else DEFAULT_SYMBOLS
            async with HistoricalDataCollector(symbols=symbols, months=args.months) as collector:
                results = await collector.collect_all(force_full=args.full)
                print(json.dumps(results, indent=2))

        asyncio.run(main())
