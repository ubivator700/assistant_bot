from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, Index, SmallInteger, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(SmallInteger, default=2)  # 1=high, 2=medium, 3=low
    status: Mapped[str] = mapped_column(
        Enum("pending", "done", "cancelled"), default="pending"
    )
    deadline: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, onupdate=func.now())

    __table_args__ = (Index("ix_tasks_user_status", "user_id", "status"),)
