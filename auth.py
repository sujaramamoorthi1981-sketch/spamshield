import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.errors import AppError
from app.core.security import create_access_token, hash_password, verify_password
from app.database.session import get_db
from app.models import User
from app.schemas import LoginIn, RegisterIn, UserOut, ok

router = APIRouter(prefix="/api/auth", tags=["auth"])
log = logging.getLogger("spamshield.auth")


@router.post("/register", status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise AppError("EMAIL_TAKEN", "An account with this email already exists.", 409)
    user = User(name=body.name.strip(), email=email, password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    log.info("user registered id=%s", user.id)
    return ok({"token": create_access_token(user.id), "user": UserOut.model_validate(user)}, "Account created")


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if not user or not verify_password(body.password, user.password_hash):
        log.info("failed login attempt")
        raise AppError("INVALID_CREDENTIALS", "Email or password is incorrect.", 401)
    log.info("user login id=%s", user.id)
    return ok({"token": create_access_token(user.id), "user": UserOut.model_validate(user)}, "Signed in")


@router.get("/me")
def me(user: User = Depends(current_user)):
    return ok(UserOut.model_validate(user))
