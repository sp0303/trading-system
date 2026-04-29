import uuid
import time
from sqlalchemy.orm import Session
from ..models.schema import PaperOrder, PaperOrderAudit, PaperFill, PaperPosition
from .price_resolver import PriceResolver
from .fill_simulator import FillSimulator
from .position_service import PositionService
from .risk_service import RiskError, RiskService
import logging

class OMS:
    def __init__(self, db: Session):
        self.db = db
        self.price_resolver = PriceResolver(db)
        self.fill_simulator = FillSimulator()
        self.position_service = PositionService(db)
        self.risk_service = RiskService(db)

    def create_order(self, order_data: dict) -> PaperOrder:
        """
        Main entry point for placing a paper order.
        Sequence: NEW -> ACK -> (Execution) -> FILLED
        """
        # 1. Initialize Order in NEW status
        client_order_id = f"PAPER-{int(time.time())}-{order_data['symbol']}-{order_data['side']}-{str(uuid.uuid4())[:4]}"
        
        order = PaperOrder(
            client_order_id=client_order_id,
            symbol=order_data["symbol"],
            side=order_data["side"],
            qty=order_data["qty"],
            requested_price=order_data.get("requested_price"),
            order_type=order_data.get("order_type", "MARKET"),
            strategy_name=order_data.get("strategy_name"),
            regime=order_data.get("regime"),
            trade_signal_id=order_data.get("trade_signal_id"),
            source=order_data.get("source", "frontend"),
            extra=order_data.get("extra", {}),
            status="NEW"
        )
        self.db.add(order)
        self.db.commit()
        self._audit(client_order_id, None, "NEW")

        # 2. ACK the order
        order.status = "ACK"
        self.db.commit()
        self._audit(client_order_id, "NEW", "ACK")

        # 3. Simulate Execution (Market Order logic)
        try:
            market_price = self.price_resolver.get_latest_price(order.symbol)
            if market_price == 0:
                self._reject_order(order, "Price resolution failed - no data found")
                return order

            self.risk_service.validate_new_order(order.symbol, order.side, order.qty, market_price)

            fill_info = self.fill_simulator.simulate_fill(
                order.symbol, order.side, order.qty, market_price
            )

            # 4. Record Fill
            fill = PaperFill(
                client_order_id=client_order_id,
                symbol=fill_info["symbol"],
                side=fill_info["side"],
                qty=fill_info["qty"],
                price=fill_info["price"],
                slippage_bps=fill_info["slippage_bps"],
                venue=fill_info["venue"]
            )
            self.db.add(fill)

            # 5. Update Order to FILLED
            order.status = "FILLED"
            order.filled_qty = fill_info["qty"]
            order.avg_fill_price = fill_info["price"]
            self.db.commit()
            self._audit(client_order_id, "ACK", "FILLED")

            # 6. Update Position
            self.position_service.update_position(fill_info)

        except RiskError as e:
            logging.warning(f"Risk rejected order {client_order_id}: {e}")
            self._reject_order(order, str(e))
        except Exception as e:
            logging.error(f"Execution failed for {client_order_id}: {e}")
            self._reject_order(order, str(e))

        return order

    def execute_institutional_order(self, order_data: dict) -> PaperOrder:
        """
        Executes an order that was approved and sized by the institutional risk manager.
        """
        client_order_id = order_data["client_order_id"]
        
        # 1. Record the approved order in our DB if it doesn't exist
        order = self.db.query(PaperOrder).filter(PaperOrder.client_order_id == client_order_id).first()
        if not order:
            order = PaperOrder(
                client_order_id=client_order_id,
                symbol=order_data["symbol"],
                side=order_data["side"],
                qty=order_data["qty"],
                order_type=order_data.get("order_type", "MARKET"),
                strategy_name=order_data.get("strategy", "INSTITUTIONAL"),
                source="kafka_institutional",
                extra=order_data.get("extra", {}),
                status="APPROVED"
            )
            self.db.add(order)
            self.db.commit()
            self._audit(client_order_id, None, "APPROVED")
        
        # 2. Simulate Execution
        try:
            # Use reference price from risk manager if available, else resolve
            market_price = (order_data.get("extra", {}).get("risk", {}).get("ref_price") or 
                            self.price_resolver.get_latest_price(order.symbol))
            
            if market_price == 0:
                self._reject_order(order, "Price resolution failed")
                return order

            fill_info = self.fill_simulator.simulate_fill(
                order.symbol, order.side, order.qty, market_price
            )

            # 3. Record Fill
            fill = PaperFill(
                client_order_id=client_order_id,
                symbol=fill_info["symbol"],
                side=fill_info["side"],
                qty=fill_info["qty"],
                price=fill_info["price"],
                slippage_bps=fill_info["slippage_bps"],
                venue=fill_info["venue"]
            )
            self.db.add(fill)

            # 4. Update Order to FILLED
            order.status = "FILLED"
            order.filled_qty = fill_info["qty"]
            order.avg_fill_price = fill_info["price"]
            self.db.commit()
            self._audit(client_order_id, "APPROVED", "FILLED")

            # 5. Update Position
            self.position_service.update_position(fill_info)

        except Exception as e:
            logging.error(f"Kafka Execution failed for {client_order_id}: {e}")
            self._reject_order(order, str(e))

        return order

    def close_symbol_position(self, symbol: str, source: str = "frontend_close") -> PaperOrder:
        position = self.db.query(PaperPosition).filter(PaperPosition.symbol == symbol).first()
        if not position or position.net_qty == 0:
            raise ValueError(f"No open position for {symbol}")

        side = "SELL" if position.net_qty > 0 else "BUY"
        return self.create_order({
            "symbol": symbol,
            "side": side,
            "qty": abs(position.net_qty),
            "order_type": "MARKET",
            "strategy_name": "MANUAL_CLOSE",
            "source": source,
            "extra": {"close_reason": "manual_close"},
        })

    def _audit(self, client_order_id: str, from_status: str, to_status: str, note: str = None):
        audit = PaperOrderAudit(
            client_order_id=client_order_id,
            from_status=from_status,
            to_status=to_status,
            note=note
        )
        self.db.add(audit)
        self.db.commit()

    def _reject_order(self, order: PaperOrder, reason: str):
        old_status = order.status
        order.status = "REJECTED"
        order.note = reason
        self.db.commit()
        self._audit(order.client_order_id, old_status, "REJECTED", note=reason)
