"""
User management service for handling user profiles and pro status.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, date, timedelta
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession

from src.repositories.user_repository import UserRepository
from src.repositories.rate_limit_repository import RateLimitRepository
from src.models.user import User


@dataclass
class UserProfile:
    """User profile data transfer object."""
    telegram_id: int
    username: Optional[str]
    first_name: Optional[str]
    created_at: datetime
    is_pro: bool
    daily_submissions: int
    last_submission_date: Optional[date]
    total_submissions: int = 0


@dataclass
class UserStats:
    """User statistics data transfer object."""
    total_submissions: int
    active_days: int
    average_submissions_per_day: float
    current_streak: int
    longest_streak: int
    pro_since: Optional[datetime] = None


class UserService:
    """
    Service for managing user profiles and pro status.
    Handles user creation, updates, and profile management.
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)
        self.rate_limit_repo = RateLimitRepository(session)
    
    async def get_or_create_user(self, telegram_id: int, username: Optional[str] = None,
                                first_name: Optional[str] = None) -> UserProfile:
        """
        Get existing user or create new one.
        
        Args:
            telegram_id: Telegram user ID
            username: Telegram username (optional)
            first_name: User's first name (optional)
            
        Returns:
            UserProfile object with user data
        """
        user = await self.user_repo.get_or_create_user(telegram_id, username, first_name)
        
        # Get total submissions count
        total_submissions = await self._get_user_total_submissions(user.id)
        
        return UserProfile(
            telegram_id=user.telegram_id,
            username=user.username,
            first_name=user.first_name,
            created_at=user.created_at,
            is_pro=user.is_pro,
            daily_submissions=user.daily_submissions,
            last_submission_date=user.last_submission_date,
            total_submissions=total_submissions
        )
    
    async def get_user_profile(self, telegram_id: int) -> Optional[UserProfile]:
        """Get user profile by Telegram ID."""
        user = await self.user_repo.get_by_telegram_id(telegram_id)
        if not user:
            return None
        
        # Get total submissions count
        total_submissions = await self._get_user_total_submissions(user.id)
        
        return UserProfile(
            telegram_id=user.telegram_id,
            username=user.username,
            first_name=user.first_name,
            created_at=user.created_at,
            is_pro=user.is_pro,
            daily_submissions=user.daily_submissions,
            last_submission_date=user.last_submission_date,
            total_submissions=total_submissions
        )
    
    async def update_user_info(self, telegram_id: int, username: Optional[str] = None,
                              first_name: Optional[str] = None) -> Optional[UserProfile]:
        """Update user information."""
        user = await self.user_repo.update_user_info(telegram_id, username, first_name)
        if not user:
            return None
        
        # Get total submissions count
        total_submissions = await self._get_user_total_submissions(user.id)
        
        return UserProfile(
            telegram_id=user.telegram_id,
            username=user.username,
            first_name=user.first_name,
            created_at=user.created_at,
            is_pro=user.is_pro,
            daily_submissions=user.daily_submissions,
            last_submission_date=user.last_submission_date,
            total_submissions=total_submissions
        )
    
    async def set_pro_status(self, telegram_id: int, is_pro: bool) -> Optional[UserProfile]:
        """
        Set user's pro status.
        
        Args:
            telegram_id: Telegram user ID
            is_pro: Pro status to set
            
        Returns:
            Updated UserProfile or None if user not found
        """
        user = await self.user_repo.set_pro_status(telegram_id, is_pro)
        if not user:
            return None
        
        # Get total submissions count
        total_submissions = await self._get_user_total_submissions(user.id)
        
        return UserProfile(
            telegram_id=user.telegram_id,
            username=user.username,
            first_name=user.first_name,
            created_at=user.created_at,
            is_pro=user.is_pro,
            daily_submissions=user.daily_submissions,
            last_submission_date=user.last_submission_date,
            total_submissions=total_submissions
        )
    
    async def is_pro_user(self, telegram_id: int) -> bool:
        """Check if user has pro status."""
        user = await self.user_repo.get_by_telegram_id(telegram_id)
        return user.is_pro if user else False
    
    async def get_user_stats(self, telegram_id: int, days: int = 30) -> Optional[UserStats]:
        """
        Get comprehensive user statistics.
        
        Args:
            telegram_id: Telegram user ID
            days: Number of days to analyze (default: 30)
            
        Returns:
            UserStats object or None if user not found
        """
        user = await self.user_repo.get_by_telegram_id(telegram_id)
        if not user:
            return None
        
        # Get rate limit history
        rate_limits = await self.rate_limit_repo.get_user_rate_limits(user.id, days)
        
        # Calculate statistics
        total_submissions = sum(rl.submission_count for rl in rate_limits)
        active_days = len([rl for rl in rate_limits if rl.submission_count > 0])
        avg_per_day = total_submissions / days if days > 0 else 0
        
        # Calculate streaks
        current_streak = await self._calculate_current_streak(user.id)
        longest_streak = await self._calculate_longest_streak(user.id, days)
        
        return UserStats(
            total_submissions=total_submissions,
            active_days=active_days,
            average_submissions_per_day=avg_per_day,
            current_streak=current_streak,
            longest_streak=longest_streak
        )
    
    async def get_all_pro_users(self) -> List[UserProfile]:
        """Get all users with pro status."""
        pro_users = await self.user_repo.get_pro_users()
        
        profiles = []
        for user in pro_users:
            total_submissions = await self._get_user_total_submissions(user.id)
            profiles.append(UserProfile(
                telegram_id=user.telegram_id,
                username=user.username,
                first_name=user.first_name,
                created_at=user.created_at,
                is_pro=user.is_pro,
                daily_submissions=user.daily_submissions,
                last_submission_date=user.last_submission_date,
                total_submissions=total_submissions
            ))
        
        return profiles
    
    async def get_active_users(self, days: int = 7) -> List[UserProfile]:
        """Get users who have been active in the last N days."""
        active_profiles = []
        
        # Get users who submitted in the last N days
        for i in range(days):
            target_date = date.today() - timedelta(days=i)
            users = await self.user_repo.get_users_by_submission_date(target_date)
            
            for user in users:
                # Avoid duplicates
                if not any(p.telegram_id == user.telegram_id for p in active_profiles):
                    total_submissions = await self._get_user_total_submissions(user.id)
                    active_profiles.append(UserProfile(
                        telegram_id=user.telegram_id,
                        username=user.username,
                        first_name=user.first_name,
                        created_at=user.created_at,
                        is_pro=user.is_pro,
                        daily_submissions=user.daily_submissions,
                        last_submission_date=user.last_submission_date,
                        total_submissions=total_submissions
                    ))
        
        return active_profiles
    
    async def reset_user_daily_submissions(self, telegram_id: int) -> bool:
        """Reset user's daily submission count."""
        user = await self.user_repo.reset_daily_submissions(telegram_id)
        return user is not None
    
    async def get_user_display_name(self, telegram_id: int) -> str:
        """Get user's display name (first_name or username or telegram_id)."""
        user = await self.user_repo.get_by_telegram_id(telegram_id)
        if not user:
            return f"User {telegram_id}"
        
        if user.first_name:
            return user.first_name
        elif user.username:
            return f"@{user.username}"
        else:
            return f"User {telegram_id}"
    
    async def delete_user(self, telegram_id: int) -> bool:
        """
        Delete user and all associated data.
        
        Args:
            telegram_id: Telegram user ID
            
        Returns:
            True if user was deleted, False if user not found
        """
        user = await self.user_repo.get_by_telegram_id(telegram_id)
        if not user:
            return False
        
        await self.user_repo.delete(user.id)
        return True
    
    async def get_user_summary(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Get a comprehensive user summary."""
        profile = await self.get_user_profile(telegram_id)
        if not profile:
            return None
        
        stats = await self.get_user_stats(telegram_id)
        current_daily_count = await self.user_repo.get_daily_submission_count(telegram_id)
        
        return {
            "profile": profile,
            "stats": stats,
            "current_daily_count": current_daily_count,
            "display_name": await self.get_user_display_name(telegram_id),
            "account_age_days": (datetime.now() - profile.created_at).days,
            "is_active_today": current_daily_count > 0
        }
    
    # Private helper methods
    
    async def _get_user_total_submissions(self, user_id: int) -> int:
        """Get total number of submissions for a user."""
        rate_limits = await self.rate_limit_repo.get_user_rate_limits(user_id, days=365)
        return sum(rl.submission_count for rl in rate_limits)
    
    async def _calculate_current_streak(self, user_id: int) -> int:
        """Calculate current consecutive days streak."""
        streak = 0
        current_date = date.today()
        
        # Check each day going backwards from today
        while True:
            daily_count = await self.rate_limit_repo.get_daily_count(user_id, current_date)
            if daily_count > 0:
                streak += 1
                current_date -= timedelta(days=1)
            else:
                break
        
        return streak
    
    async def _calculate_longest_streak(self, user_id: int, days: int = 30) -> int:
        """Calculate longest consecutive days streak in the given period."""
        rate_limits = await self.rate_limit_repo.get_user_rate_limits(user_id, days)
        
        if not rate_limits:
            return 0
        
        # Sort by date
        rate_limits.sort(key=lambda x: x.submission_date)
        
        longest_streak = 0
        current_streak = 0
        
        for i, rl in enumerate(rate_limits):
            if rl.submission_count > 0:
                # Check if this is consecutive to the previous day
                if i > 0:
                    prev_date = rate_limits[i-1].submission_date
                    expected_date = prev_date + timedelta(days=1)
                    if rl.submission_date == expected_date:
                        current_streak += 1
                    else:
                        current_streak = 1
                else:
                    current_streak = 1
                
                longest_streak = max(longest_streak, current_streak)
            else:
                current_streak = 0
        
        return longest_streak