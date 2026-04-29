from sqlalchemy.orm import Session
from ..models.schema import PaperAccount, PaperPosition
import logging

class PositionService:
    def __init__(self, db: Session):
        self.db = db

    def update_position(self, fill_data: dict):
        """
        Updates symbol position, realized PnL, AND account cash balance.
        """
        symbol = fill_data["symbol"]
        side = fill_data["side"].upper()
        qty = fill_data["qty"]
        price = fill_data["price"]
        
        # Calculate cash impact (Buy = negative cash, Sell = positive cash)
        total_cost = price * qty
        cash_impact = -total_cost if side in ("BUY", "LONG") else total_cost

        # 1. Update Account Cash Balance
        account = self.db.query(PaperAccount).filter(PaperAccount.id == 1).first()
        if account:
            brokerage = self._calculate_brokerage(total_cost)
            account.available_cash += (cash_impact - brokerage)
            logging.info(f"Updated account cash: {cash_impact} (Trade) - {brokerage} (Brokerage)")

        # 2. Update Position
        pos = self.db.query(PaperPosition).filter(PaperPosition.symbol == symbol).first()

        if not pos:
            # Create new position
            net_qty = qty if side in ("BUY", "LONG") else -qty
            pos = PaperPosition(
                symbol=symbol,
                net_qty=net_qty,
                avg_price=price,
                realized_pnl=0.0,
                unrealized_pnl=0.0
            )
            self.db.add(pos)
        else:
            prev_qty = pos.net_qty
            prev_avg = pos.avg_price

            # If increasing same side
            if (prev_qty >= 0 and side in ("BUY", "LONG")) or (prev_qty <= 0 and side in ("SELL", "SHORT")):
                new_total_qty = prev_qty + (qty if side in ("BUY", "LONG") else -qty)
                if new_total_qty != 0:
                    pos.avg_price = (abs(prev_qty) * prev_avg + qty * price) / abs(new_total_qty)
                pos.net_qty = new_total_qty
            else:
                # Reducing position or flipping
                closed_qty = min(abs(prev_qty), qty)
                
                if prev_qty > 0: # Closing long
                    pnl = (price - prev_avg) * closed_qty
                else: # Closing short
                    pnl = (prev_avg - price) * closed_qty
                
                pos.realized_pnl += pnl
                pos.net_qty += (qty if side in ("BUY", "LONG") else -qty)
                
                if (prev_qty > 0 and pos.net_qty < 0) or (prev_qty < 0 and pos.net_qty > 0):
                    pos.avg_price = price

        self.db.commit()
        
        # 3. Save PnL back to the Order if it was a closing trade
        if 'pnl' in locals():
            order = self.db.query(PaperOrder).filter(PaperOrder.id == fill_data.get("order_id")).first()
            if order:
                order.extra = {**(order.extra or {}), "realized_pnl": round(pnl, 2)}
                self.db.commit()
                logging.info(f"Recorded PnL {pnl} to Order {order.id}")

        return pos

    def _calculate_brokerage(self, turnover: float) -> float:
        """
        Calculates brokerage for the trade (0.05% all-in).
        """
        rate = 0.0005 
        return round(turnover * rate, 2)
