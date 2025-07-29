"""
Unit tests for AI Assessment Engine

Tests the AI assessment functionality with mocked OpenAI responses
to ensure proper error handling, response parsing, and score validation.
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, Mock, patch
import openai

from src.services.ai_assessment_engine import (
    AIAssessmentEngine, TaskType, StructuredAssessment, RawAssessment
)


@pytest.fixture
def engine():
    """Create AI assessment engine instance for testing"""
    with patch('src.services.ai_assessment_engine.AsyncOpenAI') as mock_openai:
        mock_client = AsyncMock()
        mock_openai.return_value = mock_client
        engine = AIAssessmentEngine(api_key="test-key", model="gpt-4")
        engine.client = mock_client
        return engine


@pytest.fixture
def mock_openai_response():
    """Mock OpenAI API response"""
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = json.dumps({
        "task_achievement_score": 7.0,
        "coherence_cohesion_score": 6.5,
        "lexical_resource_score": 7.5,
        "grammatical_accuracy_score": 6.0,
        "overall_band_score": 6.5,
        "detailed_feedback": "This is a well-structured response that addresses the task requirements effectively.",
        "improvement_suggestions": [
            "Use more varied sentence structures",
            "Include more specific examples",
            "Improve grammatical accuracy"
        ],
        "score_justifications": {
            "task_achievement": "The response addresses all parts of the task with clear position",
            "coherence_cohesion": "Good organization with appropriate linking devices",
            "lexical_resource": "Wide range of vocabulary used appropriately",
            "grammatical_accuracy": "Some errors present but communication is clear"
        }
    })
    mock_response.usage.total_tokens = 1200
    mock_response.model = "gpt-4"
    return mock_response


@pytest.fixture
def sample_task1_text():
    """Sample Task 1 writing text"""
    return """
    The chart shows the percentage of households with different types of internet connection 
    from 2010 to 2020. Overall, there was a significant increase in broadband connections 
    while dial-up connections decreased dramatically over the period.
    """


@pytest.fixture
def sample_task2_text():
    """Sample Task 2 writing text"""
    return """
    Some people believe that technology has made our lives easier, while others argue 
    that it has created more problems. In my opinion, while technology has brought 
    convenience, it has also introduced new challenges that we must address.
    """


class TestAIAssessmentEngine:
    """Test suite for AIAssessmentEngine class"""


class TestPromptBuilder:
    """Test prompt building functionality"""
    
    def test_build_task1_prompt(self, engine, sample_task1_text):
        """Test Task 1 prompt building"""
        prompt = engine.build_prompt(sample_task1_text, TaskType.TASK_1)
        
        assert sample_task1_text in prompt
        assert "Task 1" in prompt
        assert "task_achievement_score" in prompt
        assert "Task Achievement" in prompt
        assert "overview of main trends" in prompt
    
    def test_build_task2_prompt(self, engine, sample_task2_text):
        """Test Task 2 prompt building"""
        prompt = engine.build_prompt(sample_task2_text, TaskType.TASK_2)
        
        assert sample_task2_text in prompt
        assert "Task 2" in prompt
        assert "task_achievement_score" in prompt
        assert "Task Response" in prompt
        assert "clear position throughout" in prompt
    
    def test_prompt_contains_json_format(self, engine, sample_task1_text):
        """Test that prompt contains required JSON format"""
        prompt = engine.build_prompt(sample_task1_text, TaskType.TASK_1)
        
        required_fields = [
            "task_achievement_score",
            "coherence_cohesion_score", 
            "lexical_resource_score",
            "grammatical_accuracy_score",
            "overall_band_score",
            "detailed_feedback",
            "improvement_suggestions",
            "score_justifications"
        ]
        
        for field in required_fields:
            assert field in prompt


class TestAssessWriting:
    """Test the main assess_writing method"""
    
    @pytest.mark.asyncio
    async def test_successful_assessment(self, engine, mock_openai_response, sample_task1_text):
        """Test successful writing assessment"""
        with patch.object(engine.client.chat.completions, 'create', return_value=mock_openai_response):
            result = await engine.assess_writing(sample_task1_text, TaskType.TASK_1)
            
            assert isinstance(result, RawAssessment)
            assert result.usage_tokens == 1200
            assert result.model_used == "gpt-4"
            assert "task_achievement_score" in result.content
    
    @pytest.mark.asyncio
    async def test_rate_limit_retry(self, engine, sample_task1_text):
        """Test retry logic for rate limit errors"""
        with patch.object(engine.client.chat.completions, 'create') as mock_create:
            # First two calls raise rate limit error, third succeeds
            mock_create.side_effect = [
                openai.RateLimitError("Rate limit exceeded", response=Mock(), body={}),
                openai.RateLimitError("Rate limit exceeded", response=Mock(), body={}),
                Mock(
                    choices=[Mock(message=Mock(content='{"test": "response"}'))],
                    usage=Mock(total_tokens=100),
                    model="gpt-4"
                )
            ]
            
            result = await engine.assess_writing(sample_task1_text, TaskType.TASK_1)
            
            assert mock_create.call_count == 3
            assert isinstance(result, RawAssessment)
    
    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self, engine, sample_task1_text):
        """Test behavior when max retries are exceeded"""
        with patch.object(engine.client.chat.completions, 'create') as mock_create:
            mock_create.side_effect = openai.RateLimitError("Rate limit exceeded", response=Mock(), body={})
            
            with pytest.raises(Exception, match="Rate limit exceeded after all retries"):
                await engine.assess_writing(sample_task1_text, TaskType.TASK_1)
            
            assert mock_create.call_count == engine.max_retries
    
    @pytest.mark.asyncio
    async def test_api_timeout_retry(self, engine, sample_task1_text):
        """Test retry logic for API timeout errors"""
        with patch.object(engine.client.chat.completions, 'create') as mock_create:
            mock_create.side_effect = [
                openai.APITimeoutError("Request timeout"),
                Mock(
                    choices=[Mock(message=Mock(content='{"test": "response"}'))],
                    usage=Mock(total_tokens=100),
                    model="gpt-4"
                )
            ]
            
            result = await engine.assess_writing(sample_task1_text, TaskType.TASK_1)
            
            assert mock_create.call_count == 2
            assert isinstance(result, RawAssessment)


class TestResponseParser:
    """Test response parsing functionality"""
    
    def test_parse_valid_response(self, engine):
        """Test parsing valid JSON response"""
        response = json.dumps({
            "task_achievement_score": 7.0,
            "coherence_cohesion_score": 6.5,
            "lexical_resource_score": 7.5,
            "grammatical_accuracy_score": 6.0,
            "overall_band_score": 6.5,
            "detailed_feedback": "Good response overall",
            "improvement_suggestions": ["Suggestion 1", "Suggestion 2"],
            "score_justifications": {
                "task_achievement": "Good task response",
                "coherence_cohesion": "Well organized",
                "lexical_resource": "Good vocabulary",
                "grammatical_accuracy": "Some errors present"
            }
        })
        
        result = engine.parse_response(response)
        
        assert isinstance(result, StructuredAssessment)
        assert result.task_achievement_score == 7.0
        assert result.coherence_cohesion_score == 6.5
        assert result.overall_band_score == 6.5
        assert len(result.improvement_suggestions) == 2
    
    def test_parse_response_with_extra_text(self, engine):
        """Test parsing JSON wrapped in extra text"""
        json_data = {
            "task_achievement_score": 7.0,
            "coherence_cohesion_score": 6.5,
            "lexical_resource_score": 7.5,
            "grammatical_accuracy_score": 6.0,
            "overall_band_score": 6.5,
            "detailed_feedback": "Good response overall",
            "improvement_suggestions": ["Suggestion 1", "Suggestion 2"],
            "score_justifications": {
                "task_achievement": "Good task response",
                "coherence_cohesion": "Well organized", 
                "lexical_resource": "Good vocabulary",
                "grammatical_accuracy": "Some errors present"
            }
        }
        
        response = f"Here is my assessment:\n\n{json.dumps(json_data)}\n\nI hope this helps!"
        
        result = engine.parse_response(response)
        
        assert isinstance(result, StructuredAssessment)
        assert result.task_achievement_score == 7.0
    
    def test_parse_invalid_json(self, engine):
        """Test parsing invalid JSON"""
        response = "This is not valid JSON {invalid}"
        
        with pytest.raises(ValueError, match="Invalid JSON in response"):
            engine.parse_response(response)
    
    def test_parse_missing_fields(self, engine):
        """Test parsing JSON with missing required fields"""
        response = json.dumps({
            "task_achievement_score": 7.0,
            "coherence_cohesion_score": 6.5
            # Missing other required fields
        })
        
        with pytest.raises(ValueError, match="Missing required field"):
            engine.parse_response(response)
    
    def test_parse_no_json_found(self, engine):
        """Test parsing response with no JSON"""
        response = "This response contains no JSON at all"
        
        with pytest.raises(ValueError, match="No JSON found in response"):
            engine.parse_response(response)


class TestScoreValidator:
    """Test score validation functionality"""
    
    def test_validate_valid_scores(self, engine):
        """Test validation of valid scores"""
        # Average of 7.0, 6.5, 7.5, 6.0 = 6.75, rounded to 7.0
        assessment = StructuredAssessment(
            task_achievement_score=7.0,
            coherence_cohesion_score=6.5,
            lexical_resource_score=7.5,
            grammatical_accuracy_score=6.0,
            overall_band_score=7.0,  # Changed from 6.5 to 7.0
            detailed_feedback="Good response with clear structure",
            improvement_suggestions=["Improve grammar", "Use more examples"],
            score_justifications={
                "task_achievement": "Addresses task well",
                "coherence_cohesion": "Good organization",
                "lexical_resource": "Appropriate vocabulary",
                "grammatical_accuracy": "Some errors present"
            }
        )
        
        assert engine.validate_scores(assessment) is True
    
    def test_validate_scores_out_of_range(self, engine):
        """Test validation fails for scores out of range"""
        assessment = StructuredAssessment(
            task_achievement_score=10.0,  # Invalid: > 9.0
            coherence_cohesion_score=6.5,
            lexical_resource_score=7.5,
            grammatical_accuracy_score=6.0,
            overall_band_score=6.5,
            detailed_feedback="Good response",
            improvement_suggestions=["Improve grammar"],
            score_justifications={
                "task_achievement": "Good",
                "coherence_cohesion": "Good",
                "lexical_resource": "Good",
                "grammatical_accuracy": "Good"
            }
        )
        
        assert engine.validate_scores(assessment) is False
    
    def test_validate_scores_wrong_increments(self, engine):
        """Test validation fails for scores not in 0.5 increments"""
        assessment = StructuredAssessment(
            task_achievement_score=7.3,  # Invalid: not 0.5 increment
            coherence_cohesion_score=6.5,
            lexical_resource_score=7.5,
            grammatical_accuracy_score=6.0,
            overall_band_score=6.5,
            detailed_feedback="Good response",
            improvement_suggestions=["Improve grammar"],
            score_justifications={
                "task_achievement": "Good",
                "coherence_cohesion": "Good",
                "lexical_resource": "Good",
                "grammatical_accuracy": "Good"
            }
        )
        
        assert engine.validate_scores(assessment) is False
    
    def test_validate_inconsistent_overall_score(self, engine):
        """Test validation fails for inconsistent overall score"""
        assessment = StructuredAssessment(
            task_achievement_score=7.0,
            coherence_cohesion_score=6.5,
            lexical_resource_score=7.5,
            grammatical_accuracy_score=6.0,
            overall_band_score=8.0,  # Invalid: should be ~6.75 -> 7.0
            detailed_feedback="Good response",
            improvement_suggestions=["Improve grammar"],
            score_justifications={
                "task_achievement": "Good",
                "coherence_cohesion": "Good",
                "lexical_resource": "Good",
                "grammatical_accuracy": "Good"
            }
        )
        
        assert engine.validate_scores(assessment) is False
    
    def test_validate_empty_feedback(self, engine):
        """Test validation fails for empty feedback"""
        assessment = StructuredAssessment(
            task_achievement_score=7.0,
            coherence_cohesion_score=6.5,
            lexical_resource_score=7.5,
            grammatical_accuracy_score=6.0,
            overall_band_score=6.5,
            detailed_feedback="",  # Invalid: empty
            improvement_suggestions=["Improve grammar"],
            score_justifications={
                "task_achievement": "Good",
                "coherence_cohesion": "Good",
                "lexical_resource": "Good",
                "grammatical_accuracy": "Good"
            }
        )
        
        assert engine.validate_scores(assessment) is False
    
    def test_validate_insufficient_suggestions(self, engine):
        """Test validation fails for insufficient improvement suggestions"""
        assessment = StructuredAssessment(
            task_achievement_score=7.0,
            coherence_cohesion_score=6.5,
            lexical_resource_score=7.5,
            grammatical_accuracy_score=6.0,
            overall_band_score=6.5,
            detailed_feedback="Good response",
            improvement_suggestions=["Only one suggestion"],  # Invalid: < 2
            score_justifications={
                "task_achievement": "Good",
                "coherence_cohesion": "Good",
                "lexical_resource": "Good",
                "grammatical_accuracy": "Good"
            }
        )
        
        assert engine.validate_scores(assessment) is False
    
    def test_validate_missing_justifications(self, engine):
        """Test validation fails for missing score justifications"""
        assessment = StructuredAssessment(
            task_achievement_score=7.0,
            coherence_cohesion_score=6.5,
            lexical_resource_score=7.5,
            grammatical_accuracy_score=6.0,
            overall_band_score=6.5,
            detailed_feedback="Good response",
            improvement_suggestions=["Improve grammar", "Use examples"],
            score_justifications={
                "task_achievement": "Good",
                # Missing other justifications
            }
        )
        
        assert engine.validate_scores(assessment) is False


class TestIntegration:
    """Integration tests combining multiple components"""
    
    @pytest.mark.asyncio
    async def test_full_assessment_workflow(self, engine, sample_task1_text):
        """Test complete assessment workflow from text to validated result"""
        mock_response_data = {
            "task_achievement_score": 7.0,
            "coherence_cohesion_score": 6.5,
            "lexical_resource_score": 7.5,
            "grammatical_accuracy_score": 6.0,
            "overall_band_score": 7.0,  # Changed from 6.5 to 7.0 to match average
            "detailed_feedback": "This response demonstrates good understanding of the task",
            "improvement_suggestions": [
                "Use more varied sentence structures",
                "Include more specific data points",
                "Improve grammatical accuracy"
            ],
            "score_justifications": {
                "task_achievement": "Addresses all requirements with clear overview",
                "coherence_cohesion": "Well organized with appropriate linking",
                "lexical_resource": "Good range of vocabulary used appropriately",
                "grammatical_accuracy": "Some errors but communication is clear"
            }
        }
        
        mock_openai_response = Mock()
        mock_openai_response.choices = [Mock()]
        mock_openai_response.choices[0].message.content = json.dumps(mock_response_data)
        mock_openai_response.usage.total_tokens = 1200
        mock_openai_response.model = "gpt-4"
        
        with patch.object(engine.client.chat.completions, 'create', return_value=mock_openai_response):
            # Get raw assessment
            raw_result = await engine.assess_writing(sample_task1_text, TaskType.TASK_1)
            
            # Parse response
            structured_result = engine.parse_response(raw_result.content)
            
            # Validate scores
            is_valid = engine.validate_scores(structured_result)
            
            assert isinstance(raw_result, RawAssessment)
            assert isinstance(structured_result, StructuredAssessment)
            assert is_valid is True
            assert structured_result.overall_band_score == 7.0
            assert len(structured_result.improvement_suggestions) == 3