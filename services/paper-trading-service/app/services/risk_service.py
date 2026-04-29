import os
from sqlalchemy.orm import Session
from ..models.schema import PaperAccount, PaperPosition


class RiskError(Exception):
    pass


class RiskService:
    def __init__(self, db: Session):
        self.db = db
        self.max_open_positions = int(os.getenv("PAPER_MAX_OPEN_POSITIONS", "10"))
        self.max_notional_per_trade = float(os.getenv("PAPER_MAX_NOTIONAL_PER_TRADE", "100000"))
        self.max_position_notional = float(os.getenv("PAPER_MAX_POSITION_NOTIONAL", "150000"))
        self.min_cash_buffer = float(os.getenv("PAPER_MIN_CASH_BUFFER", "50000"))
        self.allow_pyramiding = os.getenv("PAPER_ALLOW_PYRAMIDING", "false").lower() == "true"
        self.allow_direction_flip = os.getenv("PAPER_ALLOW_DIRECTION_FLIP", "true").lower() == "true"

    def validate_new_order(self, symbol: str, side: str, qty: int, market_price: float):
        if qty <= 0:
            raise RiskError("Quantity must be greater than zero")
        if market_price <= 0:
            raise RiskError("Market price unavailable")

        side = side.upper()
        if side not in ("BUY", "LONG", "SELL", "SHORT"):
            raise RiskError(f"Unsupported side: {side}")

        order_notional = market_price * qty
        if order_notional > self.max_notional_per_trade:
            raise RiskError(
                f"Order notional {order_notional:.2f} exceeds per-trade cap {self.max_notional_per_trade:.2f}"
            )

        account = self.db.query(PaperAccount).filter(PaperAccount.id == 1).first()
        if not account:
            raise RiskError("Paper account is not initialized")

        position = self.db.query(PaperPosition).filter(PaperPosition.symbol == symbol).first()
        open_positions = self.db.query(PaperPosition).filter(PaperPosition.net_qty != 0).count()
        signed_qty = qty if side in ("BUY", "LONG") else -qty

        current_qty = position.net_qty if position else 0
        if current_qty == 0 and open_positions >= self.max_open_positions:
            raise RiskError(f"Open position cap reached ({self.max_open_positions})")

        if current_qty != 0:
            same_side = (current_qty > 0 and signed_qty > 0) or (current_qty < 0 and signed_qty < 0)
            flipping = current_qty != 0 and (current_qty + signed_qty) != 0 and ((current_qty > 0 > current_qty + signed_qty) or (current_qty < 0 < current_qty + signed_qty))

            if same_side and not self.allow_pyramiding:
                raise RiskError(f"Pyramiding disabled for existing {symbol} position")
            if flipping and not self.allow_direction_flip:
                raise RiskError(f"Direction flip disabled for existing {symbol} position")

        projected_qty = current_qty + signed_qty
        projected_notional = abs(projected_qty) * market_price
        if projected_notional > self.max_position_notional:
            raise RiskError(
                f"Projected position notional {projected_notional:.2f} exceeds cap {self.max_position_notional:.2f}"
            )

        if side in ("BUY", "LONG"):
            remaining_cash = account.available_cash - order_notional
            if remaining_cash < self.min_cash_buffer:
                raise RiskError(
                    f"Insufficient cash after buffer. Remaining {remaining_cash:.2f}, buffer {self.min_cash_buffer:.2f}"
                )

