from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Loan(Base):
    """One borrowed copy of a book. Active while returned_at is NULL.

    Copies of a title are interchangeable, so a loan links a borrower to a
    title, not to a physical copy.
    """

    __tablename__ = "loans"
    __table_args__ = (
        # A borrower may hold at most one copy of a title at a time.
        Index(
            "uq_loans_active_book_borrower",
            "book_id",
            "borrower_id",
            unique=True,
            sqlite_where=text("returned_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    book_id: Mapped[int] = mapped_column(Integer, ForeignKey("books.id"), nullable=False)
    borrower_id: Mapped[int] = mapped_column(Integer, ForeignKey("borrowers.id"), nullable=False)
    borrowed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    returned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    book: Mapped["Book"] = relationship("Book", back_populates="loans")  # noqa: F821
    borrower: Mapped["Borrower"] = relationship("Borrower", back_populates="loans")  # noqa: F821
