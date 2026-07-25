import logging
from sqlalchemy import create_engine
from app.core.config import settings
from app.core.database import Base
# Import all models here so that Base metadata detects them
from app.models.user import User
from app.models.wallet import WalletTransaction
from app.models.tournament import Tournament, TournamentEntry
from app.models.game import Game

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db():
    logger.info("Creating all tables in the database...")
    engine = create_engine(settings.DATABASE_URL)
    Base.metadata.create_all(bind=engine)
    logger.info("Tables created successfully.")

if __name__ == "__main__":
    init_db()
