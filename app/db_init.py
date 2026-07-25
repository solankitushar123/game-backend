"""
One-time DB setup: create all tables and seed initial data
(game catalog + a default admin account for local development).

Run with: python -m app.db_init
"""
from datetime import date

from app.core.database import Base, engine, SessionLocal
from app.models.user import User
from app.models.wallet import Wallet
from app.models.game import Game
from app.core.security import hash_password

GAMES_SEED = [
    {
        "slug": "spin-wheel",
        "name": "Cosmic Spin Wheel",
        "genre": "arcade",
        "description": "Spin the cosmic wheel to win up to 10x your bet.",
        "higher_score_is_better": True,
    },
    {
        "slug": "dice",
        "name": "Neo Dice",
        "genre": "arcade",
        "description": "Roll the crypto dice. Pick your win chance and multiplier.",
        "higher_score_is_better": True,
    },
    {
        "slug": "coin-toss",
        "name": "Cyber Coin Toss",
        "genre": "arcade",
        "description": "Heads or Tails? 50/50 chance to double your money.",
        "higher_score_is_better": True,
    },
    {
        "slug": "scratch-card",
        "name": "Holo Scratch",
        "genre": "puzzle",
        "description": "Scratch the holographic card to reveal matching symbols and win big.",
        "higher_score_is_better": True,
    },
    {
        "slug": "lucky-number",
        "name": "Lucky Number",
        "genre": "strategy",
        "description": "Pick a number between 1 and 10. Win huge if it matches the server draw.",
        "higher_score_is_better": True,
    },
    {
        "slug": "crash",
        "name": "Crash",
        "genre": "crypto",
        "description": "Guess the multiplier before the rocket crashes! High risk, high reward.",
        "higher_score_is_better": True,
    },
    {
        "slug": "mines",
        "name": "Mines",
        "genre": "crypto",
        "description": "Navigate the minefield. The more safe spots you pick, the higher your multiplier.",
        "higher_score_is_better": True,
    },
    {
        "slug": "plinko",
        "name": "Plinko",
        "genre": "crypto",
        "description": "Drop the ball and watch it bounce through the pegs. Outer bins pay massive multipliers.",
        "higher_score_is_better": True,
    },
    {
        "slug": "hilo",
        "name": "HiLo",
        "genre": "cards",
        "description": "Guess if the next card drawn will be higher or lower than the current card.",
        "higher_score_is_better": True,
    },
    {
        "slug": "color-prediction",
        "name": "Color Prediction",
        "genre": "strategy",
        "description": "Predict the winning color (Red, Green, Violet) to multiply your stake.",
        "higher_score_is_better": True,
    },
    {
        "slug": "lucky-seven",
        "name": "Lucky Seven",
        "genre": "arcade",
        "description": "Will the sum of the dice be under 7, over 7, or exactly 7?",
        "higher_score_is_better": True,
    },
    {
        "slug": "treasure-box",
        "name": "Treasure Box",
        "genre": "puzzle",
        "description": "Pick the right box to uncover the hidden crypto treasure.",
        "higher_score_is_better": True,
    },
    {
        "slug": "balloon-pop",
        "name": "Balloon Pop",
        "genre": "arcade",
        "description": "Cash out before the balloon pops!",
        "higher_score_is_better": True,
    },
    {
        "slug": "snake",
        "name": "Snake Pro",
        "genre": "skill",
        "description": "The classic snake game. Survive and eat to build your multiplier.",
        "higher_score_is_better": True,
    },
    {
        "slug": "tic-tac-toe",
        "name": "Tic Tac Toe",
        "genre": "skill",
        "description": "Beat the AI in Tic Tac Toe.",
        "higher_score_is_better": True,
    },
    {
        "slug": "sudoku",
        "name": "Sudoku Challenge",
        "genre": "skill",
        "description": "Solve the puzzle to win.",
        "higher_score_is_better": True,
    },
    {
        "slug": "word-search",
        "name": "Word Search",
        "genre": "skill",
        "description": "Find the hidden words fast enough to earn a payout.",
        "higher_score_is_better": True,
    },
    {
        "slug": "car-racing",
        "name": "Turbo Racing",
        "genre": "skill",
        "description": "Outrun the competition in this fast-paced racing game.",
        "higher_score_is_better": True,
    },
    {
        "slug": "flappy-bird",
        "name": "Flappy Crypto",
        "genre": "skill",
        "description": "Navigate the pipes. High score gets the prize pool.",
        "higher_score_is_better": True,
    },
]


def init_db():
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)
    print("Tables created.")

    db = SessionLocal()
    try:
        # Seed games
        valid_slugs = []
        for g in GAMES_SEED:
            valid_slugs.append(g["slug"])
            existing = db.query(Game).filter(Game.slug == g["slug"]).first()
            if not existing:
                db.add(Game(**g))
                print(f"Seeded game: {g['name']}")
            else:
                existing.is_active = True
                
        # Deactivate old games
        old_games = db.query(Game).filter(Game.slug.notin_(valid_slugs)).all()
        for og in old_games:
            og.is_active = False
            print(f"Deactivated old game: {og.name}")

        # Seed admin user (local dev only — change password before any real deployment)
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            admin = User(
                username="admin",
                email="admin@arenaforge.local",
                password_hash=hash_password("ChangeMe123!"),
                date_of_birth=date(1995, 1, 1),
                is_age_verified=True,
                is_kyc_verified=True,
                kyc_status="verified",
                is_admin=True,
            )
            db.add(admin)
            db.flush()
            db.add(Wallet(user_id=admin.id, balance_paise=0))
            print("Seeded admin user: admin / ChangeMe123!  (CHANGE THIS PASSWORD)")

        db.commit()
        print("Seeding complete.")
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
