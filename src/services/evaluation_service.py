"""
Evaluation Service Orchestrator for IELTS Writing Assessment

This module coordinates the complete evaluation workflow including text validation,
task type detection, AI assessment, and result formatting.
"""

import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from datetime import datetime

from src.models.submission import TaskType, ProcessingStatus
from src.services.text_processor import TextValidator, TaskTypeDetector, ValidationResult, TaskDetectionResult
from src.services.ai_assessment_engine import AIAssessmentEngine, StructuredAssessment, RawAssessment
from src.repositories.user_repository import UserRepository
from src.repositories.submission_repository import SubmissionRepository
from src.repositories.assessment_repository import AssessmentRepository
from src.repositories.rate_limit_repository import RateLimitRepository
from src.exceptions import DatabaseError, AIServiceError, ValidationError, RateLimitError

logger = logging.getLogger(__name__)


@dataclass
class EvaluationRequest:
    """Request for writing evaluation"""
    user_id: int
    text: str
    task_type: Optional[TaskType] = None
    force_task_type: bool = False


@dataclass
class EvaluationResult:
    """Complete evaluation result"""
    success: bool
    submission_id: Optional[int] = None
    assessment: Optional[StructuredAssessment] = None
    validation_result: Optional[ValidationResult] = None
    task_detection_result: Optional[TaskDetectionResult] = None
    error_message: Optional[str] = None
    requires_task_clarification: bool = False


@dataclass
class RateLimitStatus:
    """Rate limiting status for a user"""
    is_allowed: bool
    daily_count: int
    daily_limit: int
    reset_time: Optional[datetime] = None
    message: Optional[str] = None


