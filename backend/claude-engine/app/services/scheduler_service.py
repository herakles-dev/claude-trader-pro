"""
APScheduler Service for Automated Trading Predictions

This service manages scheduled prediction jobs with:
- SQLAlchemy job store (PostgreSQL persistence)
- Hourly prediction scheduling
- Budget monitoring ($10/day limit)
- Error handling with retry logic
- Prometheus metrics
- Loki logging integration

Author: Backend Architect
Date: 2025-11-12
"""

import logging
import os
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import (
    EVENT_JOB_EXECUTED, 
    EVENT_JOB_ERROR,
    EVENT_JOB_MISSED,
    JobExecutionEvent
)
from prometheus_client import Counter, Histogram, Gauge
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError

logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp":"%(asctime)s","service":"scheduler","level":"%(levelname)s","message":"%(message)s","function":"%(funcName)s"}'
)
logger = logging.getLogger(__name__)

PREDICTION_JOB_RUNS_TOTAL = Counter(
    'prediction_job_runs_total',
    'Total number of prediction job executions',
    ['status']
)
PREDICTION_JOB_FAILURES_TOTAL = Counter(
    'prediction_job_failures_total',
    'Total number of prediction job failures',
    ['error_type']
)
PREDICTION_JOB_DURATION_SECONDS = Histogram(
    'prediction_job_duration_seconds',
    'Duration of prediction job execution in seconds',
    buckets=[5, 10, 30, 60, 120, 300, 600]
)
SCHEDULER_STATUS = Gauge(
    'scheduler_status',
    'Scheduler status (1=running, 0=stopped)'
)
DAILY_BUDGET_REMAINING = Gauge(
    'daily_budget_remaining_usd',
    'Remaining budget for today in USD'
)
DAILY_COST_TOTAL = Gauge(
    'daily_cost_total_usd',
    'Total cost spent today in USD'
)

PREDICTION_ENABLED = os.getenv('PREDICTION_ENABLED', 'true').lower() == 'true'
PREDICTION_INTERVAL_MINUTES = int(os.getenv('PREDICTION_INTERVAL_MINUTES', '60'))
EVALUATION_ENABLED = os.getenv('EVALUATION_ENABLED', 'true').lower() == 'true'
EVALUATION_INTERVAL_MINUTES = int(os.getenv('EVALUATION_INTERVAL_MINUTES', '30'))
TRADE_TRACKING_ENABLED = os.getenv('TRADE_TRACKING_ENABLED', 'true').lower() == 'true'
TRADE_POLL_INTERVAL_SECONDS = int(os.getenv('TRADE_POLL_INTERVAL', '30'))
AUTO_EXECUTE_ENABLED = os.getenv('AUTO_EXECUTE_ENABLED', 'true').lower() == 'true'
EXECUTION_CONFIDENCE_THRESHOLD = float(os.getenv('EXECUTION_CONFIDENCE_THRESHOLD', '0.70'))
OCTOBOT_SYNC_ENABLED = os.getenv('OCTOBOT_SYNC_ENABLED', 'true').lower() == 'true'
OCTOBOT_SYNC_INTERVAL_SECONDS = int(os.getenv('OCTOBOT_SYNC_INTERVAL', '300'))  # 5 minutes

# Use centralized DatabaseConfig - no hardcoded fallback
def get_database_url() -> str:
    """Get database URL from environment or DatabaseConfig"""
    url = os.getenv('DATABASE_URL')
    if url:
        return url
    # Fall back to DatabaseConfig which requires POSTGRES_PASSWORD
    from app.models.prediction import DatabaseConfig
    return DatabaseConfig.get_connection_string()

DATABASE_URL = get_database_url()
DAILY_BUDGET_LIMIT = float(os.getenv('DAILY_BUDGET_LIMIT', '10.0'))
MAX_RETRIES = int(os.getenv('PREDICTION_MAX_RETRIES', '3'))
RETRY_BASE_DELAY = int(os.getenv('PREDICTION_RETRY_BASE_DELAY', '5'))

