from datetime import date, datetime
import logging
from app.core.time_utils import now_utc

from fastapi import APIRouter, Depends, HTTPException, status, Request
from jose import JWTError
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from app.core.config import settings
from app.core.redis_client import redis_client
from app.models.user import User
from app.models.wallet import Wallet
from app.schemas.auth import SignupRequest, LoginRequest, TokenResponse, RefreshRequest, UserResponse
from app.services.audit_service import AuditService
from app.api.deps import get_current_user, get_client_ip

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger(__name__)


def _calculate_age(dob: date) -> int:
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def signup(body: SignupRequest, request: Request, db: Session = Depends(get_db)):
    age = _calculate_age(body.date_of_birth)
    if age < settings.MIN_AGE_YEARS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You must be at least {settings.MIN_AGE_YEARS} years old to register.",
        )

    existing = db.query(User).filter(
        (User.username == body.username) | (User.email == body.email)
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username or email already registered")

    user = User(
        username=body.username,
        email=body.email,
        phone=body.phone,
        password_hash=hash_password(body.password),
        date_of_birth=body.date_of_birth,
        is_age_verified=True,  # self-declared at signup; real DOB/document check happens in KYC flow
        kyc_status="not_started",
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username or email already registered")

    wallet = Wallet(user_id=user.id, balance_paise=0)
    db.add(wallet)

    try:
        AuditService.log(
            db, action="user.signup", actor_user_id=user.id, actor_type="user",
            target_type="user", target_id=user.id,
            ip_address=get_client_ip(request),
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Signup failed after user row was created (wallet/audit step)")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Signup failed, please try again")

    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(
        (User.username == body.username_or_email) | (User.email == body.username_or_email)
    ).first()

    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username/email or password")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")

    user.last_login_at = now_utc()
    AuditService.log(
        db, action="user.login", actor_user_id=user.id, actor_type="user",
        target_type="user", target_id=user.id,
        ip_address=get_client_ip(request),
    )
    db.commit()

    access_token = create_access_token(subject=str(user.id), extra_claims={"is_admin": user.is_admin})
    refresh_token = create_refresh_token(subject=str(user.id))
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    try:
        payload = decode_token(body.refresh_token)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    import uuid as uuid_module
    user = db.query(User).filter(User.id == uuid_module.UUID(payload["sub"])).first()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    access_token = create_access_token(subject=str(user.id), extra_claims={"is_admin": user.is_admin})
    new_refresh_token = create_refresh_token(subject=str(user.id))
    return TokenResponse(access_token=access_token, refresh_token=new_refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(token_payload: dict = Depends(lambda: None), current_user: User = Depends(get_current_user)):
    return None


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user
