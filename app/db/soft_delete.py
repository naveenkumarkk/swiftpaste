from datetime import datetime, timezone

from sqlalchemy import event
from sqlalchemy.orm import Session, with_loader_criteria

from app.db.mixins import SoftDeleteMixin


@event.listens_for(Session, "do_orm_execute")
def _soft_delete_filter(execute_state):
    if not execute_state.is_select:
        return

    if execute_state.execution_options.get("include_deleted", False):
        return

    execute_state.statement = execute_state.statement.options(
        with_loader_criteria(
            SoftDeleteMixin,
            lambda cls: cls.deleted_at.is_(None),
            include_aliases=True,
        )
    )


@event.listens_for(Session, "before_flush")
def _soft_delete_before_flush(session: Session, flush_context, instances):
    now = datetime.now(timezone.utc)

    for obj in list(session.deleted):
        if isinstance(obj, SoftDeleteMixin):
            if obj.deleted_at is None:
                obj.deleted_at = now
            session.add(obj)
            try:
                session.deleted.remove(obj)
            except KeyError:
                pass