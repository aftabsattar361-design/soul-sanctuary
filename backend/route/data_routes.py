"""Projects / datasets endpoints."""
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from auth import get_current_user, require_admin
from database import get_db
from model import Project, User
from schemas import ProjectCreate, ProjectList, ProjectOut

router = APIRouter(prefix="/projects", tags=["data"])


@router.get("", response_model=ProjectList)
def list_projects(search: str | None = None, status_filter: str | None = Query(default=None, alias="status"),
                  limit: int = Query(default=100, ge=1, le=500), offset: int = Query(default=0, ge=0),
                  db: Session = Depends(get_db), _: User = Depends(get_current_user)) -> ProjectList:
    """Projects (newest update first) with optional name/owner search and status filter."""
    cond = []
    if search:
        like = f"%{search.strip()}%"
        cond.append(Project.name.ilike(like) | Project.owner_name.ilike(like))
    if status_filter:
        cond.append(Project.status == status_filter)
    total = db.scalar(select(func.count()).select_from(Project).where(*cond)) or 0
    entries = db.scalar(select(func.coalesce(func.sum(Project.entries_count), 0)).where(*cond)) or 0
    items = db.scalars(select(Project).where(*cond).order_by(Project.last_updated.desc(), Project.id.desc())
                       .limit(limit).offset(offset)).all()
    return ProjectList(items=[ProjectOut.model_validate(p) for p in items], total=total, total_entries=int(entries))


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(body: ProjectCreate, db: Session = Depends(get_db), _: User = Depends(require_admin)) -> Project:
    """Add a project (admin only)."""
    project = Project(name=body.name.strip(), entries_count=body.entries_count, owner_name=body.owner_name.strip(),
                      status=body.status)
    db.add(project)
    db.commit()
    return project
