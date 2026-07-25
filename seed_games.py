import logging
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.game import Game

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GAMES = [
    {"slug": "spin-wheel", "name": "Spin Wheel", "genre": "arcade"},
    {"slug": "coin-toss", "name": "Coin Toss", "genre": "casino"},
    {"slug": "dice", "name": "Dice", "genre": "casino"},
    {"slug": "scratch-card", "name": "Scratch Card", "genre": "casino"},
    {"slug": "lucky-number", "name": "Lucky Number", "genre": "casino"},
    {"slug": "mines", "name": "Mines", "genre": "casino"},
    {"slug": "crash", "name": "Crash", "genre": "casino"},
    {"slug": "plinko", "name": "Plinko", "genre": "casino"},
    {"slug": "hilo", "name": "HiLo", "genre": "casino"},
    {"slug": "color-prediction", "name": "Color Prediction", "genre": "arcade"},
    {"slug": "lucky-seven", "name": "Lucky Seven", "genre": "arcade"},
    {"slug": "treasure-box", "name": "Treasure Box", "genre": "arcade"},
    {"slug": "balloon-pop", "name": "Balloon Pop", "genre": "arcade"},
    {"slug": "car-racing", "name": "Neon Racing", "genre": "arcade"},
    {"slug": "tic-tac-toe", "name": "Tic Tac Toe", "genre": "strategy"},
    {"slug": "snake", "name": "Snake 3000", "genre": "arcade"},
    {"slug": "flappy-bird", "name": "Flappy Crash", "genre": "arcade"},
    {"slug": "sudoku", "name": "Mini Sudoku", "genre": "puzzle"},
    {"slug": "word-search", "name": "Word Search", "genre": "puzzle"}
]

def seed_db():
    logger.info("Seeding games table...")
    db: Session = SessionLocal()
    try:
        for g_data in GAMES:
            existing = db.query(Game).filter(Game.slug == g_data["slug"]).first()
            if not existing:
                game = Game(
                    slug=g_data["slug"],
                    name=g_data["name"],
                    genre=g_data["genre"],
                    description=f"Play {g_data['name']} to win big!",
                    is_active=True,
                    higher_score_is_better=True
                )
                db.add(game)
        db.commit()
        logger.info("Games seeded successfully.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error seeding games: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_db()
