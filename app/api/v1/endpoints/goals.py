from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.goal import Goal, GoalStatus
from app.models.user import User
from app.schemas.goal import GoalCreate, GoalDeposit, GoalOut, GoalProgress, GoalUpdate

router = APIRouter(prefix="/goals", tags=["goals"])


def _get_or_404(db: Session, goal_id: UUID, user_id: UUID) -> Goal:
    goal = db.scalar(select(Goal).where(Goal.id == goal_id, Goal.user_id == user_id))
    if goal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Goal not found")
    return goal


def _to_progress(goal: Goal) -> GoalProgress:
    today = date.today()
    target = float(goal.target_amount)
    saved = float(goal.saved_amount)
    remaining = max(target - saved, 0)
    progress_pct = round((saved / target) * 100, 2) if target > 0 else 0.0
    days_remaining = max((goal.target_date - today).days, 0)
    months_remaining = max(days_remaining / 30, 1)
    monthly_savings_required = round(remaining / months_remaining, 2) if remaining > 0 else 0.0

    return GoalProgress(
        goal_id=goal.id,
        title=goal.title,
        target_amount=target,
        saved_amount=saved,
        remaining_amount=remaining,
        progress_pct=progress_pct,
        target_date=goal.target_date,
        days_remaining=days_remaining,
        monthly_savings_required=monthly_savings_required,
        status=goal.status,
    )


@router.post("", response_model=GoalOut, status_code=status.HTTP_201_CREATED)
def create_goal(
    payload: GoalCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Goal:
    goal = Goal(**payload.model_dump(), user_id=current_user.id)
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


@router.get("", response_model=list[GoalOut])
def list_goals(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    status_filter: Annotated[GoalStatus | None, Query(alias="status")] = None,
) -> list[Goal]:
    q = select(Goal).where(Goal.user_id == current_user.id)
    if status_filter:
        q = q.where(Goal.status == status_filter)
    return list(db.scalars(q.order_by(Goal.target_date.asc())).all())


@router.get("/progress", response_model=list[GoalProgress])
def all_goals_progress(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[GoalProgress]:
    goals = db.scalars(
        select(Goal).where(Goal.user_id == current_user.id, Goal.status == GoalStatus.active)
        .order_by(Goal.target_date.asc())
    ).all()
    return [_to_progress(g) for g in goals]


@router.get("/{goal_id}", response_model=GoalOut)
def get_goal(
    goal_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Goal:
    return _get_or_404(db, goal_id, current_user.id)


@router.get("/{goal_id}/progress", response_model=GoalProgress)
def goal_progress(
    goal_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> GoalProgress:
    goal = _get_or_404(db, goal_id, current_user.id)
    return _to_progress(goal)


@router.post("/{goal_id}/deposit", response_model=GoalProgress)
def deposit(
    goal_id: UUID,
    payload: GoalDeposit,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> GoalProgress:
    goal = _get_or_404(db, goal_id, current_user.id)
    if goal.status != GoalStatus.active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Goal is not active")
    goal.saved_amount = float(goal.saved_amount) + payload.amount
    if float(goal.saved_amount) >= float(goal.target_amount):
        goal.status = GoalStatus.completed
    db.commit()
    db.refresh(goal)
    return _to_progress(goal)


@router.patch("/{goal_id}", response_model=GoalOut)
def update_goal(
    goal_id: UUID,
    payload: GoalUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Goal:
    goal = _get_or_404(db, goal_id, current_user.id)
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(goal, field, value)
    db.commit()
    db.refresh(goal)
    return goal


@router.delete("/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(
    goal_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    goal = _get_or_404(db, goal_id, current_user.id)
    db.delete(goal)
    db.commit()
