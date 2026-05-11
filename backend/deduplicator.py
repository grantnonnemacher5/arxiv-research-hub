from sqlalchemy import select
from sqlalchemy.orm import Session

from database import Paper


def is_duplicate(arxiv_id: str, db: Session) -> bool:
    return db.scalar(select(Paper.id).where(Paper.arxiv_id == arxiv_id)) is not None
