from sqlalchemy import ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class ToolCall(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "tool_calls"

    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True, nullable=False)
    tool_name: Mapped[str] = mapped_column(String(120), nullable=False)
    tool_input: Mapped[dict] = mapped_column(JSON, nullable=False)
    tool_output: Mapped[dict] = mapped_column(JSON, nullable=False)

    run = relationship("Run", back_populates="tool_calls")

