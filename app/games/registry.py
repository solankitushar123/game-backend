"""
Per-game score plausibility validators.
Each game defines its own theoretical max score and minimum-time-per-point,
so the server can reject obviously impossible submissions.
"""
from typing import Tuple


class BaseGameValidator:
    slug: str
    max_possible_score: int
    min_seconds_for_max_score: float

    def validate(self, claimed_score: int, elapsed_seconds: float, seed: int) -> Tuple[bool, str | None]:
        if claimed_score < 0:
            return False, "score cannot be negative"
        if claimed_score > self.max_possible_score:
            return False, f"score exceeds theoretical maximum ({self.max_possible_score})"

        if self.max_possible_score > 0:
            fraction_of_max = claimed_score / self.max_possible_score
            min_time_required = fraction_of_max * self.min_seconds_for_max_score
            if elapsed_seconds < min_time_required * 0.5:  # 50% leeway for network/render variance
                return False, "score not physically achievable in elapsed time"
        return True, None


class GlyphCascadeValidator(BaseGameValidator):
    """Puzzle game: tile-matching cascade. Max realistic score per round ~50,000."""
    slug = "glyph-cascade"
    max_possible_score = 50000
    min_seconds_for_max_score = 45.0


class ReflexRunValidator(BaseGameValidator):
    """Arcade reflex/reaction game. Score = obstacles cleared * 10, capped by round length."""
    slug = "reflex-run"
    max_possible_score = 20000
    min_seconds_for_max_score = 30.0


class QuizForgeValidator(BaseGameValidator):
    """Trivia sprint: fixed question set, max score = perfect answers + speed bonus."""
    slug = "quizforge"
    max_possible_score = 10000
    min_seconds_for_max_score = 20.0


class WordLadderValidator(BaseGameValidator):
    """Word-chain strategy game. Score based on chain length and word rarity."""
    slug = "word-ladder"
    max_possible_score = 30000
    min_seconds_for_max_score = 40.0


registry = {
    "glyph-cascade": GlyphCascadeValidator(),
    "reflex-run": ReflexRunValidator(),
    "quizforge": QuizForgeValidator(),
    "word-ladder": WordLadderValidator(),
}
