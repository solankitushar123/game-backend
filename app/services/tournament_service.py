"""
TournamentService — settlement logic: once a tournament ends, final ranks are
locked from the Redis leaderboard, written to Postgres (source of truth), and
prizes are credited via WalletService with the tournament's declared funding_source.

Settlement is idempotent: re-running it on an already-settled tournament is a no-op,
which protects against double-payout if a cron job or admin action fires twice.
"""
import uuid
from datetime import datetime
from app.core.time_utils import now_utc

from sqlalchemy.orm import Session

from app.models.tournament import Tournament, TournamentEntry
from app.services.leaderboard_service import LeaderboardService
from app.services.wallet_service import WalletService, DuplicateTransactionError
from app.services.audit_service import AuditService


class TournamentService:

    @staticmethod
    def compute_prize_for_rank(payout_structure: list, rank: int) -> int:
        for tier in payout_structure:
            if tier["rank_from"] <= rank <= tier["rank_to"]:
                return int(tier["amount_paise"])
        return 0

    @staticmethod
    def settle_tournament(db: Session, tournament_id: uuid.UUID) -> dict:
        tournament = db.query(Tournament).filter(Tournament.id == tournament_id).with_for_update().first()
        if tournament is None:
            raise ValueError("Tournament not found")

        if tournament.status == "settled":
            return {"already_settled": True, "tournament_id": str(tournament_id)}

        if tournament.ends_at > now_utc():
            raise ValueError("Tournament has not ended yet")

        ranked = LeaderboardService.get_all_ranked(tournament_id)  # [(user_id_str, score), ...] desc

        settled_count = 0
        total_paid_paise = 0

        for idx, (user_id_str, score) in enumerate(ranked):
            rank = idx + 1
            entry = db.query(TournamentEntry).filter(
                TournamentEntry.tournament_id == tournament_id,
                TournamentEntry.user_id == uuid.UUID(user_id_str),
            ).first()
            if entry is None:
                continue

            entry.final_rank = rank
            entry.best_score = int(score)

            if rank <= tournament.max_paid_ranks:
                prize_paise = TournamentService.compute_prize_for_rank(tournament.payout_structure, rank)
                if prize_paise > 0:
                    idempotency_key = f"prize:{tournament_id}:{entry.user_id}"
                    try:
                        WalletService.credit_prize(
                            db, entry.user_id, prize_paise, tournament_id,
                            funding_source=tournament.funding_source,
                            idempotency_key=idempotency_key,
                        )
                        entry.prize_awarded_paise = prize_paise
                        entry.prize_settled = True
                        total_paid_paise += prize_paise
                        settled_count += 1
                    except DuplicateTransactionError:
                        pass  # already paid — idempotent re-run

        tournament.status = "settled"
        AuditService.log(
            db, action="tournament.settled", actor_type="system",
            target_type="tournament", target_id=tournament_id,
            metadata={"players_paid": settled_count, "total_paid_paise": total_paid_paise},
        )
        db.commit()
        return {
            "already_settled": False,
            "tournament_id": str(tournament_id),
            "players_paid": settled_count,
            "total_paid_paise": total_paid_paise,
        }
