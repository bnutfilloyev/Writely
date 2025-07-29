"""
Rate limiting service for managing daily submission limits and tracking.
"""
from typing import Optional, Dict, Any, List
from datetime import date, datetime, timedelta
from dataclasses import dataclass
from enum import Enum
from sqlalchemy.ext.asyncio import AsyncSession

from src.repositories.rate_limit_repository import RateLimitRepository
from src.repositories.user_repository import UserRepository
from src.models.user import User
from src.models.rate_limit import RateLimit


class RateLimitStatus(Enum):
    """Rate limit status enumeration."""
    ALLOWED = "allowed"
    LIMIT_REACHED = "limit_reached"
    USER_NOT_FOUND = "user_not_found"


@dataclass
class RateLimitResult:
    """Result of rate limit check."""
    status: RateLimitStatus
    current_count: int
    daily_limit: int
    remaining: int
    can_submit: bool
    reset_time: Optional[datetime] = None
    message: Optional[str] = None


@dataclass
class UsageStatistics:
    """Daily usage statistics."""
    date: date
    total_users: int
    total_submissions: int
    users_at_limit: int
    average_submissions_per_user: float


class RateLimitService:
    """
    Service for managing rate limits and daily submission tracking.
    Implements requirements 5.1, 5.2, 5.3, 5.4.
    """
    
    DEFAULT_DAILY_LIMIT = 3
    PRO_DAILY_LIMIT = 100  # Effectively unlimited for pro users
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.rate_limit_repo = RateLimitRepository(session)
        self.user_repo = UserRepository(session)
    
    async def check_rate_limit(self, telegram_id: int, is_pro: bool = False) -> RateLimitResult:
        """
        Check if user can make a submission based on daily limits.
        
        Requirements:
        - 5.1: Track daily submission count per user
        - 5.2: Inform user when reaching 3 submissions per day
        - 5.3: Suggest Pro upgrade when limit reached
        """
        # Get user
        user = await self.user_repo.get_by_telegram_id(telegram_id)
        if not user:
            return RateLimitResult(
                status=RateLimitStatus.USER_NOT_FOUND,
                current_count=0,
                daily_limit=self.DEFAULT_DAILY_LIMIT,
                remaining=0,
                can_submit=False,
                message="User not found. Please start the bot first."
            )
        
        # Determine daily limit based on pro status
        daily_limit = self.PRO_DAILY_LIMIT if (is_pro or user.is_pro) else self.DEFAULT_DAILY_LIMIT
        
        # Get current daily count
        current_count = await self.rate_limit_repo.get_daily_count(user.id)
        remaining = max(0, daily_limit - current_count)
        can_submit = current_count < daily_limit
        
        # Calculate reset time (midnight tomorrow)
        tomorrow = date.today() + timedelta(days=1)
        reset_time = datetime.combine(tomorrow, datetime.min.time())
        
        if can_submit:
            status = RateLimitStatus.ALLOWED
            message = None
            if remaining <= 1 and not (is_pro or user.is_pro):
                message = f"You have {remaining} submission{'s' if remaining != 1 else ''} remaining today."
        else:
            status = RateLimitStatus.LIMIT_REACHED
            if is_pro or user.is_pro:
                message = "You've reached your daily limit. Please try again tomorrow."
            else:
                message = (
                    f"You've reached your daily limit of {daily_limit} submissions. "
                    "Upgrade to Pro for unlimited daily checks!"
                )
        
        return RateLimitResult(
            status=status,
            current_count=current_count,
            daily_limit=daily_limit,
            remaining=remaining,
            can_submit=can_submit,
            reset_time=reset_time,
            message=message
        )
    
    async def record_submission(self, telegram_id: int) -> RateLimitResult:
        """
        Record a submission and update rate limit counters.
        
        Requirements:
        - 5.1: Track daily submission count per user
        """
        # Get user
        user = await self.user_repo.get_by_telegram_id(telegram_id)
        if not user:
            return RateLimitResult(
                status=RateLimitStatus.USER_NOT_FOUND,
                current_count=0,
                daily_limit=self.DEFAULT_DAILY_LIMIT,
                remaining=0,
                can_submit=False,
                message="User not found."
            )
        
        # Increment counters
        await self.rate_limit_repo.increment_daily_count(user.id)
        await self.user_repo.increment_daily_submissions(telegram_id)
        
        # Return updated status
        return await self.check_rate_limit(telegram_id, user.is_pro)
    
    async def reset_daily_counters(self) -> int:
        """
        Reset daily counters for all users.
        
        Requirements:
        - 5.4: Reset daily submission counter when new day begins
        
        Returns:
            Number of users whose counters were reset.
        """
        # This would typically be called by a scheduled job at midnight
        users_reset = 0
        
        # Get all users who made submissions yesterday
        yesterday = date.today() - timedelta(days=1)
        users_with_submissions = await self.user_repo.get_users_by_submission_date(yesterday)
        
        for user in users_with_submissions:
            # Reset user's daily submission count
            await self.user_repo.reset_daily_submissions(user.telegram_id)
            users_reset += 1
        
        return users_reset
    
    async def get_user_usage_stats(self, telegram_id: int, days: int = 7) -> Dict[str, Any]:
        """Get usage statistics for a specific user."""
        user = await self.user_repo.get_by_telegram_id(telegram_id)
        if not user:
            return {"error": "User not found"}
        
        # Get rate limit history
        rate_limits = await self.rate_limit_repo.get_user_rate_limits(user.id, days)
        
        # Calculate statistics
        total_submissions = sum(rl.submission_count for rl in rate_limits)
        active_days = len([rl for rl in rate_limits if rl.submission_count > 0])
        
        # Get weekly pattern
        weekly_pattern = await self.rate_limit_repo.get_weekly_usage_pattern(user.id)
        
        return {
            "user_id": user.telegram_id,
            "is_pro": user.is_pro,
            "total_submissions": total_submissions,
            "active_days": active_days,
            "average_per_day": total_submissions / days if days > 0 else 0,
            "weekly_pattern": weekly_pattern,
            "current_daily_count": await self.rate_limit_repo.get_daily_count(user.id)
        }
    
    async def get_daily_statistics(self, target_date: Optional[date] = None) -> UsageStatistics:
        """Get system-wide daily usage statistics."""
        stats = await self.rate_limit_repo.get_daily_statistics(target_date)
        
        return UsageStatistics(
            date=stats["date"],
            total_users=stats["total_users"],
            total_submissions=stats["total_submissions"],
            users_at_limit=stats["users_at_limit"],
            average_submissions_per_user=stats["average_submissions_per_user"]
        )
    
    async def cleanup_old_records(self, days_to_keep: int = 90) -> int:
        """Clean up old rate limit records."""
        return await self.rate_limit_repo.cleanup_old_records(days_to_keep)
    
    async def get_users_at_limit(self, target_date: Optional[date] = None) -> List[RateLimit]:
        """Get users who have reached their daily limit."""
        return await self.rate_limit_repo.get_users_by_usage_level(
            target_date, min_submissions=self.DEFAULT_DAILY_LIMIT
        )
    
    async def is_user_active_today(self, telegram_id: int) -> bool:
        """Check if user has made any submissions today."""
        user = await self.user_repo.get_by_telegram_id(telegram_id)
        if not user:
            return False
        
        return await self.rate_limit_repo.is_user_active_today(user.id)
    
    async def get_time_until_reset(self) -> timedelta:
        """Get time remaining until daily reset (midnight)."""
        now = datetime.now()
        tomorrow = date.today() + timedelta(days=1)
        midnight = datetime.combine(tomorrow, datetime.min.time())
        return midnight - now