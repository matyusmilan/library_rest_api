from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Book(Base):
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    author: Mapped[str] = mapped_column(String(255), nullable=False)
    isbn: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    is_borrowed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # FK to borrowers – nullable because a book may not be borrowed
    borrower_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("borrowers.id"), nullable=True, default=None
    )

    borrower: Mapped["Borrower | None"] = relationship(  # noqa: F821
        "Borrower", back_populates="borrowed_books"
    )
