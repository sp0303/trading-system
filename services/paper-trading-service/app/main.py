from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from typing import List
import datetime
from .models.database import get_db
from .models.schema import PaperOrder, PaperFill, PaperPosition, PaperAccount, PaperDailyPnL
from .schemas.paper import PaperOrderCreate, PaperOrderResponse, PaperPositionResponse, PaperFillResponse
from .services.oms import OMS
from .services.price_resolver import PriceResolver
from .services.position_monitor import PositionMonitor
from .services.kafka_consumer import InstitutionalOrderConsumer
import logging

monitor = PositionMonitor()
kafka_consumer = InstitutionalOrderConsumer()

def _seed_paper_account(db: Session):
    """Auto-seed the paper trading account if it doesn't exist."""
    account = db.query(PaperAccount).filter(PaperAccount.id == 1).first()
    if not account:
        logging.info("Seeding paper account with ₹10 Lakhs starting capital...")
        account = PaperAccount(
            id=1,
            total_capital=1_000_000.0,
            available_cash=1_000_000.0
        )
        db.add(account)
        db.commit()
        logging.info("✅ Paper account seeded successfully.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB tables
    from .models.database import Base, engine, SessionLocal
    Base.metadata.create_all(bind=engine)

    # Auto-seed paper account (critical: must exist before any order)
    db = SessionLocal()
    try:
        _seed_paper_account(db)
    finally:
        db.close()

    # Start automated SL/TP monitoring thread
    monitor.start()
    
    # Start Kafka Institutional Consumer
    await kafka_consumer.start()
    
    yield
    # Graceful stop on shutdown
    monitor.stop()
    await kafka_consumer.stop()

app = FastAPI(title="Nifty 500 Paper Trading Service", lifespan=lifespan)


def ok(data):
    return {"status": "success", "data": data}

@app.get("/account")
def get_account_summary(db: Session = Depends(get_db)):
    account = db.query(PaperAccount).filter(PaperAccount.id == 1).first()
    if not account:
        return ok({
            "starting_capital": 10000000.0,
            "available_cash": 10000000.0,
            "invested_capital": 0.0,
            "unrealized_pnl": 0.0,
            "realized_pnl": 0.0,
            "total_equity": 1000000.0
        })
    
    positions = db.query(PaperPosition).all()
    price_resolver = PriceResolver(db)
    
    total_holdings_value = 0
    total_unrealized_pnl = 0
    invested_capital = 0
    
    for pos in positions:
        curr_price = price_resolver.get_latest_price(pos.symbol)
        total_holdings_value += (pos.net_qty * curr_price)
        invested_capital += (abs(pos.net_qty) * pos.avg_price)
        
        if pos.net_qty > 0:
            total_unrealized_pnl += (curr_price - pos.avg_price) * pos.net_qty
        elif pos.net_qty < 0:
            total_unrealized_pnl += (pos.avg_price - curr_price) * abs(pos.net_qty)
            
    return ok({
        "starting_capital": account.total_capital,
        "available_cash": account.available_cash,
        "invested_capital": invested_capital,
        "market_value": total_holdings_value,
        "unrealized_pnl": total_unrealized_pnl,
        "realized_pnl": sum(p.realized_pnl for p in positions),
        "total_equity": account.available_cash + total_holdings_value,
        "updated_at": account.updated_at
    })

@app.post("/orders")
def create_order(order: PaperOrderCreate, db: Session = Depends(get_db)):
    oms = OMS(db)
    return ok(PaperOrderResponse.model_validate(oms.create_order(order.dict())).model_dump(mode="json"))

@app.post("/positions/{symbol}/close")
def close_position(symbol: str, db: Session = Depends(get_db)):
    oms = OMS(db)
    try:
        order = oms.close_symbol_position(symbol)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return ok(PaperOrderResponse.model_validate(order).model_dump(mode="json"))

@app.get("/orders")
def get_orders(symbol: str = None, limit: int = 50, db: Session = Depends(get_db)):
    query = db.query(PaperOrder)
    if symbol:
        query = query.filter(PaperOrder.symbol == symbol)
    rows = query.order_by(PaperOrder.created_at.desc()).limit(limit).all()
    return ok([PaperOrderResponse.model_validate(row).model_dump(mode="json") for row in rows])

@app.get("/fills")
def get_fills(symbol: str = None, limit: int = 50, db: Session = Depends(get_db)):
    query = db.query(PaperFill)
    if symbol:
        query = query.filter(PaperFill.symbol == symbol)
    rows = query.order_by(PaperFill.timestamp.desc()).limit(limit).all()
    return ok([PaperFillResponse.model_validate(row).model_dump(mode="json") for row in rows])

@app.get("/positions")
def get_positions(db: Session = Depends(get_db)):
    """Return all positions with live unrealized PnL calculated from latest prices."""
    positions = db.query(PaperPosition).all()
    price_resolver = PriceResolver(db)

    for pos in positions:
        curr_price = price_resolver.get_latest_price(pos.symbol)
        if curr_price > 0:
            pos.last_price = curr_price
            if pos.net_qty > 0:
                pos.unrealized_pnl = (curr_price - pos.avg_price) * pos.net_qty
            elif pos.net_qty < 0:
                pos.unrealized_pnl = (pos.avg_price - curr_price) * abs(pos.net_qty)

    # BUG FIX: was missing return statement — positions were calculated but never sent
    return ok([PaperPositionResponse.model_validate(pos).model_dump(mode="json") for pos in positions])

@app.get("/daily-pnl")
def get_daily_pnl(db: Session = Depends(get_db)):
    """Return today's trading P&L summary — realized + unrealized + trade count."""
    today = datetime.date.today()

    # Realized PnL: sum of fills closed today (position update records realized_pnl)
    positions = db.query(PaperPosition).all()
    price_resolver = PriceResolver(db)

    total_unrealized = 0.0
    total_realized = sum(p.realized_pnl for p in positions)
    open_positions = 0

    position_breakdown = []
    for pos in positions:
        if pos.net_qty != 0:
            open_positions += 1
            curr_price = price_resolver.get_latest_price(pos.symbol)
            if curr_price > 0:
                if pos.net_qty > 0:
                    unreal = (curr_price - pos.avg_price) * pos.net_qty
                else:
                    unreal = (pos.avg_price - curr_price) * abs(pos.net_qty)
                total_unrealized += unreal
                position_breakdown.append({
                    "symbol": pos.symbol,
                    "net_qty": pos.net_qty,
                    "avg_price": pos.avg_price,
                    "last_price": curr_price,
                    "unrealized_pnl": round(unreal, 2),
                    "realized_pnl": round(pos.realized_pnl, 2),
                })

    # Trades today
    start_of_day = datetime.datetime.combine(today, datetime.time.min)
    trades_today = db.query(PaperOrder).filter(
        PaperOrder.status == "FILLED",
        PaperOrder.created_at >= start_of_day
    ).count()

    return ok({
        "date": str(today),
        "realized_pnl": round(total_realized, 2),
        "unrealized_pnl": round(total_unrealized, 2),
        "total_pnl": round(total_realized + total_unrealized, 2),
        "trades_today": trades_today,
        "open_positions": open_positions,
        "positions": position_breakdown,
    })

@app.post("/orders/{symbol}/close")
def close_symbol_position(symbol: str, db: Session = Depends(get_db)):
    oms = OMS(db)
    try:
        order = oms.close_symbol_position(symbol)
        return ok({
            "client_order_id": order.client_order_id,
            "status": order.status,
            "symbol": order.symbol,
            "avg_fill_price": order.avg_fill_price
        })
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "paper-trading-service"}