scheduler: Optional[BackgroundScheduler] = None
db_session_maker = None


class BudgetExceededError(Exception):
    """Raised when daily budget limit is exceeded"""
    pass


def get_db_session():
    """Get database session for queries"""
    global db_session_maker
    if not db_session_maker:
        engine = create_engine(
            DATABASE_URL,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True
        )
        db_session_maker = sessionmaker(bind=engine)
    
    return db_session_maker()


# Advisory lock key for budget checking (prevents race conditions)
BUDGET_LOCK_KEY = 8108001  # Unique identifier for budget lock


def check_budget() -> tuple[float, float]:
    """
    Check daily budget from daily_cost_summary view.

    Returns:
        Tuple of (total_cost_today, budget_remaining)

    Raises:
        BudgetExceededError: If daily budget limit exceeded
    """
    session = get_db_session()

    try:
        query = text("""
            SELECT
                COALESCE(SUM(total_cost_usd), 0) as daily_cost
            FROM trading_predictions.automated_predictions
            WHERE DATE(created_at) = CURRENT_DATE
        """)

        result = session.execute(query).fetchone()
        daily_cost = float(result[0]) if result else 0.0
        budget_remaining = DAILY_BUDGET_LIMIT - daily_cost

        DAILY_COST_TOTAL.set(daily_cost)
        DAILY_BUDGET_REMAINING.set(budget_remaining)

        logger.info(
            f'{{"event":"budget_check","daily_cost":{daily_cost:.4f},'
            f'"budget_limit":{DAILY_BUDGET_LIMIT},"remaining":{budget_remaining:.4f}}}'
        )

        if daily_cost >= DAILY_BUDGET_LIMIT:
            raise BudgetExceededError(
                f"Daily budget limit exceeded: ${daily_cost:.4f} >= ${DAILY_BUDGET_LIMIT}"
            )

        return daily_cost, budget_remaining

    except OperationalError as e:
        logger.error(f'{{"event":"budget_check_error","error":"{str(e)}"}}')
        PREDICTION_JOB_FAILURES_TOTAL.labels(error_type='database_error').inc()
        raise
    finally:
        session.close()


def acquire_budget_lock(session) -> bool:
    """
    Acquire PostgreSQL advisory lock for budget operations.
    This prevents race conditions where multiple workers check budget simultaneously.

    Args:
        session: SQLAlchemy database session

    Returns:
        True if lock acquired, False otherwise
    """
    try:
        # Try to acquire advisory lock (non-blocking)
        result = session.execute(
            text("SELECT pg_try_advisory_lock(:lock_key)"),
            {"lock_key": BUDGET_LOCK_KEY}
        ).fetchone()
        return result[0] if result else False
    except Exception as e:
        logger.error(f'{{"event":"budget_lock_acquire_failed","error":"{str(e)}"}}')
        return False


def release_budget_lock(session) -> None:
    """
    Release PostgreSQL advisory lock for budget operations.

    Args:
        session: SQLAlchemy database session
    """
    try:
        session.execute(
            text("SELECT pg_advisory_unlock(:lock_key)"),
            {"lock_key": BUDGET_LOCK_KEY}
        )
    except Exception as e:
        logger.warning(f'{{"event":"budget_lock_release_failed","error":"{str(e)}"}}')


