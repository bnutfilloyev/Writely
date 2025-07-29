"""
AI Assessment Engine for IELTS Writing Evaluation

This module provides the core AI-powered assessment functionality for evaluating
IELTS writing tasks using OpenAI's GPT-4 API.
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Any
import openai
from openai import AsyncOpenAI

from src.exceptions import AIServiceError, ConfigurationError

logger = logging.getLogger(__name__)


class TaskType(Enum):
    TASK_1 = "task_1"
    TASK_2 = "task_2"


@dataclass
class StructuredAssessment:
    """Structured assessment result from AI evaluation"""
    task_achievement_score: float
    coherence_cohesion_score: float
    lexical_resource_score: float
    grammatical_accuracy_score: float
    overall_band_score: float
    detailed_feedback: str
    improvement_suggestions: List[str]
    score_justifications: Dict[str, str]


@dataclass
class RawAssessment:
    """Raw assessment response from OpenAI API"""
    content: str
    usage_tokens: int
    model_used: str


class AIAssessmentEngine:
    """
    Main AI assessment engine that interfaces with OpenRouter API
    for IELTS writing evaluation using various AI models
    """
    
    def __init__(self, api_key: str, model: str = "openai/gpt-4o", base_url: str = "https://openrouter.ai/api/v1", site_url: str = "https://ielts-telegram-bot.local", site_name: str = "IELTS Writing Bot"):
        if not api_key:
            raise ConfigurationError("OpenRouter API key is required", "OPENAI_API_KEY")
        
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url
        )
        self.model = model
        self.site_url = site_url
        self.site_name = site_name
        self.max_retries = 3
        self.retry_delay = 1.0
        self.circuit_breaker_failures = 0
        self.circuit_breaker_threshold = 5
        self.circuit_breaker_reset_time = None
        
    async def assess_writing(self, text: str, task_type: TaskType) -> RawAssessment:
        """
        Assess writing using OpenAI API with comprehensive error handling
        
        Args:
            text: The writing text to evaluate
            task_type: Whether it's Task 1 or Task 2
            
        Returns:
            RawAssessment containing the API response
            
        Raises:
            AIServiceError: For various AI service related errors
        """
        # Check circuit breaker
        if self._is_circuit_breaker_open():
            raise AIServiceError(
                "AI service temporarily disabled due to repeated failures",
                service_type="openai",
                error_type="circuit_breaker",
                retry_after=300,  # 5 minutes
                recoverable=True
            )
        
        prompt = self.build_prompt(text, task_type)
        last_exception = None
        
        for attempt in range(self.max_retries):
            try:
                response = await asyncio.wait_for(
                    self.client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {
                                "role": "system",
                                "content": "You are an expert IELTS examiner with years of experience evaluating writing tasks according to official IELTS band descriptors."
                            },
                            {
                                "role": "user", 
                                "content": prompt
                            }
                        ],
                        temperature=0.3,
                        max_tokens=1500,
                        extra_headers={
                            "HTTP-Referer": self.site_url,
                            "X-Title": self.site_name,
                        }
                    ),
                    timeout=30.0  # 30 second timeout
                )
                
                # Reset circuit breaker on success
                self.circuit_breaker_failures = 0
                self.circuit_breaker_reset_time = None
                
                return RawAssessment(
                    content=response.choices[0].message.content,
                    usage_tokens=response.usage.total_tokens,
                    model_used=response.model
                )
                
            except asyncio.TimeoutError as e:
                last_exception = e
                logger.warning(f"Request timeout on attempt {attempt + 1}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))
                else:
                    self._increment_circuit_breaker()
                    raise AIServiceError(
                        "Request timed out after all retries",
                        service_type="openai",
                        error_type="timeout",
                        retry_after=60,
                        recoverable=True
                    )
                    
            except openai.RateLimitError as e:
                last_exception = e
                logger.warning(f"Rate limit hit on attempt {attempt + 1}: {e}")
                
                # Extract retry-after from headers if available
                retry_after = getattr(e, 'retry_after', None) or 60
                
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(min(retry_after, self.retry_delay * (2 ** attempt)))
                else:
                    raise AIServiceError(
                        "Rate limit exceeded after all retries",
                        service_type="openai",
                        error_type="rate_limit",
                        retry_after=retry_after,
                        recoverable=True
                    )
                    
            except openai.AuthenticationError as e:
                last_exception = e
                logger.error(f"Authentication error: {e}")
                self._increment_circuit_breaker()
                raise AIServiceError(
                    "Authentication failed with AI service",
                    service_type="openai",
                    error_type="auth",
                    recoverable=False
                )
                
            except openai.PermissionDeniedError as e:
                last_exception = e
                logger.error(f"Permission denied: {e}")
                self._increment_circuit_breaker()
                raise AIServiceError(
                    "Permission denied by AI service",
                    service_type="openai",
                    error_type="permission",
                    recoverable=False
                )
                
            except openai.BadRequestError as e:
                last_exception = e
                logger.error(f"Bad request error: {e}")
                # Don't retry bad requests
                raise AIServiceError(
                    "Invalid request to AI service",
                    service_type="openai",
                    error_type="bad_request",
                    recoverable=False
                )
                
            except openai.APIConnectionError as e:
                last_exception = e
                logger.warning(f"Connection error on attempt {attempt + 1}: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))
                else:
                    self._increment_circuit_breaker()
                    raise AIServiceError(
                        "Connection to AI service failed",
                        service_type="openai",
                        error_type="connection",
                        retry_after=120,
                        recoverable=True
                    )
                    
            except openai.APIError as e:
                last_exception = e
                logger.error(f"OpenAI API error on attempt {attempt + 1}: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))
                else:
                    self._increment_circuit_breaker()
                    raise AIServiceError(
                        f"AI service error: {str(e)}",
                        service_type="openai",
                        error_type="api_error",
                        retry_after=180,
                        recoverable=True
                    )
                    
            except Exception as e:
                last_exception = e
                logger.error(f"Unexpected error on attempt {attempt + 1}: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))
                else:
                    self._increment_circuit_breaker()
                    raise AIServiceError(
                        f"Unexpected error in AI service: {str(e)}",
                        service_type="openai",
                        error_type="unknown",
                        retry_after=300,
                        recoverable=True
                    )
    
    def build_prompt(self, text: str, task_type: TaskType) -> str:
        """
        Build task-specific evaluation prompt
        
        Args:
            text: The writing text to evaluate
            task_type: Whether it's Task 1 or Task 2
            
        Returns:
            Formatted prompt string for the AI model
        """
        if task_type == TaskType.TASK_1:
            return self._build_task1_prompt(text)
        else:
            return self._build_task2_prompt(text)
    
    def _build_task1_prompt(self, text: str) -> str:
        """Build Task 1 specific evaluation prompt"""
        return f"""
