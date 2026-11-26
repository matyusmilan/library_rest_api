from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Book(Base):
    __tablename__ = "books"
    __table_args__ = (
        CheckConstraint(
            "available_copies >= 0 AND available_copies <= total_copies",
            name="ck_books_available_within_total",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    author: Mapped[str] = mapped_column(String(255), nullable=False)
    isbn: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    total_copies: Mapped[int] = mapped_column(Integer, nullable=False)
    available_copies: Mapped[int] = mapped_column(Integer, nullable=False)
    is_borrowed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # FK to borrowers – nullable because a book may not be borrowed
    borrower_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("borrowers.id"), nullable=True, default=None
    )

    borrower: Mapped["Borrower | None"] = relationship(  # noqa: F821
        "Borrower", back_populates="borrowed_books"
    )

    loans: Mapped[list["Loan"]] = relationship("Loan", back_populates="book")  # noqa: F821
