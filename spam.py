from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.core.config import settings
from app.core.errors import AppError
from app.database.session import get_db
from app.ml.detector import detector
from app.models import Check, User, utcnow
from app.schemas import BatchIn, DetectIn, ok

router = APIRouter(prefix="/api", tags=["spam"])


def _out(c: Check) -> dict:
    return {
        "id": c.id, "text": c.text, "label": c.label, "spam_probability": c.spam_probability,
        "engine": c.engine, "reasons": c.reasons, "created_at": c.created_at.isoformat(),
    }


def _run(db: Session, user: User, text: str) -> Check:
    text = text.strip()
    if not text or len(text) > settings.max_message_chars:
        raise AppError("INVALID_INPUT", "Messages must be 1 to %d characters." % settings.max_message_chars, 422)
    result = detector.predict(text)
    check = Check(user_id=user.id, text=text, **result)
    db.add(check)
    return check


@router.post("/detect")
def detect(body: DetectIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    check = _run(db, user, body.text)
    db.commit()
    return ok(_out(check), "Message analyzed")


@router.post("/detect/batch")
def detect_batch(body: BatchIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    checks = [_run(db, user, t) for t in body.messages]
    db.commit()
    return ok([_out(c) for c in checks], f"{len(checks)} messages analyzed")


@router.get("/history")
def history(
    label: str | None = Query(default=None, pattern="^(spam|ham)$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    q = select(Check).where(Check.user_id == user.id)
    if label:
        q = q.where(Check.label == label)
    rows = db.scalars(q.order_by(Check.id.desc()).limit(limit).offset(offset)).all()
    return ok([_out(c) for c in rows])


@router.delete("/history/{check_id}")
def delete_check(check_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    check = db.get(Check, check_id)
    if not check or check.user_id != user.id:
        raise AppError("NOT_FOUND", "Result not found.", 404)
    db.delete(check)
    db.commit()
    return ok(None, "Deleted")


@router.get("/stats")
def stats(db: Session = Depends(get_db), user: User = Depends(current_user)):
    base = Check.user_id == user.id
    total = db.scalar(select(func.count()).select_from(Check).where(base)) or 0
    spam = db.scalar(select(func.count()).select_from(Check).where(base, Check.label == "spam")) or 0
    since = utcnow() - timedelta(days=13)
    rows = db.execute(
        select(func.date(Check.created_at), Check.label, func.count())
        .where(base, Check.created_at >= since)
        .group_by(func.date(Check.created_at), Check.label)
    ).all()
    per_day: dict[str, dict[str, int]] = {}
    for day, lab, n in rows:
        per_day.setdefault(str(day), {"spam": 0, "ham": 0})[lab] = n
    return ok({
        "total": total, "spam": spam, "ham": total - spam,
        "spam_rate": round(spam / total, 3) if total else 0.0,
        "per_day": [{"date": d, **v} for d, v in sorted(per_day.items())],
    })


@router.get("/model")
def model_info(_: User = Depends(current_user)):
    return ok(detector.info)
