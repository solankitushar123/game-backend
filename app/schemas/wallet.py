from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class DepositRequest(BaseModel):
    amount_paise: int = Field(..., gt=0)
    # In production: payment_method, gateway_payload etc. Simulated here.

class WithdrawRequest(BaseModel):
    amount_paise: int = Field(..., gt=0)


class WalletResponse(BaseModel):
    balance_paise: int
    balance_rupees: float

    @classmethod
    def from_wallet(cls, wallet):
        return cls(
            balance_paise=wallet.balance_paise,
            balance_rupees=round(wallet.balance_paise / 100, 2),
        )


class TransactionResponse(BaseModel):
    id: UUID
    tx_type: str
    amount_paise: int
    balance_after_paise: int
    funding_source: Optional[str]
    description: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
