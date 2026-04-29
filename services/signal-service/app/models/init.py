from app.models.database import engine, Base
from app.models.schema import StrategySignal, TradeSignal

def init_signal_db():
    print("Creating tables in PostgreSQL...")
    Base.metadata.create_all(bind=engine)
    print("Tables 'strategy_signals' and 'trade_signals' created.")

if __name__ == "__main__":
    init_signal_db()