def run_hourly_prediction_with_retry(retry_count: int = 0):
    """
    Execute hourly prediction with exponential backoff retry logic.

    Uses PostgreSQL advisory lock to prevent race conditions where multiple
    workers could exceed the budget limit simultaneously.
    """
    start_time = time.time()
    session = get_db_session()
    lock_acquired = False

    try:
        # Acquire advisory lock to prevent race conditions
        lock_acquired = acquire_budget_lock(session)
        if not lock_acquired:
            logger.warning(
                f'{{"event":"prediction_skipped","reason":"budget_lock_busy",'
                f'"retry_count":{retry_count}}}'
            )
            PREDICTION_JOB_RUNS_TOTAL.labels(status='skipped').inc()
            return

        try:
            daily_cost, budget_remaining = check_budget()
        except BudgetExceededError as e:
            logger.warning(
                f'{{"event":"prediction_skipped","reason":"budget_exceeded",'
                f'"error":"{str(e)}","limit":{DAILY_BUDGET_LIMIT}}}'
            )
            PREDICTION_JOB_RUNS_TOTAL.labels(status='skipped').inc()
            return
        except Exception as e:
            logger.error(f'{{"event":"budget_check_failed","error":"{str(e)}"}}')
            PREDICTION_JOB_FAILURES_TOTAL.labels(error_type='budget_check_error').inc()
            raise

        logger.info(
            f'{{"event":"prediction_job_started","retry_count":{retry_count},'
            f'"budget_remaining":{budget_remaining:.4f}}}'
        )

        from app.services.prediction_worker import generate_automated_prediction

        symbol = os.getenv('DEFAULT_PREDICTION_SYMBOL', 'BTC/USDT')
        # Use force=True in test mode (interval < 60 min) to bypass cycle duplicate check
        force_mode = PREDICTION_INTERVAL_MINUTES < 60
        result = generate_automated_prediction(symbol, force=force_mode)
        
        duration = time.time() - start_time
        PREDICTION_JOB_DURATION_SECONDS.observe(duration)
        PREDICTION_JOB_RUNS_TOTAL.labels(status='success').inc()
        
        logger.info(
            f'{{"event":"prediction_job_completed","symbol":"{symbol}",'
            f'"prediction_type":"{result.get("prediction_type")}",'
            f'"confidence":{result.get("confidence")},"duration_seconds":{duration:.2f}}}'
        )

        # Auto-execute if enabled and confidence meets threshold
        if AUTO_EXECUTE_ENABLED:
            confidence = result.get("confidence", 0)
            if confidence >= EXECUTION_CONFIDENCE_THRESHOLD:
                try:
                    from app.services.order_executor_service import get_order_executor
                    import asyncio

                    # Get the prediction object from database
                    prediction_id = result.get("id")
                    if prediction_id:
                        from app.models import AutomatedPrediction
                        prediction = session.query(AutomatedPrediction).filter(
                            AutomatedPrediction.id == prediction_id
                        ).first()

                        if prediction:
                            executor = get_order_executor()
                            # Run async execution in sync context
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            try:
                                exec_result = loop.run_until_complete(
                                    executor.execute_signal(prediction)
                                )
                                logger.info(
                                    f'{{"event":"auto_execute_completed",'
                                    f'"symbol":"{symbol}",'
                                    f'"executed":{exec_result.executed},'
                                    f'"status":"{exec_result.status.value}",'
                                    f'"order_id":"{exec_result.order_id}"}}'
                                )
                            finally:
                                loop.close()
                except Exception as exec_error:
                    logger.error(
                        f'{{"event":"auto_execute_failed",'
                        f'"symbol":"{symbol}",'
                        f'"error":"{str(exec_error)}"}}'
                    )
            else:
                logger.info(
                    f'{{"event":"auto_execute_skipped",'
                    f'"reason":"below_threshold",'
                    f'"confidence":{confidence},'
                    f'"threshold":{EXECUTION_CONFIDENCE_THRESHOLD}}}'
                )
        else:
            logger.debug('{"event":"auto_execute_disabled"}')
        
    except Exception as e:
        error_type = type(e).__name__
        duration = time.time() - start_time

        logger.error(
            f'{{"event":"prediction_job_error","error_type":"{error_type}",'
            f'"error":"{str(e)}","retry_count":{retry_count},'
            f'"duration_seconds":{duration:.2f}}}'
        )

        PREDICTION_JOB_FAILURES_TOTAL.labels(error_type=error_type).inc()
        PREDICTION_JOB_RUNS_TOTAL.labels(status='failure').inc()

        if retry_count < MAX_RETRIES:
            delay = RETRY_BASE_DELAY * (2 ** retry_count)
            logger.info(
                f'{{"event":"prediction_job_retry","retry_count":{retry_count + 1},'
                f'"delay_seconds":{delay}}}'
            )

            scheduler.add_job(
                func=run_hourly_prediction_with_retry,
                trigger='date',
                run_date=datetime.now() + timedelta(seconds=delay),
                args=[retry_count + 1],
                id=f'prediction_retry_{retry_count + 1}_{int(time.time())}',
                replace_existing=False
            )
        else:
            logger.error(
                f'{{"event":"prediction_job_failed","reason":"max_retries_exceeded",'
                f'"max_retries":{MAX_RETRIES}}}'
            )

    finally:
        # Always release the budget lock and close session
        if lock_acquired:
            release_budget_lock(session)
        session.close()


