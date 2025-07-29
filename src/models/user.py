"""
User model for storing Telegram user information.
"""
from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date
from sqlalchemy.orm import relationship
from src.database.base import Base


class User(Base):
    """
    User model representing a Telegram user.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_pro = Column(Boolean, default=False, nullable=False)
    daily_submissions = Column(Integer, default=0, nullable=False)
    last_submission_date = Column(Date, nullable=True)

    # Relationships
    submissions = relationship("Submission", back_populates="user", cascade="all, delete-orphan")
    rate_limits = relationship("RateLimit", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, username='{self.username}')>"

    def reset_daily_submissions(self):
        """Reset daily submission count and update last submission date."""
        self.daily_submissions = 0
        self.last_submission_date = date.today()

    def increment_daily_submissions(self):
        """Increment daily submission count."""
        today = date.today()
        if self.last_submission_date != today:
            self.reset_daily_submissions()
        self.daily_submissions += 1
        self.last_submission_date = today