Please evaluate this IELTS Writing Task 1 response according to the official IELTS band descriptors. 

TEXT TO EVALUATE:
{text}

Provide your assessment in the following JSON format:
{{
    "task_achievement_score": 0.0,
    "coherence_cohesion_score": 0.0,
    "lexical_resource_score": 0.0,
    "grammatical_accuracy_score": 0.0,
    "overall_band_score": 0.0,
    "detailed_feedback": "Overall assessment of the writing...",
    "improvement_suggestions": [
        "Specific suggestion 1",
        "Specific suggestion 2",
        "Specific suggestion 3"
    ],
    "score_justifications": {{
        "task_achievement": "Justification for Task Achievement score...",
        "coherence_cohesion": "Justification for Coherence and Cohesion score...",
        "lexical_resource": "Justification for Lexical Resource score...",
        "grammatical_accuracy": "Justification for Grammatical Range and Accuracy score..."
    }}
}}

TASK 1 EVALUATION CRITERIA:
- Task Achievement: How well does the response address the task requirements? Does it present a clear overview of main trends, differences or stages? Are key features appropriately selected and reported?
- Coherence and Cohesion: Is the information organized logically? Are cohesive devices used appropriately?
- Lexical Resource: Is there a range of vocabulary? Is vocabulary used accurately and appropriately?
- Grammatical Range and Accuracy: Is there a variety of sentence structures? Are they used accurately?

Scores should be between 0.0 and 9.0 in 0.5 increments. The overall band score should be the average of the four criteria scores, rounded to the nearest 0.5.
"""

    def _build_task2_prompt(self, text: str) -> str:
        """Build Task 2 specific evaluation prompt"""
        return f"""
Please evaluate this IELTS Writing Task 2 response according to the official IELTS band descriptors.

TEXT TO EVALUATE:
{text}

Provide your assessment in the following JSON format:
{{
    "task_achievement_score": 0.0,
    "coherence_cohesion_score": 0.0,
    "lexical_resource_score": 0.0,
    "grammatical_accuracy_score": 0.0,
    "overall_band_score": 0.0,
    "detailed_feedback": "Overall assessment of the writing...",
    "improvement_suggestions": [
        "Specific suggestion 1",
        "Specific suggestion 2",
        "Specific suggestion 3"
    ],
    "score_justifications": {{
        "task_achievement": "Justification for Task Response score...",
        "coherence_cohesion": "Justification for Coherence and Cohesion score...",
        "lexical_resource": "Justification for Lexical Resource score...",
        "grammatical_accuracy": "Justification for Grammatical Range and Accuracy score..."
    }}
}}

TASK 2 EVALUATION CRITERIA:
- Task Response: How well does the response address all parts of the task? Is there a clear position throughout? Are ideas developed with relevant examples?
- Coherence and Cohesion: Is the information organized logically with clear progression? Are cohesive devices used effectively?
- Lexical Resource: Is there a wide range of vocabulary used naturally and flexibly? Are there attempts at less common vocabulary?
- Grammatical Range and Accuracy: Is there a wide range of structures used accurately? Are complex sentences attempted?

