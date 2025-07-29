"""
Service monitoring and health checking for IELTS Telegram Bot
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Optional, List, Callable, Awaitable
import aiohttp

from src.exceptions import DatabaseError, AIServiceError, ConfigurationError

logger = logging.getLogger(__name__)


class ServiceStatus(Enum):
    """Service status levels"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ServiceHealth:
    """Health status of a service"""
    name: str
    status: ServiceStatus
    last_check: datetime
    response_time: Optional[float] = None
    error_message: Optional[str] = None
    consecutive_failures: int = 0


@dataclass
class FallbackResponse:
    """Fallback response when services are unavailable"""
    message: str
    can_retry: bool = True
    estimated_recovery_time: Optional[str] = None
    alternative_actions: Optional[List[str]] = None


class ServiceMonitor:
    """
    Monitor service health and provide fallback responses
    """
    
    def __init__(self):
        self.services: Dict[str, ServiceHealth] = {}
        self.check_interval = 300  # 5 minutes
        self.failure_threshold = 3
        self.recovery_threshold = 2
        self.monitoring_task: Optional[asyncio.Task] = None
        
        # Initialize service health tracking
        self._initialize_services()
    
    def _initialize_services(self):
        """Initialize service health tracking"""
        services = [
            "openai_api",
            "database",
            "telegram_api",
            "text_processor"
        ]
        
        for service in services:
            self.services[service] = ServiceHealth(
                name=service,
                status=ServiceStatus.UNKNOWN,
                last_check=datetime.now(),
                consecutive_failures=0
            )
    
    async def start_monitoring(self):
        """Start background service monitoring"""
        if self.monitoring_task and not self.monitoring_task.done():
            return
        
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Service monitoring started")
    
    async def stop_monitoring(self):
        """Stop background service monitoring"""
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        logger.info("Service monitoring stopped")
    
    async def _monitoring_loop(self):
        """Background monitoring loop"""
        while True:
            try:
                await self.check_all_services()
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying
    
    async def check_all_services(self):
        """Check health of all services"""
        tasks = []
        for service_name in self.services.keys():
            task = asyncio.create_task(self._check_service_health(service_name))
            tasks.append(task)
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _check_service_health(self, service_name: str):
        """Check health of a specific service"""
        start_time = datetime.now()
        
        try:
            if service_name == "openai_api":
                await self._check_openai_health()
            elif service_name == "database":
                await self._check_database_health()
            elif service_name == "telegram_api":
                await self._check_telegram_health()
            elif service_name == "text_processor":
                await self._check_text_processor_health()
            
            # Service is healthy
            response_time = (datetime.now() - start_time).total_seconds()
            self._update_service_status(
                service_name, ServiceStatus.HEALTHY, 
                response_time=response_time
            )
            
        except Exception as e:
            logger.warning(f"Health check failed for {service_name}: {e}")
            self._update_service_status(
                service_name, ServiceStatus.UNHEALTHY,
                error_message=str(e)
            )
    
    async def _check_openai_health(self):
        """Check OpenAI API health"""
        # Simple health check - could be enhanced with actual API call
        import openai
        from src.config.settings import get_settings
        
        settings = get_settings()
        if not settings.OPENAI_API_KEY:
            raise ConfigurationError("OpenAI API key not configured", "OPENAI_API_KEY")
        
        # Could add actual API health check here
        # For now, just verify configuration
        pass
    
    async def _check_database_health(self):
        """Check database health"""
        # Simple connection test
        from src.database.base import get_session
        
        async with get_session() as session:
            # Simple query to test connection
            result = await session.execute("SELECT 1")
            if not result:
                raise DatabaseError("Database query failed", "health_check")
    
    async def _check_telegram_health(self):
        """Check Telegram API health"""
        # Check if we can reach Telegram API
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.telegram.org/bot/getMe",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status != 200:
                    raise Exception(f"Telegram API returned status {response.status}")
    
    async def _check_text_processor_health(self):
        """Check text processor health"""
        # Simple test of text processing functionality
        from src.services.text_processor import TextValidator
        
        validator = TextValidator()
        test_result = validator.validate_submission("This is a test text for health check.")
        
        if not hasattr(test_result, 'is_valid'):
            raise Exception("Text processor validation failed")
    
    def _update_service_status(
        self, 
        service_name: str, 
        status: ServiceStatus,
        response_time: Optional[float] = None,
        error_message: Optional[str] = None
    ):
        """Update service status"""
        service = self.services[service_name]
        previous_status = service.status
        
        service.last_check = datetime.now()
        service.response_time = response_time
        service.error_message = error_message
        
        if status == ServiceStatus.HEALTHY:
            service.consecutive_failures = 0
            service.status = ServiceStatus.HEALTHY
        else:
            service.consecutive_failures += 1
            
            if service.consecutive_failures >= self.failure_threshold:
                service.status = ServiceStatus.UNHEALTHY
            elif service.consecutive_failures > 1:
                service.status = ServiceStatus.DEGRADED
            else:
                service.status = status  # Use the provided status for first failure
        
        # Log status changes
        if previous_status != service.status:
            logger.info(f"Service {service_name} status changed: {previous_status.value} -> {service.status.value}")
    
    def get_service_status(self, service_name: str) -> ServiceHealth:
        """Get current status of a service"""
        return self.services.get(service_name, ServiceHealth(
            name=service_name,
            status=ServiceStatus.UNKNOWN,
            last_check=datetime.now()
        ))
    
    def get_overall_health(self) -> ServiceStatus:
        """Get overall system health"""
        unhealthy_count = sum(1 for s in self.services.values() if s.status == ServiceStatus.UNHEALTHY)
        degraded_count = sum(1 for s in self.services.values() if s.status == ServiceStatus.DEGRADED)
        
        if unhealthy_count > 0:
            return ServiceStatus.UNHEALTHY
        elif degraded_count > 0:
            return ServiceStatus.DEGRADED
        else:
            return ServiceStatus.HEALTHY
    
    def get_fallback_response(self, service_name: str) -> FallbackResponse:
        """Get fallback response for unavailable service"""
        service = self.get_service_status(service_name)
        
        if service_name == "openai_api":
            return self._get_ai_fallback_response(service)
        elif service_name == "database":
            return self._get_database_fallback_response(service)
        elif service_name == "telegram_api":
            return self._get_telegram_fallback_response(service)
        else:
            return FallbackResponse(
                message="Service temporarily unavailable. Please try again later.",
                can_retry=True,
                estimated_recovery_time="a few minutes"
            )
    
    def _get_ai_fallback_response(self, service: ServiceHealth) -> FallbackResponse:
        """Get fallback response for AI service issues"""
        if service.consecutive_failures >= self.failure_threshold:
            return FallbackResponse(
                message=(
                    "🤖 AI assessment service is temporarily unavailable.\n\n"
                    "This might be due to high demand or maintenance. "
                    "Please try again in a few minutes."
                ),
                can_retry=True,
                estimated_recovery_time="5-10 minutes",
                alternative_actions=[
                    "Check your submission history",
                    "Try submitting a shorter text",
                    "Contact support if the issue persists"
                ]
            )
        else:
            return FallbackResponse(
                message=(
                    "🤖 AI assessment is experiencing some delays.\n\n"
                    "Your request might take longer than usual to process."
                ),
                can_retry=True,
                estimated_recovery_time="1-2 minutes"
            )
    
    def _get_database_fallback_response(self, service: ServiceHealth) -> FallbackResponse:
        """Get fallback response for database issues"""
        return FallbackResponse(
            message=(
                "💾 Database temporarily unavailable.\n\n"
                "Your evaluation can still proceed, but history tracking "
                "may be limited until service is restored."
            ),
            can_retry=True,
            estimated_recovery_time="a few minutes",
            alternative_actions=[
                "Continue with evaluation (history may not be saved)",
                "Try again later for full functionality"
            ]
        )
    
    def _get_telegram_fallback_response(self, service: ServiceHealth) -> FallbackResponse:
        """Get fallback response for Telegram API issues"""
        return FallbackResponse(
            message=(
                "📱 Telegram service experiencing connectivity issues.\n\n"
                "Some features may be limited until connection is restored."
            ),
            can_retry=True,
            estimated_recovery_time="1-5 minutes"
        )
    
    def is_service_available(self, service_name: str) -> bool:
        """Check if service is available for use"""
        service = self.get_service_status(service_name)
        return service.status in [ServiceStatus.HEALTHY, ServiceStatus.DEGRADED]
    
    def get_health_summary(self) -> Dict[str, any]:
        """Get summary of all service health"""
        return {
            "overall_status": self.get_overall_health().value,
            "services": {
                name: {
                    "status": service.status.value,
                    "last_check": service.last_check.isoformat(),
                    "response_time": service.response_time,
                    "consecutive_failures": service.consecutive_failures,
                    "error_message": service.error_message
                }
                for name, service in self.services.items()
            },
            "timestamp": datetime.now().isoformat()
        }


# Global service monitor instance
service_monitor = ServiceMonitor()