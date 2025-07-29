"""
Assessment model for storing evaluation results.
"""
from datetime import datetime
from typing import List, Dict, Any
import json
from sqlalchemy import Column, Integer, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from src.database.base import Base


class Assessment(Base):
    """
    Assessment model representing evaluation results for a submission.
    """
    __tablename__ = "assessments"

    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("submissions.id"), nullable=False, unique=True, index=True)
    task_achievement_score = Column(Float, nullable=False)
    coherence_cohesion_score = Column(Float, nullable=False)
    lexical_resource_score = Column(Float, nullable=False)
    grammatical_accuracy_score = Column(Float, nullable=False)
    overall_band_score = Column(Float, nullable=False)
    detailed_feedback = Column(Text, nullable=False)
    improvement_suggestions = Column(Text, nullable=False)  # JSON string
    assessed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    submission = relationship("Submission", back_populates="assessment")

    def __repr__(self):
        return f"<Assessment(id={self.id}, submission_id={self.submission_id}, overall_score={self.overall_band_score})>"

    @property
    def improvement_suggestions_list(self) -> List[str]:
        """Get improvement suggestions as a list."""
        try:
            return json.loads(self.improvement_suggestions)
        except (json.JSONDecodeError, TypeError):
            return []

    @improvement_suggestions_list.setter
    def improvement_suggestions_list(self, suggestions: List[str]):
        """Set improvement suggestions from a list."""
        self.improvement_suggestions = json.dumps(suggestions)

    @property
    def scores_dict(self) -> Dict[str, float]:
        """Get all scores as a dictionary."""
        return {
            "task_achievement": self.task_achievement_score,
            "coherence_cohesion": self.coherence_cohesion_score,
            "lexical_resource": self.lexical_resource_score,
            "grammatical_accuracy": self.grammatical_accuracy_score,
            "overall_band_score": self.overall_band_score
        }

    def validate_scores(self) -> bool:
        """Validate that all scores are within valid IELTS band range (0.0-9.0)."""
        scores = [
            self.task_achievement_score,
            self.coherence_cohesion_score,
            self.lexical_resource_score,
            self.grammatical_accuracy_score,
            self.overall_band_score
        ]
        return all(0.0 <= score <= 9.0 for score in scores)

    def calculate_overall_score(self) -> float:
        """Calculate overall band score as average of four criteria."""
        individual_scores = [
            self.task_achievement_score,
            self.coherence_cohesion_score,
            self.lexical_resource_score,
            self.grammatical_accuracy_score
        ]
        return round(sum(individual_scores) / len(individual_scores), 1)