Scores should be between 0.0 and 9.0 in 0.5 increments. The overall band score should be the average of the four criteria scores, rounded to the nearest 0.5.
"""

    def parse_response(self, response: str) -> StructuredAssessment:
        """
        Parse AI response into structured assessment data
        
        Args:
            response: Raw response string from OpenAI
            
        Returns:
            StructuredAssessment object
            
        Raises:
            ValueError: If response cannot be parsed or is invalid
        """
        try:
            # Extract JSON from response if it's wrapped in other text
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start == -1 or json_end == 0:
                raise AIServiceError(
                    "No JSON found in AI response",
                    service_type="openai",
                    error_type="parse_error",
                    recoverable=True
                )
                
            json_str = response[json_start:json_end]
            data = json.loads(json_str)
            
            # Validate required fields
            required_fields = [
                'task_achievement_score', 'coherence_cohesion_score',
                'lexical_resource_score', 'grammatical_accuracy_score',
                'overall_band_score', 'detailed_feedback',
                'improvement_suggestions', 'score_justifications'
            ]
            
            for field in required_fields:
                if field not in data:
                    raise ValueError(f"Missing required field: {field}")
            
            return StructuredAssessment(
                task_achievement_score=float(data['task_achievement_score']),
                coherence_cohesion_score=float(data['coherence_cohesion_score']),
                lexical_resource_score=float(data['lexical_resource_score']),
                grammatical_accuracy_score=float(data['grammatical_accuracy_score']),
                overall_band_score=float(data['overall_band_score']),
                detailed_feedback=str(data['detailed_feedback']),
                improvement_suggestions=list(data['improvement_suggestions']),
                score_justifications=dict(data['score_justifications'])
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            raise AIServiceError(
                f"Invalid JSON in AI response: {e}",
                service_type="openai",
                error_type="parse_error",
                recoverable=True
            )
        except (KeyError, TypeError, ValueError) as e:
            logger.error(f"Data validation error: {e}")
            raise AIServiceError(
                f"Invalid response format from AI: {e}",
                service_type="openai",
                error_type="format_error",
                recoverable=True
            )
    
    def validate_scores(self, assessment: StructuredAssessment) -> bool:
        """
        Validate assessment scores for consistency and prevent hallucinated scores
        
        Args:
            assessment: The structured assessment to validate
            
        Returns:
            True if scores are valid, False otherwise
        """
        try:
            # Check score ranges (0.0 to 9.0)
            scores = [
                assessment.task_achievement_score,
                assessment.coherence_cohesion_score,
                assessment.lexical_resource_score,
                assessment.grammatical_accuracy_score,
                assessment.overall_band_score
            ]
            
            for score in scores:
                if not (0.0 <= score <= 9.0):
                    logger.warning(f"Score out of range: {score}")
                    return False
                    
                # Check if score is in valid 0.5 increments
                if (score * 2) % 1 != 0:
                    logger.warning(f"Score not in 0.5 increments: {score}")
                    return False
            
            # Check overall score consistency (should be average of four criteria)
            individual_scores = scores[:4]
            expected_average = sum(individual_scores) / 4
            
            # Round to nearest 0.5
            expected_overall = round(expected_average * 2) / 2
            
            if abs(assessment.overall_band_score - expected_overall) > 0.1:
                logger.warning(
                    f"Overall score inconsistent. Expected: {expected_overall}, "
                    f"Got: {assessment.overall_band_score}"
                )
                return False
            
            # Check that feedback and suggestions are not empty
            if not assessment.detailed_feedback.strip():
                logger.warning("Empty detailed feedback")
                return False
                
            if not assessment.improvement_suggestions or len(assessment.improvement_suggestions) < 2:
                logger.warning("Insufficient improvement suggestions")
                return False
                
            # Check that all justifications are provided
            required_justifications = [
                'task_achievement', 'coherence_cohesion',
                'lexical_resource', 'grammatical_accuracy'
            ]
            
            for key in required_justifications:
                if key not in assessment.score_justifications or not assessment.score_justifications[key].strip():
                    logger.warning(f"Missing or empty justification for: {key}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating scores: {e}")
            return False
    
    def _is_circuit_breaker_open(self) -> bool:
        """Check if circuit breaker is currently open"""
        from datetime import datetime, timedelta
        
        if self.circuit_breaker_failures < self.circuit_breaker_threshold:
            return False
        
        if self.circuit_breaker_reset_time is None:
            self.circuit_breaker_reset_time = datetime.now() + timedelta(minutes=5)
            return True
        
        if datetime.now() > self.circuit_breaker_reset_time:
            # Reset circuit breaker
            self.circuit_breaker_failures = 0
            self.circuit_breaker_reset_time = None
            return False
        
        return True
    
    def _increment_circuit_breaker(self):
        """Increment circuit breaker failure count"""
        self.circuit_breaker_failures += 1
        logger.warning(f"Circuit breaker failures: {self.circuit_breaker_failures}/{self.circuit_breaker_threshold}")