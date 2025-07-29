"""
Submission model for storing writing submissions.
"""
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from src.database.base import Base


class TaskType(Enum):
    """Enumeration for IELTS task types."""
    TASK_1 = "task_1"
    TASK_2 = "task_2"


class ProcessingStatus(Enum):
    """Enumeration for submission processing status."""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class Submission(Base):
    """
    Submission model representing a writing submission.
    """
    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    text = Column(Text, nullable=False)
    task_type = Column(SQLEnum(TaskType), nullable=False)
    word_count = Column(Integer, nullable=False)
    submitted_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    processing_status = Column(SQLEnum(ProcessingStatus), default=ProcessingStatus.PENDING, nullable=False)

    # Relationships
    user = relationship("User", back_populates="submissions")
    assessment = relationship("Assessment", back_populates="submission", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Submission(id={self.id}, user_id={self.user_id}, task_type={self.task_type.value}, status={self.processing_status.value})>"

    @property
    def is_completed(self) -> bool:
        """Check if submission processing is completed."""
        return self.processing_status == ProcessingStatus.COMPLETED

    @property
    def is_pending(self) -> bool:
        """Check if submission is still pending processing."""
        return self.processing_status == ProcessingStatus.PENDING

    @property
    def is_failed(self) -> bool:
        """Check if submission processing failed."""
        return self.processing_status == ProcessingStatus.FAILED