@app.get("/reports/daily")
def get_daily_report(date: str = None, db: Session = Depends(get_db)):
    """
    Generates a professional daily trading report with analytics.
    """
    from datetime import datetime, date as date_obj
    import pytz
    
    ist = pytz.timezone('Asia/Kolkata')
    # Simplified query: Convert the timestamp to the target date string for matching
    orders = db.query(PaperOrder).filter(
        func.to_char(PaperOrder.created_at, 'YYYY-MM-DD') == (date or datetime.now(ist).strftime('%Y-%m-%d')),
        PaperOrder.status == 'FILLED'
    ).all()
    
    # Analytics Calculations
    total_trades = len(orders)
    
    def get_pnl(o):
        return o.extra.get("realized_pnl", 0.0) if o.extra else 0.0

    wins = [o for o in orders if get_pnl(o) > 0]
    
    winning_trades = len(wins)
    losing_trades = len([o for o in orders if get_pnl(o) < 0])
    
    gross_profit = sum(get_pnl(o) for o in orders if get_pnl(o) > 0)
    gross_loss = sum(get_pnl(o) for o in orders if get_pnl(o) < 0)
    
    # Strategy Performance
    strategy_stats = {}
    for o in orders:
        s_name = o.strategy_name or "Unknown"
        pnl = get_pnl(o)
        if s_name not in strategy_stats:
            strategy_stats[s_name] = {"count": 0, "pnl": 0.0, "wins": 0}
        strategy_stats[s_name]["count"] += 1
        strategy_stats[s_name]["pnl"] += pnl
        if pnl > 0:
            strategy_stats[s_name]["wins"] += 1

    return ok({
        "summary": {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": round((winning_trades / total_trades * 100), 2) if total_trades > 0 else 0,
            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(gross_loss, 2),
            "net_pnl": round(gross_profit + gross_loss, 2),
            "avg_profit_per_trade": round((gross_profit + gross_loss) / total_trades, 2) if total_trades > 0 else 0,
        },
        "trades": [
            {
                "id": o.id,
                "symbol": o.symbol,
                "side": o.side,
                "qty": o.qty,
                "entry_price": o.avg_fill_price or o.requested_price,
                "exit_price": o.extra.get("exit_price") if o.extra else None,
                "pnl": get_pnl(o),
                "strategy": o.strategy_name,
                "time": o.created_at.strftime("%H:%M:%S"),
                "status": "Win" if get_pnl(o) > 0 else "Loss" if get_pnl(o) < 0 else "Open/Breakeven"
            } for o in orders
        ],
        "strategy_performance": [
            {
                "name": name,
                "trades": stats["count"],
                "pnl": round(stats["pnl"], 2),
                "win_rate": round((stats["wins"] / stats["count"] * 100), 2)
            } for name, stats in strategy_stats.items()
        ]
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=7012, log_level="info")
