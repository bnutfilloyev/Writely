"""
User repository for user management operations.
"""
from typing import Optional, List
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from src.models.user import User
from src.repositories.base_repository import BaseRepository


class UserRepository(BaseRepository[User]):
    """
    Repository for User model operations.
    """
    
    def __init__(self, session: AsyncSession):
        super().__init__(User, session)

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Get user by Telegram ID."""
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def create_user(self, telegram_id: int, username: Optional[str] = None, 
                         first_name: Optional[str] = None) -> User:
        """Create a new user."""
        return await self.create(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name
        )

    async def get_or_create_user(self, telegram_id: int, username: Optional[str] = None,
                                first_name: Optional[str] = None) -> User:
        """Get existing user or create new one."""
        user = await self.get_by_telegram_id(telegram_id)
        if user:
            # Update username and first_name if provided
            if username and user.username != username:
                user.username = username
            if first_name and user.first_name != first_name:
                user.first_name = first_name
            await self.session.commit()
            return user
        
        return await self.create_user(telegram_id, username, first_name)

    async def update_user_info(self, telegram_id: int, username: Optional[str] = None,
                              first_name: Optional[str] = None) -> Optional[User]:
        """Update user information."""
        user = await self.get_by_telegram_id(telegram_id)
        if not user:
            return None
        
        update_data = {}
        if username is not None:
            update_data['username'] = username
        if first_name is not None:
            update_data['first_name'] = first_name
        
        if update_data:
            await self.session.execute(
                update(User).where(User.telegram_id == telegram_id).values(**update_data)
            )
            await self.session.commit()
            await self.session.refresh(user)
        
        return user

    async def set_pro_status(self, telegram_id: int, is_pro: bool) -> Optional[User]:
        """Set user's pro status."""
        user = await self.get_by_telegram_id(telegram_id)
        if not user:
            return None
        
        user.is_pro = is_pro
        await self.session.commit()
        return user

    async def reset_daily_submissions(self, telegram_id: int) -> Optional[User]:
        """Reset user's daily submission count."""
        user = await self.get_by_telegram_id(telegram_id)
        if not user:
            return None
        
        user.reset_daily_submissions()
        await self.session.commit()
        return user

    async def increment_daily_submissions(self, telegram_id: int) -> Optional[User]:
        """Increment user's daily submission count."""
        user = await self.get_by_telegram_id(telegram_id)
        if not user:
            return None
        
        user.increment_daily_submissions()
        await self.session.commit()
        return user

    async def get_users_with_submissions(self, limit: Optional[int] = None) -> List[User]:
        """Get users with their submissions loaded."""
        query = select(User).options(selectinload(User.submissions))
        if limit:
            query = query.limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_pro_users(self) -> List[User]:
        """Get all pro users."""
        result = await self.session.execute(
            select(User).where(User.is_pro == True)
        )
        return result.scalars().all()

    async def get_users_by_submission_date(self, submission_date: date) -> List[User]:
        """Get users who submitted on a specific date."""
        result = await self.session.execute(
            select(User).where(User.last_submission_date == submission_date)
        )
        return result.scalars().all()

    async def get_daily_submission_count(self, telegram_id: int) -> int:
        """Get user's current daily submission count."""
        user = await self.get_by_telegram_id(telegram_id)
        if not user:
            return 0
        
        # Check if last submission was today
        today = date.today()
        if user.last_submission_date != today:
            return 0
        
        return user.daily_submissions