def run_hourly_prediction():
    """Wrapper function for scheduled prediction job"""
    run_hourly_prediction_with_retry(retry_count=0)


def job_listener(event: JobExecutionEvent):
    """APScheduler event listener for job execution tracking"""
    if event.exception:
        logger.error(
            f'{{"event":"job_error","job_id":"{event.job_id}",'
            f'"exception":"{str(event.exception)}"}}'
        )
    else:
        logger.info(
            f'{{"event":"job_executed","job_id":"{event.job_id}",'
            f'"scheduled_run_time":"{event.scheduled_run_time}"}}'
        )


def start_scheduler():
    """Initialize and start APScheduler with SQLAlchemy job store"""
    global scheduler
    
    if scheduler and scheduler.running:
        logger.warning('{"event":"scheduler_already_running"}')
        return
    
    logger.info('{"event":"scheduler_starting"}')
    
    try:
        jobstores = {
            'default': SQLAlchemyJobStore(
                url=DATABASE_URL,
                tablename='apscheduler_jobs',
                metadata=None
            )
        }
        
        executors = {
            'default': ThreadPoolExecutor(max_workers=5)
        }
        
        job_defaults = {
            'coalesce': True,
            'max_instances': 1,
            'misfire_grace_time': 300
        }
        
        scheduler = BackgroundScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone='UTC'
        )
        
        scheduler.add_listener(job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
        
        scheduler.start()
        SCHEDULER_STATUS.set(1)
        
        logger.info(
            f'{{"event":"scheduler_started","recovered_jobs":{len(scheduler.get_jobs())}}}'
        )
        
        if not PREDICTION_ENABLED:
            logger.warning(
                '{"event":"predictions_disabled","reason":"PREDICTION_ENABLED=false"}'
            )
            return
        
        job_id = 'hourly_prediction_job'
        existing_job = scheduler.get_job(job_id)
        
        if existing_job:
            logger.info(
                f'{{"event":"job_recovered","job_id":"{job_id}",'
                f'"next_run":"{existing_job.next_run_time}"}}'
            )
        else:
            if PREDICTION_INTERVAL_MINUTES == 60:
                trigger = CronTrigger(minute=0, timezone='UTC')
            else:
                trigger = CronTrigger(
                    minute=f'*/{PREDICTION_INTERVAL_MINUTES}',
                    timezone='UTC'
                )
            
            scheduler.add_job(
                func=run_hourly_prediction,
                trigger=trigger,
                id=job_id,
                name='Hourly Crypto Prediction Job',
                replace_existing=False
            )
            
            logger.info(
                f'{{"event":"job_scheduled","job_id":"{job_id}",'
                f'"interval_minutes":{PREDICTION_INTERVAL_MINUTES},'
                f'"next_run":"{scheduler.get_job(job_id).next_run_time}"}}'
            )

        # Schedule evaluation job (runs every 30 minutes by default)
        if EVALUATION_ENABLED:
            eval_job_id = 'prediction_evaluation_job'
            existing_eval_job = scheduler.get_job(eval_job_id)

            if existing_eval_job:
                logger.info(
                    f'{{"event":"job_recovered","job_id":"{eval_job_id}",'
                    f'"next_run":"{existing_eval_job.next_run_time}"}}'
                )
            else:
                from app.services.evaluation_worker import run_evaluation_sync

                eval_trigger = CronTrigger(
                    minute=f'*/{EVALUATION_INTERVAL_MINUTES}',
                    timezone='UTC'
                )

                scheduler.add_job(
                    func=run_evaluation_sync,
                    trigger=eval_trigger,
                    id=eval_job_id,
                    name='Prediction Evaluation Job',
                    replace_existing=False
                )

                logger.info(
                    f'{{"event":"job_scheduled","job_id":"{eval_job_id}",'
                    f'"interval_minutes":{EVALUATION_INTERVAL_MINUTES},'
                    f'"next_run":"{scheduler.get_job(eval_job_id).next_run_time}"}}'
                )
        else:
            logger.warning(
                '{"event":"evaluation_disabled","reason":"EVALUATION_ENABLED=false"}'
            )

        # Schedule trade tracking job (polls OctoBot every 30 seconds by default)
        if TRADE_TRACKING_ENABLED:
            trade_job_id = 'trade_tracking_job'
            existing_trade_job = scheduler.get_job(trade_job_id)

            if existing_trade_job:
                logger.info(
                    f'{{"event":"job_recovered","job_id":"{trade_job_id}",'
                    f'"next_run":"{existing_trade_job.next_run_time}"}}'
                )
            else:
                from app.services.trade_tracker_service import run_poll_cycle_sync
                from apscheduler.triggers.interval import IntervalTrigger

                trade_trigger = IntervalTrigger(seconds=TRADE_POLL_INTERVAL_SECONDS)

                scheduler.add_job(
                    func=run_poll_cycle_sync,
                    trigger=trade_trigger,
                    id=trade_job_id,
                    name='OctoBot Trade Tracking Job',
                    replace_existing=False
                )

                logger.info(
                    f'{{"event":"job_scheduled","job_id":"{trade_job_id}",'
                    f'"interval_seconds":{TRADE_POLL_INTERVAL_SECONDS},'
                    f'"next_run":"{scheduler.get_job(trade_job_id).next_run_time}"}}'
                )
        else:
            logger.warning(
                '{"event":"trade_tracking_disabled","reason":"TRADE_TRACKING_ENABLED=false"}'
            )

        # Schedule OctoBot sync job (runs every 5 minutes by default)
        if OCTOBOT_SYNC_ENABLED:
            sync_job_id = 'octobot_sync_job'
            existing_sync_job = scheduler.get_job(sync_job_id)

            if existing_sync_job:
                logger.info(
                    f'{{"event":"job_recovered","job_id":"{sync_job_id}",'
                    f'"next_run":"{existing_sync_job.next_run_time}"}}'
                )
            else:
                from app.services.octobot_sync_service import run_sync_cycle_sync
                from apscheduler.triggers.interval import IntervalTrigger

                sync_trigger = IntervalTrigger(seconds=OCTOBOT_SYNC_INTERVAL_SECONDS)

                scheduler.add_job(
                    func=run_sync_cycle_sync,
                    trigger=sync_trigger,
                    id=sync_job_id,
                    name='OctoBot Sync Job',
                    replace_existing=False
                )

                logger.info(
                    f'{{"event":"job_scheduled","job_id":"{sync_job_id}",'
                    f'"interval_seconds":{OCTOBOT_SYNC_INTERVAL_SECONDS},'
                    f'"next_run":"{scheduler.get_job(sync_job_id).next_run_time}"}}'
                )

            # Schedule daily reconciliation job (runs at 00:30 UTC)
            reconcile_job_id = 'octobot_reconcile_job'
            existing_reconcile_job = scheduler.get_job(reconcile_job_id)

            if existing_reconcile_job:
                logger.info(
                    f'{{"event":"job_recovered","job_id":"{reconcile_job_id}",'
                    f'"next_run":"{existing_reconcile_job.next_run_time}"}}'
                )
            else:
                from app.services.octobot_sync_service import run_reconciliation_sync

                reconcile_trigger = CronTrigger(hour=0, minute=30, timezone='UTC')

                scheduler.add_job(
                    func=run_reconciliation_sync,
                    trigger=reconcile_trigger,
                    id=reconcile_job_id,
                    name='OctoBot Daily Reconciliation',
                    replace_existing=False
                )

                logger.info(
                    f'{{"event":"job_scheduled","job_id":"{reconcile_job_id}",'
                    f'"schedule":"00:30 UTC daily",'
                    f'"next_run":"{scheduler.get_job(reconcile_job_id).next_run_time}"}}'
                )
        else:
            logger.warning(
                '{"event":"octobot_sync_disabled","reason":"OCTOBOT_SYNC_ENABLED=false"}'
            )

        for job in scheduler.get_jobs():
            logger.info(
                f'{{"event":"scheduled_job","id":"{job.id}","name":"{job.name}",'
                f'"next_run":"{job.next_run_time}"}}'
            )
        
    except Exception as e:
        logger.error(f'{{"event":"scheduler_start_error","error":"{str(e)}"}}')
        SCHEDULER_STATUS.set(0)
        raise


def shutdown_scheduler(wait: bool = True):
    """Gracefully shutdown APScheduler"""
    global scheduler
    
    if not scheduler:
        logger.warning('{"event":"scheduler_not_running"}')
        return
    
    logger.info(
        f'{{"event":"scheduler_stopping","wait_for_jobs":{wait},'
        f'"running_jobs":{len(scheduler.get_jobs())}}}'
    )
    
    try:
        scheduler.shutdown(wait=wait)
        SCHEDULER_STATUS.set(0)
        logger.info('{"event":"scheduler_stopped"}')
    except Exception as e:
        logger.error(f'{{"event":"scheduler_shutdown_error","error":"{str(e)}"}}')
        raise


def get_scheduler_status() -> dict:
    """Get current scheduler status and job information"""
    if not scheduler:
        return {
            'running': False,
            'jobs': []
        }
    
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            'id': job.id,
            'name': job.name,
            'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
            'trigger': str(job.trigger)
        })
    
    return {
        'running': scheduler.running,
        'prediction_enabled': PREDICTION_ENABLED,
        'interval_minutes': PREDICTION_INTERVAL_MINUTES,
        'daily_budget_limit': DAILY_BUDGET_LIMIT,
        'jobs': jobs
    }


