"""
Assessment repository for evaluation results and history tracking.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_, func
from sqlalchemy.orm import selectinload, joinedload
from src.models.assessment import Assessment
from src.models.submission import Submission, TaskType
from src.repositories.base_repository import BaseRepository


class AssessmentRepository(BaseRepository[Assessment]):
    """
    Repository for Assessment model operations.
    """
    
    def __init__(self, session: AsyncSession):
        super().__init__(Assessment, session)

    async def create_assessment(self, submission_id: int, task_achievement_score: float,
                               coherence_cohesion_score: float, lexical_resource_score: float,
                               grammatical_accuracy_score: float, overall_band_score: float,
                               detailed_feedback: str, improvement_suggestions: List[str]) -> Assessment:
        """Create a new assessment."""
        assessment = Assessment(
            submission_id=submission_id,
            task_achievement_score=task_achievement_score,
            coherence_cohesion_score=coherence_cohesion_score,
            lexical_resource_score=lexical_resource_score,
            grammatical_accuracy_score=grammatical_accuracy_score,
            overall_band_score=overall_band_score,
            detailed_feedback=detailed_feedback
        )
        assessment.improvement_suggestions_list = improvement_suggestions
        
        self.session.add(assessment)
        await self.session.commit()
        await self.session.refresh(assessment)
        return assessment

    async def get_by_submission_id(self, submission_id: int) -> Optional[Assessment]:
        """Get assessment by submission ID."""
        result = await self.session.execute(
            select(Assessment).where(Assessment.submission_id == submission_id)
        )
        return result.scalar_one_or_none()

    async def get_with_submission(self, assessment_id: int) -> Optional[Assessment]:
        """Get assessment with submission details loaded."""
        result = await self.session.execute(
            select(Assessment)
            .options(selectinload(Assessment.submission))
            .where(Assessment.id == assessment_id)
        )
        return result.scalar_one_or_none()

    async def get_user_assessments(self, user_id: int, limit: Optional[int] = None,
                                  include_submission: bool = True) -> List[Assessment]:
        """Get assessments for a specific user, ordered by most recent first."""
        query = (
            select(Assessment)
            .join(Submission)
            .where(Submission.user_id == user_id)
            .order_by(desc(Assessment.assessed_at))
        )
        
        if include_submission:
            query = query.options(selectinload(Assessment.submission))
        
        if limit:
            query = query.limit(limit)
        
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_assessments_by_task_type(self, task_type: TaskType, user_id: Optional[int] = None,
                                          limit: Optional[int] = None) -> List[Assessment]:
        """Get assessments by task type, optionally filtered by user."""
        query = (
            select(Assessment)
            .join(Submission)
            .where(Submission.task_type == task_type)
        )
        
        if user_id:
            query = query.where(Submission.user_id == user_id)
        
        query = query.order_by(desc(Assessment.assessed_at))
        
        if limit:
            query = query.limit(limit)
        
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_assessments_by_date_range(self, start_date: datetime, end_date: datetime,
                                           user_id: Optional[int] = None) -> List[Assessment]:
        """Get assessments within a date range."""
        query = (
            select(Assessment)
            .join(Submission)
            .where(
                and_(
                    Assessment.assessed_at >= start_date,
                    Assessment.assessed_at <= end_date
                )
            )
        )
        
        if user_id:
            query = query.where(Submission.user_id == user_id)
        
        query = query.order_by(desc(Assessment.assessed_at))
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_user_progress_data(self, user_id: int, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get user's assessment history for progress tracking."""
        assessments = await self.get_user_assessments(user_id, limit, include_submission=True)
        
        progress_data = []
        for assessment in assessments:
            progress_data.append({
                "assessment_id": assessment.id,
                "submission_id": assessment.submission_id,
                "task_type": assessment.submission.task_type.value,
                "assessed_at": assessment.assessed_at,
                "overall_band_score": assessment.overall_band_score,
                "scores": assessment.scores_dict,
                "word_count": assessment.submission.word_count
            })
        
        return progress_data

    async def get_average_scores_by_user(self, user_id: int, task_type: Optional[TaskType] = None) -> Dict[str, float]:
        """Get average scores for a user, optionally filtered by task type."""
        query = (
            select(
                func.avg(Assessment.task_achievement_score).label('avg_task_achievement'),
                func.avg(Assessment.coherence_cohesion_score).label('avg_coherence_cohesion'),
                func.avg(Assessment.lexical_resource_score).label('avg_lexical_resource'),
                func.avg(Assessment.grammatical_accuracy_score).label('avg_grammatical_accuracy'),
                func.avg(Assessment.overall_band_score).label('avg_overall_band')
            )
            .join(Submission)
            .where(Submission.user_id == user_id)
        )
        
        if task_type:
            query = query.where(Submission.task_type == task_type)
        
        result = await self.session.execute(query)
        row = result.first()
        
        if not row or row.avg_overall_band is None:
            return {
                "avg_task_achievement": 0.0,
                "avg_coherence_cohesion": 0.0,
                "avg_lexical_resource": 0.0,
                "avg_grammatical_accuracy": 0.0,
                "avg_overall_band": 0.0
            }
        
        return {
            "avg_task_achievement": round(row.avg_task_achievement, 1),
            "avg_coherence_cohesion": round(row.avg_coherence_cohesion, 1),
            "avg_lexical_resource": round(row.avg_lexical_resource, 1),
            "avg_grammatical_accuracy": round(row.avg_grammatical_accuracy, 1),
            "avg_overall_band": round(row.avg_overall_band, 1)
        }

    async def get_score_distribution(self, user_id: Optional[int] = None,
                                    task_type: Optional[TaskType] = None) -> Dict[str, int]:
        """Get distribution of overall band scores."""
        query = select(Assessment.overall_band_score).join(Submission)
        
        if user_id:
            query = query.where(Submission.user_id == user_id)
        
        if task_type:
            query = query.where(Submission.task_type == task_type)
        
        result = await self.session.execute(query)
        scores = result.scalars().all()
        
        # Create distribution buckets (0-1, 1-2, 2-3, etc.)
        distribution = {f"{i}-{i+1}": 0 for i in range(9)}
        
        for score in scores:
            bucket_index = min(int(score), 8)  # Cap at 8 for 8-9 bucket
            bucket_key = f"{bucket_index}-{bucket_index+1}"
            distribution[bucket_key] += 1
        
        return distribution

    async def get_recent_assessments_with_details(self, user_id: int, limit: int = 5) -> List[Dict[str, Any]]:
        """Get recent assessments with full details for history display."""
        assessments = await self.get_user_assessments(user_id, limit, include_submission=True)
        
        detailed_assessments = []
        for assessment in assessments:
            detailed_assessments.append({
                "id": assessment.id,
                "submission_id": assessment.submission_id,
                "task_type": assessment.submission.task_type.value,
                "submitted_at": assessment.submission.submitted_at,
                "assessed_at": assessment.assessed_at,
                "word_count": assessment.submission.word_count,
                "overall_band_score": assessment.overall_band_score,
                "individual_scores": {
                    "task_achievement": assessment.task_achievement_score,
                    "coherence_cohesion": assessment.coherence_cohesion_score,
                    "lexical_resource": assessment.lexical_resource_score,
                    "grammatical_accuracy": assessment.grammatical_accuracy_score
                },
                "detailed_feedback": assessment.detailed_feedback,
                "improvement_suggestions": assessment.improvement_suggestions_list
            })
        
        return detailed_assessments

    async def update_assessment_scores(self, assessment_id: int, **score_updates) -> Optional[Assessment]:
        """Update assessment scores."""
        assessment = await self.get_by_id(assessment_id)
        if not assessment:
            return None
        
        # Update individual scores if provided
        if 'task_achievement_score' in score_updates:
            assessment.task_achievement_score = score_updates['task_achievement_score']
        if 'coherence_cohesion_score' in score_updates:
            assessment.coherence_cohesion_score = score_updates['coherence_cohesion_score']
        if 'lexical_resource_score' in score_updates:
            assessment.lexical_resource_score = score_updates['lexical_resource_score']
        if 'grammatical_accuracy_score' in score_updates:
            assessment.grammatical_accuracy_score = score_updates['grammatical_accuracy_score']
        
        # Recalculate overall score if individual scores were updated
        if any(key.endswith('_score') for key in score_updates.keys()):
            assessment.overall_band_score = assessment.calculate_overall_score()
        
        await self.session.commit()
        return assessment