"""
Rate limit repository for daily usage tracking and limits.
"""
from typing import Optional, List
from datetime import date, datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, desc
from src.models.rate_limit import RateLimit
from src.repositories.base_repository import BaseRepository


class RateLimitRepository(BaseRepository[RateLimit]):
    """
    Repository for RateLimit model operations.
    """
    
    def __init__(self, session: AsyncSession):
        super().__init__(RateLimit, session)

    async def get_or_create_today_limit(self, user_id: int) -> RateLimit:
        """Get or create rate limit record for today."""
        today = date.today()
        
        # Try to get existing record for today
        result = await self.session.execute(
            select(RateLimit).where(
                and_(
                    RateLimit.user_id == user_id,
                    RateLimit.submission_date == today
                )
            )
        )
        rate_limit = result.scalar_one_or_none()
        
        if rate_limit:
            return rate_limit
        
        # Create new record for today
        return await self.create(
            user_id=user_id,
            submission_date=today,
            submission_count=0
        )

    async def get_daily_count(self, user_id: int, target_date: Optional[date] = None) -> int:
        """Get submission count for a user on a specific date (defaults to today)."""
        if target_date is None:
            target_date = date.today()
        
        result = await self.session.execute(
            select(RateLimit).where(
                and_(
                    RateLimit.user_id == user_id,
                    RateLimit.submission_date == target_date
                )
            )
        )
        rate_limit = result.scalar_one_or_none()
        
        return rate_limit.submission_count if rate_limit else 0

    async def increment_daily_count(self, user_id: int) -> RateLimit:
        """Increment daily submission count for a user."""
        rate_limit = await self.get_or_create_today_limit(user_id)
        rate_limit.increment_count()
        await self.session.commit()
        return rate_limit

    async def reset_daily_count(self, user_id: int, target_date: Optional[date] = None) -> Optional[RateLimit]:
        """Reset daily submission count for a user on a specific date."""
        if target_date is None:
            target_date = date.today()
        
        result = await self.session.execute(
            select(RateLimit).where(
                and_(
                    RateLimit.user_id == user_id,
                    RateLimit.submission_date == target_date
                )
            )
        )
        rate_limit = result.scalar_one_or_none()
        
        if rate_limit:
            rate_limit.submission_count = 0
            await self.session.commit()
            return rate_limit
        
        return None

    async def check_daily_limit(self, user_id: int, daily_limit: int = 3) -> dict:
        """Check if user has reached daily limit and return status."""
        current_count = await self.get_daily_count(user_id)
        
        return {
            "current_count": current_count,
            "daily_limit": daily_limit,
            "remaining": max(0, daily_limit - current_count),
            "limit_reached": current_count >= daily_limit,
            "can_submit": current_count < daily_limit
        }

    async def get_user_rate_limits(self, user_id: int, days: int = 30) -> List[RateLimit]:
        """Get rate limit history for a user over specified number of days."""
        start_date = date.today() - timedelta(days=days)
        
        result = await self.session.execute(
            select(RateLimit).where(
                and_(
                    RateLimit.user_id == user_id,
                    RateLimit.submission_date >= start_date
                )
            ).order_by(desc(RateLimit.submission_date))
        )
        return result.scalars().all()

    async def get_rate_limits_by_date(self, target_date: date) -> List[RateLimit]:
        """Get all rate limits for a specific date."""
        result = await self.session.execute(
            select(RateLimit).where(RateLimit.submission_date == target_date)
        )
        return result.scalars().all()

    async def cleanup_old_records(self, days_to_keep: int = 90) -> int:
        """Clean up old rate limit records older than specified days."""
        cutoff_date = date.today() - timedelta(days=days_to_keep)
        
        result = await self.session.execute(
            delete(RateLimit).where(RateLimit.submission_date < cutoff_date)
        )
        await self.session.commit()
        return result.rowcount

    async def get_daily_statistics(self, target_date: Optional[date] = None) -> dict:
        """Get daily statistics for rate limits."""
        if target_date is None:
            target_date = date.today()
        
        rate_limits = await self.get_rate_limits_by_date(target_date)
        
        total_users = len(rate_limits)
        total_submissions = sum(rl.submission_count for rl in rate_limits)
        users_at_limit = len([rl for rl in rate_limits if rl.submission_count >= 3])
        
        return {
            "date": target_date,
            "total_users": total_users,
            "total_submissions": total_submissions,
            "users_at_limit": users_at_limit,
            "average_submissions_per_user": total_submissions / total_users if total_users > 0 else 0
        }

    async def get_weekly_usage_pattern(self, user_id: int) -> List[dict]:
        """Get weekly usage pattern for a user (last 7 days)."""
        rate_limits = await self.get_user_rate_limits(user_id, days=7)
        
        # Create a dict for easy lookup
        usage_by_date = {rl.submission_date: rl.submission_count for rl in rate_limits}
        
        # Generate last 7 days data
        weekly_pattern = []
        for i in range(7):
            target_date = date.today() - timedelta(days=i)
            weekly_pattern.append({
                "date": target_date,
                "day_name": target_date.strftime("%A"),
                "submission_count": usage_by_date.get(target_date, 0)
            })
        
        return list(reversed(weekly_pattern))  # Return in chronological order

    async def is_user_active_today(self, user_id: int) -> bool:
        """Check if user has made any submissions today."""
        today_count = await self.get_daily_count(user_id)
        return today_count > 0

    async def get_users_by_usage_level(self, target_date: Optional[date] = None,
                                      min_submissions: int = 1) -> List[RateLimit]:
        """Get users who have made at least minimum submissions on a date."""
        if target_date is None:
            target_date = date.today()
        
        result = await self.session.execute(
            select(RateLimit).where(
                and_(
                    RateLimit.submission_date == target_date,
                    RateLimit.submission_count >= min_submissions
                )
            ).order_by(desc(RateLimit.submission_count))
        )
        return result.scalars().all()