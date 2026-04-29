import logging
import asyncio
import threading
from sqlalchemy.orm import Session
from ..models.database import SessionLocal
from ..models.schema import PaperPosition, PaperOrder
from .oms import OMS
from .price_resolver import PriceResolver

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PositionMonitor")

class PositionMonitor:
    """
    Background monitor that checks all open paper positions 
    against their Stop-Loss and Target levels.
    """
    def __init__(self, interval_seconds: int = 10):
        self.interval = interval_seconds
        self.stop_event = threading.Event()
        self.thread = None

    def start(self):
        if self.thread is not None:
            return
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        logger.info(f"🚀 Position Monitor started (Interval: {self.interval}s)")

    def stop(self):
        self.stop_event.set()
        if self.thread:
            self.thread.join()

    def _run_loop(self):
        while not self.stop_event.is_set():
            try:
                self.check_exits()
            except Exception as e:
                logger.error(f"❌ Error in Position Monitor loop: {e}")
            time_to_wait = self.interval
            while time_to_wait > 0 and not self.stop_event.is_set():
                import time
                time.sleep(1)
                time_to_wait -= 1

    def check_exits(self):
        import datetime
        import pytz
        ist = pytz.timezone('Asia/Kolkata')
        now = datetime.datetime.now(ist)
        
        # Check if we should force square-off (3:25 PM IST)
        is_square_off_time = now.hour == 15 and now.minute >= 25
        if now.hour > 15: is_square_off_time = True

        db = SessionLocal()
        try:
            # Only monitor active positions
            positions = db.query(PaperPosition).filter(PaperPosition.net_qty != 0).all()
            if not positions:
                return

            price_resolver = PriceResolver(db)
            oms = OMS(db)

            for pos in positions:
                if is_square_off_time:
                    logger.info(f"⏰ [MARKET-CLOSE] Force closing {pos.symbol} at {now.strftime('%H:%M')} IST")
                    try:
                        oms.close_symbol_position(pos.symbol, source="market_close_square_off")
                    except Exception as ex:
                        logger.error(f"Failed to market-close {pos.symbol}: {ex}")
                    continue

                # Find the latest filled order that established/modified this position
                # This contains the SL/TP levels in the 'extra' JSONB field
                last_order = db.query(PaperOrder).filter(
                    PaperOrder.symbol == pos.symbol,
                    PaperOrder.status == 'FILLED'
                ).order_by(PaperOrder.created_at.desc()).first()

                if not last_order or not last_order.extra:
                    continue

                extra = last_order.extra
                # levels are typically: stop_loss, target_l1, target_l2, target_l3
                sl = extra.get('stop_loss')
                tp = extra.get('target_l1') or extra.get('target_l2') or extra.get('target_l3')
                
                curr_price = price_resolver.get_latest_price(pos.symbol)
                if curr_price <= 0:
                    continue

                trigger_close = False
                reason = ""

                if pos.net_qty > 0: # Long position
                    if sl and curr_price <= sl:
                        trigger_close = True
                        reason = f"SL Hit: {curr_price} <= {sl}"
                    elif tp and curr_price >= tp:
                        trigger_close = True
                        reason = f"TP Hit: {curr_price} >= {tp}"
                elif pos.net_qty < 0: # Short position
                    if sl and curr_price >= sl:
                        trigger_close = True
                        reason = f"SL Hit: {curr_price} >= {sl}"
                    elif tp and curr_price <= tp:
                        trigger_close = True
                        reason = f"TP Hit: {curr_price} <= {tp}"

                if trigger_close:
                    logger.info(f"🛠️ [AUTO-EXIT] {pos.symbol} | Side: {'LONG' if pos.net_qty > 0 else 'SHORT'} | Reason: {reason}")
                    try:
                        oms.close_symbol_position(pos.symbol, source="auto_exit_engine")
                    except Exception as ex:
                        logger.error(f"Failed to auto-close {pos.symbol}: {ex}")

        finally:
            db.close()