def trigger_prediction_now():
    """Manually trigger a prediction job immediately"""
    if not scheduler:
        raise RuntimeError("Scheduler not initialized")

    logger.info('{"event":"manual_prediction_triggered"}')

    scheduler.add_job(
        func=run_hourly_prediction,
        trigger='date',
        run_date=datetime.now(),
        id=f'manual_prediction_{int(time.time())}',
        replace_existing=False
    )


def trigger_evaluation_now():
    """Manually trigger an evaluation job immediately"""
    if not scheduler:
        raise RuntimeError("Scheduler not initialized")

    logger.info('{"event":"manual_evaluation_triggered"}')

    from app.services.evaluation_worker import run_evaluation_sync

    scheduler.add_job(
        func=run_evaluation_sync,
        trigger='date',
        run_date=datetime.now(),
        id=f'manual_evaluation_{int(time.time())}',
        replace_existing=False
    )


def trigger_trade_poll_now():
    """Manually trigger a trade tracking poll immediately"""
    if not scheduler:
        raise RuntimeError("Scheduler not initialized")

    logger.info('{"event":"manual_trade_poll_triggered"}')

    from app.services.trade_tracker_service import run_poll_cycle_sync

    scheduler.add_job(
        func=run_poll_cycle_sync,
        trigger='date',
        run_date=datetime.now(),
        id=f'manual_trade_poll_{int(time.time())}',
        replace_existing=False
    )
