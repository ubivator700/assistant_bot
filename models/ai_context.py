from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class AIContext(Base):
    __tablename__ = "ai_context"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    context_json: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, onupdate=func.now())