class EvaluationService:
    """
    Main orchestrator for the IELTS writing evaluation workflow
    """
    
    def __init__(
        self,
        ai_engine: AIAssessmentEngine,
        user_repo: UserRepository,
        submission_repo: SubmissionRepository,
        assessment_repo: AssessmentRepository,
        rate_limit_repo: RateLimitRepository
    ):
        self.ai_engine = ai_engine
        self.user_repo = user_repo
        self.submission_repo = submission_repo
        self.assessment_repo = assessment_repo
        self.rate_limit_repo = rate_limit_repo
        
        self.text_validator = TextValidator()
        self.task_detector = TaskTypeDetector()
        
        # Configuration
        self.free_user_daily_limit = 3
        self.pro_user_daily_limit = 50  # Effectively unlimited for pro users
    
    async def check_rate_limit(self, user_id: int) -> RateLimitStatus:
        """
        Check if user can make a submission based on rate limits
        
        Args:
            user_id: The user's ID
            
        Returns:
            RateLimitStatus indicating if submission is allowed
            
        Raises:
            DatabaseError: If database operations fail
        """
        try:
            # Get user to check pro status
            user = await self.user_repo.get_by_id(user_id)
            if not user:
                raise DatabaseError(
                    f"User {user_id} not found in database",
                    operation="get_user",
                    table="users"
                )
            
            # Determine daily limit based on user status
            daily_limit = self.pro_user_daily_limit if user.is_pro else self.free_user_daily_limit
            
            # Get current daily submission count
            daily_count = await self.rate_limit_repo.get_daily_submission_count(user_id)
            
            if daily_count >= daily_limit:
                message = "Daily submission limit reached."
                if not user.is_pro:
                    message += " Upgrade to Pro for unlimited evaluations!"
                
                raise RateLimitError(
                    message=message,
                    limit_type="daily_submissions",
                    current_count=daily_count,
                    limit=daily_limit,
                    reset_time="tomorrow at midnight"
                )
            
            return RateLimitStatus(
                is_allowed=True,
                daily_count=daily_count,
                daily_limit=daily_limit
            )
            
        except (RateLimitError, DatabaseError):
            # Re-raise known exceptions
            raise
        except Exception as e:
            logger.error(f"Unexpected error checking rate limit for user {user_id}: {e}")
            raise DatabaseError(
                f"Failed to check rate limits: {str(e)}",
                operation="check_rate_limit",
                recoverable=True
            )
    
    async def detect_task_type(self, text: str) -> TaskDetectionResult:
        """
        Detect task type from text content
        
        Args:
            text: The writing text to analyze
            
        Returns:
            TaskDetectionResult with detection outcome
        """
        return self.task_detector.detect_task_type(text)
    
    async def validate_submission(self, text: str) -> ValidationResult:
        """
        Validate text submission
        
        Args:
            text: The text to validate
            
        Returns:
            ValidationResult with validation outcome
        """
        return self.text_validator.validate_submission(text)
    
    async def evaluate_writing(self, request: EvaluationRequest) -> EvaluationResult:
        """
        Complete writing evaluation workflow with comprehensive error handling
        
        Args:
            request: EvaluationRequest with submission details
            
        Returns:
            EvaluationResult with complete evaluation outcome
        """
        submission_id = None
        
        try:
            # Step 1: Check rate limits
            try:
                rate_limit_status = await self.check_rate_limit(request.user_id)
            except RateLimitError as e:
                return EvaluationResult(
                    success=False,
                    error_message=e.user_message
                )
            except DatabaseError as e:
                # Allow evaluation to continue with warning if rate limit check fails
                logger.warning(f"Rate limit check failed, allowing evaluation: {e}")
                rate_limit_status = RateLimitStatus(
                    is_allowed=True,
                    daily_count=0,
                    daily_limit=self.free_user_daily_limit
                )
            
            # Step 2: Validate text
            try:
                validation_result = await self.validate_submission(request.text)
                if not validation_result.is_valid:
                    # Convert validation errors to ValidationError exceptions
                    error_messages = self._format_validation_errors(validation_result)
                    suggestions = self._get_validation_suggestions(validation_result)
                    
                    raise ValidationError(
                        message=error_messages,
                        validation_type="text_submission",
                        user_message=error_messages,
                        suggestions=suggestions
                    )
            except ValidationError:
                raise  # Re-raise validation errors
            except Exception as e:
                logger.error(f"Text validation failed: {e}")
                raise ValidationError(
                    message=f"Text validation failed: {str(e)}",
                    validation_type="text_processing",
                    user_message="Unable to process your text. Please try again."
                )
            
            # Step 3: Determine task type
            task_type = request.task_type
            task_detection_result = None
            
            if not task_type or not request.force_task_type:
                try:
                    task_detection_result = await self.detect_task_type(request.text)
                    
                    if not request.force_task_type:
                        if task_detection_result.requires_clarification:
                            return EvaluationResult(
                                success=False,
                                validation_result=validation_result,
                                task_detection_result=task_detection_result,
                                requires_task_clarification=True,
                                error_message="Unable to determine task type. Please specify Task 1 or Task 2."
                            )
                        task_type = task_detection_result.detected_type
                    
                    if not task_type:
                        raise ValidationError(
                            message="Could not determine task type from content",
                            validation_type="task_detection",
                            user_message="Please specify whether this is Task 1 or Task 2.",
                            suggestions=["Use the task selection buttons", "Include clear task indicators in your text"]
                        )
                except ValidationError:
                    raise
                except Exception as e:
                    logger.error(f"Task type detection failed: {e}")
                    # Continue with user-specified task type if available
                    if not request.task_type:
                        raise ValidationError(
                            message=f"Task detection failed: {str(e)}",
                            validation_type="task_detection",
                            user_message="Unable to determine task type. Please specify Task 1 or Task 2."
                        )
            
            # Step 4: Create submission record
            try:
                submission = await self.submission_repo.create(
                    user_id=request.user_id,
                    text=request.text,
                    task_type=task_type,
                    word_count=validation_result.word_count
                )
                submission_id = submission.id
            except Exception as e:
                logger.error(f"Failed to create submission record: {e}")
                raise DatabaseError(
                    f"Failed to save submission: {str(e)}",
                    operation="create_submission",
                    table="submissions",
                    recoverable=True
                )
            
            # Step 5: Update rate limit counter (with fallback)
            try:
                await self.rate_limit_repo.increment_daily_count(request.user_id)
            except Exception as e:
                logger.warning(f"Failed to update rate limit counter: {e}")
                # Continue evaluation even if rate limit update fails
            
            # Step 6: Get AI assessment
            try:
                raw_assessment = await self.ai_engine.assess_writing(request.text, task_type)
                structured_assessment = self.ai_engine.parse_response(raw_assessment.content)
                
                # Step 7: Validate assessment scores
                if not self.ai_engine.validate_scores(structured_assessment):
                    logger.warning(f"Invalid scores detected for submission {submission.id}")
                    # Continue with potentially invalid scores rather than failing completely
                
            except AIServiceError:
                # Mark submission as failed and re-raise
                if submission_id:
                    try:
                        await self.submission_repo.update_status(submission_id, ProcessingStatus.FAILED)
                    except Exception as db_error:
                        logger.error(f"Failed to update submission status: {db_error}")
                raise
            except Exception as e:
                # Mark submission as failed
                if submission_id:
                    try:
                        await self.submission_repo.update_status(submission_id, ProcessingStatus.FAILED)
                    except Exception as db_error:
                        logger.error(f"Failed to update submission status: {db_error}")
                
                logger.error(f"AI assessment failed for submission {submission_id}: {e}")
                raise AIServiceError(
                    f"Assessment processing failed: {str(e)}",
                    service_type="evaluation",
                    error_type="processing_error",
                    recoverable=True
                )
            
            # Step 8: Save assessment
            try:
                assessment_record = await self.assessment_repo.create(
                    submission_id=submission.id,
                    task_achievement_score=structured_assessment.task_achievement_score,
                    coherence_cohesion_score=structured_assessment.coherence_cohesion_score,
                    lexical_resource_score=structured_assessment.lexical_resource_score,
                    grammatical_accuracy_score=structured_assessment.grammatical_accuracy_score,
                    overall_band_score=structured_assessment.overall_band_score,
                    detailed_feedback=structured_assessment.detailed_feedback,
                    improvement_suggestions=structured_assessment.improvement_suggestions,
                    score_justifications=structured_assessment.score_justifications
                )
            except Exception as e:
                logger.error(f"Failed to save assessment: {e}")
                # Continue with evaluation result even if saving fails
                logger.warning("Assessment completed but could not be saved to history")
            
            # Step 9: Update submission status
            try:
                await self.submission_repo.update_status(submission.id, ProcessingStatus.COMPLETED)
            except Exception as e:
                logger.warning(f"Failed to update submission status to completed: {e}")
                # Don't fail the evaluation for this
            
            return EvaluationResult(
                success=True,
                submission_id=submission.id,
                assessment=structured_assessment,
                validation_result=validation_result,
                task_detection_result=task_detection_result
            )
            
        except (ValidationError, RateLimitError, AIServiceError, DatabaseError):
            # Re-raise known exceptions to be handled by error handler
            raise
        except Exception as e:
            logger.error(f"Unexpected error in evaluation workflow for user {request.user_id}: {e}")
            
            # Mark submission as failed if it was created
            if submission_id:
                try:
                    await self.submission_repo.update_status(submission_id, ProcessingStatus.FAILED)
                except Exception as db_error:
                    logger.error(f"Failed to update submission status after error: {db_error}")
            
            raise AIServiceError(
                f"Evaluation workflow failed: {str(e)}",
                service_type="evaluation",
                error_type="workflow_error",
                recoverable=True
            )
    
    def _format_validation_errors(self, validation_result: ValidationResult) -> str:
        """Format validation errors into user-friendly message"""
        if not validation_result.errors:
            return "Text validation failed"
        
        messages = []
        
        for error in validation_result.errors:
            if error.value == "empty_text":
                messages.append("Please provide some text to evaluate.")
            elif error.value == "too_short":
                messages.append(f"Text is too short ({validation_result.word_count} words). Please provide at least 50 words.")
            elif error.value == "too_long":
                messages.append(f"Text is very long ({validation_result.word_count} words). Consider typical IELTS limits.")
            elif error.value == "not_english":
                messages.append("Please submit your writing in English for IELTS evaluation.")
            elif error.value == "invalid_content":
                messages.append("Text quality issues detected. Please check your submission.")
        
        # Add warnings if any
        if validation_result.warnings:
            messages.extend(validation_result.warnings)
        
        return " ".join(messages)
    
    def _get_validation_suggestions(self, validation_result: ValidationResult) -> List[str]:
        """Get helpful suggestions based on validation errors"""
        suggestions = []
        
        if not validation_result.errors:
            return suggestions
        
        for error in validation_result.errors:
            if error.value == "empty_text":
                suggestions.append("Please provide your IELTS writing text")
            elif error.value == "too_short":
                suggestions.append("Write at least 50 words for meaningful evaluation")
                suggestions.append("Task 1: Aim for 150+ words, Task 2: Aim for 250+ words")
            elif error.value == "too_long":
                suggestions.append("Consider staying within IELTS word limits for practice")
            elif error.value == "not_english":
                suggestions.append("Submit your writing in English for IELTS evaluation")
            elif error.value == "invalid_content":
                suggestions.append("Check for proper sentence structure and grammar")
                suggestions.append("Ensure your text is readable and well-formatted")
        
        return suggestions
    
    async def get_user_evaluation_history(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get user's evaluation history
        
        Args:
            user_id: The user's ID
            limit: Maximum number of records to return
            
        Returns:
            List of evaluation history records
        """
        try:
            history = await self.assessment_repo.get_user_assessments(user_id, limit)
            return [
                {
                    'submission_id': record.submission_id,
                    'task_type': record.submission.task_type.value,
                    'overall_band_score': record.overall_band_score,
                    'submitted_at': record.submission.submitted_at,
                    'word_count': record.submission.word_count
                }
                for record in history
            ]
        except Exception as e:
            logger.error(f"Error getting history for user {user_id}: {e}")
            # Don't raise exception for history retrieval failures
            return []