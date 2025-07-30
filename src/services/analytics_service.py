"""
MongoDB Analytics Service for user interaction tracking.
"""
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import PyMongoError

from src.config.settings import settings

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Simple MongoDB service for tracking user analytics."""
    
    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[AsyncIOMotorDatabase] = None
        self._connected = False
    
    async def connect(self):
        """Connect to MongoDB."""
        try:
            self.client = AsyncIOMotorClient(settings.MONGODB_URL)
            self.db = self.client.get_default_database()
            
            # Test connection
            await self.client.admin.command('ping')
            self._connected = True
            logger.info("Connected to MongoDB successfully")
            
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            self._connected = False
    
    async def disconnect(self):
        """Disconnect from MongoDB."""
        if self.client:
            self.client.close()
            self._connected = False
            logger.info("Disconnected from MongoDB")
    
    async def track_user_action(self, user_id: int, action: str, data: Optional[Dict[str, Any]] = None):
        """Track user action for analytics."""
        if not self._connected:
            logger.warning("MongoDB not connected, skipping analytics")
            return
        
        try:
            document = {
                "user_id": user_id,
                "action": action,
                "timestamp": datetime.utcnow(),
                "data": data or {}
            }
            
            await self.db.user_actions.insert_one(document)
            logger.debug(f"Tracked action '{action}' for user {user_id}")
            
        except PyMongoError as e:
            logger.error(f"Failed to track user action: {e}")
    
    async def track_submission(self, user_id: int, task_type: str, word_count: int, score: Optional[float] = None):
        """Track IELTS submission for analytics."""
        if not self._connected:
            logger.warning("MongoDB not connected, skipping analytics")
            return
        
        try:
            document = {
                "user_id": user_id,
                "task_type": task_type,
                "word_count": word_count,
                "score": score,
                "timestamp": datetime.utcnow()
            }
            
            await self.db.submissions.insert_one(document)
            logger.debug(f"Tracked submission for user {user_id}: {task_type}")
            
        except PyMongoError as e:
            logger.error(f"Failed to track submission: {e}")
    
    async def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """Get basic user statistics."""
        if not self._connected:
            return {}
        
        try:
            # Count total submissions
            total_submissions = await self.db.submissions.count_documents({"user_id": user_id})
            
            # Count by task type
            task1_count = await self.db.submissions.count_documents({"user_id": user_id, "task_type": "TASK_1"})
            task2_count = await self.db.submissions.count_documents({"user_id": user_id, "task_type": "TASK_2"})
            
            # Get average score
            pipeline = [
                {"$match": {"user_id": user_id, "score": {"$ne": None}}},
                {"$group": {"_id": None, "avg_score": {"$avg": "$score"}}}
            ]
            avg_result = await self.db.submissions.aggregate(pipeline).to_list(1)
            avg_score = avg_result[0]["avg_score"] if avg_result else None
            
            return {
                "total_submissions": total_submissions,
                "task1_submissions": task1_count,
                "task2_submissions": task2_count,
                "average_score": round(avg_score, 1) if avg_score else None
            }
            
        except PyMongoError as e:
            logger.error(f"Failed to get user stats: {e}")
            return {}


# Global analytics service instance
analytics_service = AnalyticsService()