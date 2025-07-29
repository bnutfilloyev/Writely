"""
Submission repository for writing submission operations.
"""
from typing import Optional, List
from datetime import datetime, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, desc, and_
from sqlalchemy.orm import selectinload, joinedload
from src.models.submission import Submission, TaskType, ProcessingStatus
from src.repositories.base_repository import BaseRepository


class SubmissionRepository(BaseRepository[Submission]):
    """
    Repository for Submission model operations.
    """
    
    def __init__(self, session: AsyncSession):
        super().__init__(Submission, session)

    async def create_submission(self, user_id: int, text: str, task_type: TaskType,
                               word_count: int) -> Submission:
        """Create a new submission."""
        return await self.create(
            user_id=user_id,
            text=text,
            task_type=task_type,
            word_count=word_count,
            processing_status=ProcessingStatus.PENDING
        )

    async def get_by_user_id(self, user_id: int, limit: Optional[int] = None,
                            include_assessment: bool = False) -> List[Submission]:
        """Get submissions by user ID, ordered by most recent first."""
        query = select(Submission).where(Submission.user_id == user_id).order_by(desc(Submission.submitted_at))
        
        if include_assessment:
            query = query.options(selectinload(Submission.assessment))
        
        if limit:
            query = query.limit(limit)
        
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_with_assessment(self, submission_id: int) -> Optional[Submission]:
        """Get submission with its assessment loaded."""
        result = await self.session.execute(
            select(Submission)
            .options(selectinload(Submission.assessment))
            .where(Submission.id == submission_id)
        )
        return result.scalar_one_or_none()

    async def get_pending_submissions(self, limit: Optional[int] = None) -> List[Submission]:
        """Get submissions that are pending processing."""
        query = select(Submission).where(Submission.processing_status == ProcessingStatus.PENDING)
        if limit:
            query = query.limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_completed_submissions(self, user_id: Optional[int] = None,
                                       limit: Optional[int] = None) -> List[Submission]:
        """Get completed submissions, optionally filtered by user."""
        query = select(Submission).where(Submission.processing_status == ProcessingStatus.COMPLETED)
        
        if user_id:
            query = query.where(Submission.user_id == user_id)
        
        query = query.order_by(desc(Submission.submitted_at))
        
        if limit:
            query = query.limit(limit)
        
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_failed_submissions(self, limit: Optional[int] = None) -> List[Submission]:
        """Get submissions that failed processing."""
        query = select(Submission).where(Submission.processing_status == ProcessingStatus.FAILED)
        if limit:
            query = query.limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def update_processing_status(self, submission_id: int, 
                                     status: ProcessingStatus) -> Optional[Submission]:
        """Update submission processing status."""
        await self.session.execute(
            update(Submission)
            .where(Submission.id == submission_id)
            .values(processing_status=status)
        )
        await self.session.commit()
        return await self.get_by_id(submission_id)

    async def get_by_task_type(self, task_type: TaskType, user_id: Optional[int] = None,
                              limit: Optional[int] = None) -> List[Submission]:
        """Get submissions by task type, optionally filtered by user."""
        query = select(Submission).where(Submission.task_type == task_type)
        
        if user_id:
            query = query.where(Submission.user_id == user_id)
        
        query = query.order_by(desc(Submission.submitted_at))
        
        if limit:
            query = query.limit(limit)
        
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_submissions_by_date_range(self, start_date: datetime, end_date: datetime,
                                           user_id: Optional[int] = None) -> List[Submission]:
        """Get submissions within a date range."""
        query = select(Submission).where(
            and_(
                Submission.submitted_at >= start_date,
                Submission.submitted_at <= end_date
            )
        )
        
        if user_id:
            query = query.where(Submission.user_id == user_id)
        
        query = query.order_by(desc(Submission.submitted_at))
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_daily_submission_count(self, user_id: int, target_date: date) -> int:
        """Get submission count for a user on a specific date."""
        start_datetime = datetime.combine(target_date, datetime.min.time())
        end_datetime = datetime.combine(target_date, datetime.max.time())
        
        submissions = await self.get_submissions_by_date_range(
            start_datetime, end_datetime, user_id
        )
        return len(submissions)

    async def get_user_statistics(self, user_id: int) -> dict:
        """Get submission statistics for a user."""
        all_submissions = await self.get_by_user_id(user_id)
        
        total_submissions = len(all_submissions)
        task1_count = len([s for s in all_submissions if s.task_type == TaskType.TASK_1])
        task2_count = len([s for s in all_submissions if s.task_type == TaskType.TASK_2])
        completed_count = len([s for s in all_submissions if s.processing_status == ProcessingStatus.COMPLETED])
        pending_count = len([s for s in all_submissions if s.processing_status == ProcessingStatus.PENDING])
        failed_count = len([s for s in all_submissions if s.processing_status == ProcessingStatus.FAILED])
        
        return {
            "total_submissions": total_submissions,
            "task1_submissions": task1_count,
            "task2_submissions": task2_count,
            "completed_submissions": completed_count,
            "pending_submissions": pending_count,
            "failed_submissions": failed_count,
            "average_word_count": sum(s.word_count for s in all_submissions) / total_submissions if total_submissions > 0 else 0
        }

    async def get_recent_submissions_with_assessments(self, user_id: int, 
                                                     limit: int = 10) -> List[Submission]:
        """Get recent submissions with assessments for history display."""
        result = await self.session.execute(
            select(Submission)
            .options(selectinload(Submission.assessment))
            .where(
                and_(
                    Submission.user_id == user_id,
                    Submission.processing_status == ProcessingStatus.COMPLETED
                )
            )
            .order_by(desc(Submission.submitted_at))
            .limit(limit)
        )
        return result.scalars().all()