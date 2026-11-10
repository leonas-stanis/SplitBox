from __future__ import annotations

from datetime import UTC, datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base

class User(Base):
    __tablename__ = "user"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    image_file: Mapped[str | None] = mapped_column(String(200), nullable=True, default=None,)
    
    readings:Mapped[list[Reading]] = relationship(back_populates="author",
        cascade="all, delete-orphan") 
    
    @property
    def image_path(self)->str:
        if self.image_file:
            return f"/media/profile_pics/{self.image_file}"
        return "/static/profile_pics/default.jpg"
    
class Reading(Base):
    __tablename__ = "reading"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    sensor: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[float] = mapped_column(Float, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    date_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                     default=lambda: datetime.now(UTC))
    author: Mapped[User] = relationship(back_populates="readings")