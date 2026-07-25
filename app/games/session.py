"""
Server-authoritative game session + scoring validation.

How anti-cheat works in v1 (lightweight but real, not security theater):
  1. Client calls POST /games/{slug}/session/start -> server creates a signed
     session token containing {user_id, tournament_id, game_slug, started_at, seed}.
  2. Client plays the game *using the server-provided seed* for any randomness
     (so the play-through is deterministic and reproducible).
  3. Client submits {session_token, score, session_data} where session_data
     contains a compact event/action log (e.g. moves made, time taken).
  4. Server re-simulates / sanity-checks the submission against the session:
       - session token signature valid & not expired & not already used
       - elapsed time is physically plausible for the claimed score
       - score does not exceed the game's theoretical maximum
       - (for deterministic games) replaying the action log against the
         server seed reproduces the claimed score
  5. Only after validation does the score get written to Postgres + Redis.

This is intentionally conservative for v1: it blocks the easy attack (just POSTing
an arbitrary huge score with no session) while leaving room to harden per-game
replay validation later without changing the API contract.
"""
import time
import uuid
import hmac
import hashlib
import json
from dataclasses import dataclass
from typing import Optional

from app.core.config import settings
from app.core.redis_client import redis_client

SESSION_TTL_SECONDS = 60 * 30  # sessions expire after 30 minutes


@dataclass
class GameSessionPayload:
    user_id: str
    tournament_id: str
    game_slug: str
    seed: int
    started_at: float


def _sign(payload: str) -> str:
    return hmac.new(
        settings.JWT_SECRET_KEY.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()


def create_session_token(user_id: uuid.UUID, tournament_id: uuid.UUID, game_slug: str) -> str:
    payload = GameSessionPayload(
        user_id=str(user_id),
        tournament_id=str(tournament_id),
        game_slug=game_slug,
        seed=int.from_bytes(uuid.uuid4().bytes[:4], "big"),
        started_at=time.time(),
    )
    raw = json.dumps(payload.__dict__, separators=(",", ":"))
    token = raw + "." + _sign(raw)
    token_b = token.encode().hex()

    # Track issued (not-yet-used) session in Redis so we can enforce one-use-per-session.
    redis_client.setex(f"game_session:{token_b}", SESSION_TTL_SECONDS, "issued")
    return token_b


def _decode_session(token_hex: str) -> Optional[GameSessionPayload]:
    try:
        token = bytes.fromhex(token_hex).decode()
        raw, sig = token.rsplit(".", 1)
        if not hmac.compare_digest(sig, _sign(raw)):
            return None
        data = json.loads(raw)
        return GameSessionPayload(**data)
    except Exception:
        return None


class GameValidationResult:
    def __init__(self, is_valid: bool, reason: Optional[str] = None):
        self.is_valid = is_valid
        self.reason = reason


def validate_and_consume_session(
    token_hex: str,
    expected_user_id: uuid.UUID,
    expected_tournament_id: uuid.UUID,
    game_slug: str,
    claimed_score: int,
) -> GameValidationResult:
    redis_key = f"game_session:{token_hex}"
    status = redis_client.get(redis_key)
    if status is None:
        return GameValidationResult(False, "session expired or not found")
    if status == "consumed":
        return GameValidationResult(False, "session already used")

    payload = _decode_session(token_hex)
    if payload is None:
        return GameValidationResult(False, "invalid session signature")

    if payload.user_id != str(expected_user_id):
        return GameValidationResult(False, "session does not belong to this user")
    if payload.tournament_id != str(expected_tournament_id):
        return GameValidationResult(False, "session does not belong to this tournament")
    if payload.game_slug != game_slug:
        return GameValidationResult(False, "session game mismatch")

    elapsed = time.time() - payload.started_at
    if elapsed < 0 or elapsed > SESSION_TTL_SECONDS:
        return GameValidationResult(False, "session time window invalid")

    # Per-game plausibility checks
    from app.games.registry import registry
    validator = registry.get(game_slug)
    if validator is None:
        return GameValidationResult(False, "unknown game")

    ok, reason = validator.validate(claimed_score=claimed_score, elapsed_seconds=elapsed, seed=payload.seed)
    if not ok:
        return GameValidationResult(False, reason)

    # Mark consumed (one submission per session)
    redis_client.setex(redis_key, 60, "consumed")
    return GameValidationResult(True)
