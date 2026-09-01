"""
BeetleLabs Celery Background Tasks for Payments & Billing
=========================================================
Asynchronous workers for:
- Webhook background processing
- Periodic order reconciliation
- Failed payment recovery retry
"""
import logging
from app.celery_app import celery_app

logger = logging.getLogger("beetlelabs.billing.tasks")


@celery_app.task(name="billing.reconcile_pending_orders", bind=True, max_retries=3, default_retry_delay=60)
def reconcile_pending_orders_task(self):
    """
    Background job scanning for stale ORDER_CREATED records older than 30 minutes
    and reconciling with Razorpay API to catch missed webhooks.
    """
    import asyncio
    from app.database import AsyncSessionLocal
    from app.modules.billing.services.razorpay_service import RazorpayProductionService
    from app.models.payment_models import PaymentOrder, PaymentStatus
    from sqlalchemy import select, and_
    from datetime import datetime, timezone, timedelta

    async def _run():
        async with AsyncSessionLocal() as session:
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
            stmt = select(PaymentOrder).where(
                and_(
                    PaymentOrder.status == PaymentStatus.ORDER_CREATED.value,
                    PaymentOrder.created_at < cutoff
                )
            ).limit(20)
            orders = (await session.execute(stmt)).scalars().all()
            service = RazorpayProductionService(session)
            for order in orders:
                try:
                    await service.reconcile_order(order.broker, str(order.id))
                except Exception as e:
                    logger.warning(f"[Reconcile Task] Failed to reconcile order {order.id}: {e}")

    try:
        asyncio.run(_run())
        return {"status": "success"}
    except Exception as exc:
        logger.error(f"[Reconcile Task] Error: {exc}")
        raise self.retry(exc=exc)
