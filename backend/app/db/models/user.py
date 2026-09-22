from typing import List

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, uuid_pk


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = uuid_pk()
    email: Mapped[str] = mapped_column(unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(nullable=False)
    business_name: Mapped[str] = mapped_column(nullable=False)
    display_name: Mapped[str] = mapped_column(default="", nullable=False)
    # Access role within the company: "owner" | "member".
    role: Mapped[str] = mapped_column(default="owner", nullable=False)
    # The workspace this account signs in to. Nullable so an account can exist
    # for the moment between registering and the company row being written —
    # the frontend has a recovery screen for exactly that state.
    company_id: Mapped[str | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL"), index=True, nullable=True
    )

    company: Mapped["Company | None"] = relationship(  # noqa: F821
        back_populates="members", foreign_keys=[company_id]
    )
