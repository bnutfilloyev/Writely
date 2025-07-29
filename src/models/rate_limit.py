"""
Rate limit model for tracking daily submission limits.
"""
from datetime import datetime, date
from sqlalchemy import Column, Integer, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from src.database.base import Base


class RateLimit(Base):
    """
    Rate limit model for tracking daily submission counts per user.
    """
    __tablename__ = "rate_limits"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    submission_date = Column(Date, nullable=False, index=True)
    submission_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="rate_limits")

    def __repr__(self):
        return f"<RateLimit(id={self.id}, user_id={self.user_id}, date={self.submission_date}, count={self.submission_count})>"

    @property
    def is_today(self) -> bool:
        """Check if this rate limit record is for today."""
        return self.submission_date == date.today()

    def increment_count(self):
        """Increment the submission count."""
        self.submission_count += 1

    @classmethod
    def create_for_today(cls, user_id: int) -> "RateLimit":
        """Create a new rate limit record for today."""
        return cls(
            user_id=user_id,
            submission_date=date.today(),
            submission_count=0
        )