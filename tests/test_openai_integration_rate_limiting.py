"""
Integration tests for OpenRouter API with rate limiting scenarios.
Tests real API integration behavior and rate limit handling.
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
import openai
from typing import List, Dict, Any

from src.services.ai_assessment_engine import (
    AIAssessmentEngine, TaskType, StructuredAssessment, RawAssessment
)
from tests.test_data.ielts_samples import IELTSTestData, MOCK_OPENAI_RESPONSES


class TestOpenRouterIntegration:
    """Test OpenRouter API integration with various scenarios."""
    
    @pytest.fixture
    def engine(self):
        """Create AI assessment engine instance for testing."""
        with patch('src.services.ai_assessment_engine.AsyncOpenAI') as mock_openai:
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client
            engine = AIAssessmentEngine(api_key="test-key", model="gpt-4")
            engine.client = mock_client
            return engine
    
    @pytest.fixture
    def sample_texts(self):
        """Get sample texts for testing."""
        return {
            'task1': IELTSTestData.get_task1_samples()[0].text,
            'task2': IELTSTestData.get_task2_samples()[0].text,
            'short': IELTSTestData.get_edge_cases()[0].text,
            'ambiguous': IELTSTestData.get_edge_cases()[2].text
        }
    
    def create_mock_openai_response(self, response_data: Dict[str, Any]) -> MagicMock:
        """Create mock OpenAI response."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = str(response_data)
        mock_response.usage.total_tokens = 1200
        mock_response.model = "gpt-4"
        return mock_response
    
    @pytest.mark.asyncio
    async def test_successful_api_call(self, engine, sample_texts):
        """Test successful OpenRouter API call."""
        
        # Mock successful response
        mock_response = self.create_mock_openai_response(MOCK_OPENAI_RESPONSES['high_quality'])
        engine.client.chat.completions.create.return_value = mock_response
        
        # Test assessment
        result = await engine.assess_writing(sample_texts['task2'], TaskType.TASK_2)
        
        # Verify result
        assert isinstance(result, RawAssessment)
        assert result.usage_tokens == 1200
        assert result.model_used == "gpt-4"
        assert "task_achievement_score" in result.content
        
        # Verify API was called correctly
        engine.client.chat.completions.create.assert_called_once()
        call_args = engine.client.chat.completions.create.call_args
        assert call_args[1]['model'] == "gpt-4"
        assert sample_texts['task2'] in call_args[1]['messages'][0]['content']
    
    @pytest.mark.asyncio
    async def test_rate_limit_error_retry_logic(self, engine, sample_texts):
        """Test retry logic when rate limit is exceeded."""
        
        # Mock rate limit error followed by success
        rate_limit_error = openai.RateLimitError(
            "Rate limit exceeded", 
            response=MagicMock(status_code=429), 
            body={}
        )
        
        successful_response = self.create_mock_openai_response(MOCK_OPENAI_RESPONSES['medium_quality'])
        
        engine.client.chat.completions.create.side_effect = [
            rate_limit_error,
            rate_limit_error,
            successful_response
        ]
        
        # Test with retry
        start_time = time.time()
        result = await engine.assess_writing(sample_texts['task1'], TaskType.TASK_1)
        end_time = time.time()
        
        # Verify result
        assert isinstance(result, RawAssessment)
        assert result.usage_tokens == 1200
        
        # Verify retries occurred
        assert engine.client.chat.completions.create.call_count == 3
        
        # Verify exponential backoff delay (should be at least 1 second for 2 retries)
        assert end_time - start_time >= 1.0
    
    @pytest.mark.asyncio
    async def test_rate_limit_max_retries_exceeded(self, engine, sample_texts):
        """Test behavior when max retries are exceeded."""
        
        # Mock continuous rate limit errors
        rate_limit_error = openai.RateLimitError(
            "Rate limit exceeded", 
            response=MagicMock(status_code=429), 
            body={}
        )
        
        engine.client.chat.completions.create.side_effect = rate_limit_error
        
        # Test should raise exception after max retries
        with pytest.raises(Exception, match="Rate limit exceeded after all retries"):
            await engine.assess_writing(sample_texts['task2'], TaskType.TASK_2)
        
        # Verify max retries were attempted
        assert engine.client.chat.completions.create.call_count == engine.max_retries
    
    @pytest.mark.asyncio
    async def test_api_timeout_retry_logic(self, engine, sample_texts):
        """Test retry logic for API timeout errors."""
        
        # Mock timeout error followed by success
        timeout_error = openai.APITimeoutError("Request timeout")
        successful_response = self.create_mock_openai_response(MOCK_OPENAI_RESPONSES['high_quality'])
        
        engine.client.chat.completions.create.side_effect = [
            timeout_error,
            successful_response
        ]
        
        # Test with retry
        result = await engine.assess_writing(sample_texts['task1'], TaskType.TASK_1)
        
        # Verify result
        assert isinstance(result, RawAssessment)
        assert engine.client.chat.completions.create.call_count == 2
    
    @pytest.mark.asyncio
    async def test_api_connection_error_retry(self, engine, sample_texts):
        """Test retry logic for connection errors."""
        
        # Mock connection error followed by success
        connection_error = openai.APIConnectionError("Connection failed")
        successful_response = self.create_mock_openai_response(MOCK_OPENAI_RESPONSES['medium_quality'])
        
        engine.client.chat.completions.create.side_effect = [
            connection_error,
            connection_error,
            successful_response
        ]
        
        # Test with retry
        result = await engine.assess_writing(sample_texts['task2'], TaskType.TASK_2)
        
        # Verify result
        assert isinstance(result, RawAssessment)
        assert engine.client.chat.completions.create.call_count == 3
    
    @pytest.mark.asyncio
    async def test_concurrent_api_calls_rate_limiting(self, engine, sample_texts):
        """Test concurrent API calls with rate limiting."""
        
        # Mock responses with some rate limit errors
        responses = []
        for i in range(10):
            if i % 3 == 0:  # Every 3rd call gets rate limited initially
                responses.append(openai.RateLimitError(
                    "Rate limit exceeded", 
                    response=MagicMock(status_code=429), 
                    body={}
                ))
            responses.append(self.create_mock_openai_response(MOCK_OPENAI_RESPONSES['medium_quality']))
        
        engine.client.chat.completions.create.side_effect = responses
        
        # Create concurrent tasks
        tasks = []
        for i in range(5):
            task_type = TaskType.TASK_1 if i % 2 == 0 else TaskType.TASK_2
            text = sample_texts['task1'] if task_type == TaskType.TASK_1 else sample_texts['task2']
            tasks.append(engine.assess_writing(text, task_type))
        
        # Execute concurrently
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        
        # Verify results
        successful_results = [r for r in results if isinstance(r, RawAssessment)]
        failed_results = [r for r in results if isinstance(r, Exception)]
        
        assert len(successful_results) == 5, f"Expected 5 successful results, got {len(successful_results)}"
        assert len(failed_results) == 0, f"Unexpected failures: {failed_results}"
        
        # Verify reasonable execution time (should handle retries efficiently)
        assert end_time - start_time < 10.0, f"Concurrent execution took too long: {end_time - start_time:.2f}s"
    
    @pytest.mark.asyncio
    async def test_malformed_api_response_handling(self, engine, sample_texts):
        """Test handling of malformed API responses."""
        
        # Mock malformed response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "This is not valid JSON {malformed"
        mock_response.usage.total_tokens = 800
        mock_response.model = "gpt-4"
        
        engine.client.chat.completions.create.return_value = mock_response
        
        # Test should handle malformed response gracefully
        result = await engine.assess_writing(sample_texts['task2'], TaskType.TASK_2)
        
        # Verify raw result is returned even with malformed content
        assert isinstance(result, RawAssessment)
        assert result.content == "This is not valid JSON {malformed"
        assert result.usage_tokens == 800
    
    @pytest.mark.asyncio
    async def test_empty_api_response_handling(self, engine, sample_texts):
        """Test handling of empty API responses."""
        
        # Mock empty response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = ""
        mock_response.usage.total_tokens = 100
        mock_response.model = "gpt-4"
        
        engine.client.chat.completions.create.return_value = mock_response
        
        # Test should handle empty response
        result = await engine.assess_writing(sample_texts['task1'], TaskType.TASK_1)
        
        assert isinstance(result, RawAssessment)
        assert result.content == ""
        assert result.usage_tokens == 100
    
    @pytest.mark.asyncio
    async def test_api_authentication_error(self, engine, sample_texts):
        """Test handling of authentication errors."""
        
        # Mock authentication error
        auth_error = openai.AuthenticationError(
            "Invalid API key", 
            response=MagicMock(status_code=401), 
            body={}
        )
        
        engine.client.chat.completions.create.side_effect = auth_error
        
        # Test should raise authentication error (no retry for auth errors)
        with pytest.raises(openai.AuthenticationError):
            await engine.assess_writing(sample_texts['task2'], TaskType.TASK_2)
        
        # Verify no retries for auth errors
        assert engine.client.chat.completions.create.call_count == 1
    
    @pytest.mark.asyncio
    async def test_api_quota_exceeded_error(self, engine, sample_texts):
        """Test handling of quota exceeded errors."""
        
        # Mock quota exceeded error
        quota_error = openai.RateLimitError(
            "Quota exceeded", 
            response=MagicMock(status_code=429), 
            body={"error": {"type": "insufficient_quota"}}
        )
        
        engine.client.chat.completions.create.side_effect = quota_error
        
        # Test should raise exception after retries
        with pytest.raises(Exception, match="Rate limit exceeded after all retries"):
            await engine.assess_writing(sample_texts['task1'], TaskType.TASK_1)
        
        # Verify retries were attempted
        assert engine.client.chat.completions.create.call_count == engine.max_retries
    
    @pytest.mark.asyncio
    async def test_different_model_responses(self, engine, sample_texts):
        """Test handling of responses from different models."""
        
        # Test with different model responses
        models_to_test = ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"]
        
        for model in models_to_test:
            # Update engine model
            engine.model = model
            
            # Mock response for this model
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = str(MOCK_OPENAI_RESPONSES['high_quality'])
            mock_response.usage.total_tokens = 1000
            mock_response.model = model
            
            engine.client.chat.completions.create.return_value = mock_response
            
            # Test assessment
            result = await engine.assess_writing(sample_texts['task2'], TaskType.TASK_2)
            
            # Verify result
            assert isinstance(result, RawAssessment)
            assert result.model_used == model
            assert result.usage_tokens == 1000
    
    @pytest.mark.asyncio
    async def test_token_usage_tracking(self, engine, sample_texts):
        """Test token usage tracking across multiple calls."""
        
        # Mock responses with different token counts
        token_counts = [800, 1200, 950, 1100, 750]
        responses = []
        
        for tokens in token_counts:
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = str(MOCK_OPENAI_RESPONSES['medium_quality'])
            mock_response.usage.total_tokens = tokens
            mock_response.model = "gpt-4"
            responses.append(mock_response)
        
        engine.client.chat.completions.create.side_effect = responses
        
        # Make multiple calls
        results = []
        for i in range(5):
            task_type = TaskType.TASK_1 if i % 2 == 0 else TaskType.TASK_2
            text = sample_texts['task1'] if task_type == TaskType.TASK_1 else sample_texts['task2']
            result = await engine.assess_writing(text, task_type)
            results.append(result)
        
        # Verify token tracking
        for i, result in enumerate(results):
            assert result.usage_tokens == token_counts[i]
        
        # Verify total tokens
        total_tokens = sum(r.usage_tokens for r in results)
        expected_total = sum(token_counts)
        assert total_tokens == expected_total
    
    @pytest.mark.asyncio
    async def test_prompt_length_optimization(self, engine):
        """Test handling of different prompt lengths."""
        
        # Test with texts of different lengths
        test_cases = [
            ("Short text", TaskType.TASK_1),
            (IELTSTestData.get_task1_samples()[0].text, TaskType.TASK_1),  # Medium
            (IELTSTestData.get_task1_samples()[2].text, TaskType.TASK_1),  # Long
            (IELTSTestData.get_task2_samples()[2].text, TaskType.TASK_2),  # Very long
        ]
        
        # Mock responses
        mock_response = self.create_mock_openai_response(MOCK_OPENAI_RESPONSES['medium_quality'])
        engine.client.chat.completions.create.return_value = mock_response
        
        for text, task_type in test_cases:
            result = await engine.assess_writing(text, task_type)
            
            # Verify result
            assert isinstance(result, RawAssessment)
            
            # Verify prompt was constructed properly
            call_args = engine.client.chat.completions.create.call_args
            prompt_content = call_args[1]['messages'][0]['content']
            
            # Verify text is included in prompt
            assert text in prompt_content
            
            # Verify task-specific instructions are included
            if task_type == TaskType.TASK_1:
                assert "Task 1" in prompt_content
            else:
                assert "Task 2" in prompt_content
    
    @pytest.mark.asyncio
    async def test_api_error_message_extraction(self, engine, sample_texts):
        """Test extraction of meaningful error messages from API errors."""
        
        # Test different error types
        error_cases = [
            (openai.RateLimitError("Rate limit exceeded", response=MagicMock(status_code=429), body={}), "Rate limit"),
            (openai.APITimeoutError("Request timeout"), "timeout"),
            (openai.APIConnectionError("Connection failed"), "connection"),
            (openai.BadRequestError("Invalid request", response=MagicMock(status_code=400), body={}), "request"),
        ]
        
        for error, expected_message_part in error_cases:
            engine.client.chat.completions.create.side_effect = [error] * engine.max_retries
            
            try:
                await engine.assess_writing(sample_texts['task2'], TaskType.TASK_2)
                assert False, f"Expected exception for {type(error).__name__}"
            except Exception as e:
                # Verify error message contains relevant information
                error_message = str(e).lower()
                assert expected_message_part.lower() in error_message or "retries" in error_message


class TestRateLimitingStrategies:
    """Test different rate limiting strategies and scenarios."""
    
    @pytest.fixture
    def engine_with_custom_limits(self):
        """Create engine with custom rate limiting parameters."""
        with patch('src.services.ai_assessment_engine.AsyncOpenAI') as mock_openai:
            mock_client = AsyncMock()
            mock_openai.return_value = mock_client
            engine = AIAssessmentEngine(
                api_key="test-key", 
                model="gpt-4",
                max_retries=5,
                base_delay=0.1  # Faster testing
            )
            engine.client = mock_client
            return engine
    
    @pytest.mark.asyncio
    async def test_exponential_backoff_timing(self, engine_with_custom_limits):
        """Test exponential backoff timing is correct."""
        
        # Mock rate limit errors
        rate_limit_error = openai.RateLimitError(
            "Rate limit exceeded", 
            response=MagicMock(status_code=429), 
            body={}
        )
        
        successful_response = MagicMock()
        successful_response.choices = [MagicMock()]
        successful_response.choices[0].message.content = str(MOCK_OPENAI_RESPONSES['medium_quality'])
        successful_response.usage.total_tokens = 1000
        successful_response.model = "gpt-4"
        
        engine_with_custom_limits.client.chat.completions.create.side_effect = [
            rate_limit_error,
            rate_limit_error,
            rate_limit_error,
            successful_response
        ]
        
        # Measure timing
        start_time = time.time()
        result = await engine_with_custom_limits.assess_writing("Test text", TaskType.TASK_2)
        end_time = time.time()
        
        # Verify result
        assert isinstance(result, RawAssessment)
        
        # Verify exponential backoff timing
        # Expected delays: 0.1s, 0.2s, 0.4s = 0.7s minimum
        total_time = end_time - start_time
        assert total_time >= 0.7, f"Backoff timing too fast: {total_time:.2f}s"
        assert total_time < 2.0, f"Backoff timing too slow: {total_time:.2f}s"
    
    @pytest.mark.asyncio
    async def test_concurrent_rate_limit_handling(self, engine_with_custom_limits):
        """Test rate limit handling with concurrent requests."""
        
        # Mock mixed responses (some rate limited, some successful)
        def create_response_sequence():
            responses = []
            for i in range(20):  # Enough for multiple concurrent requests
                if i % 4 == 0:  # Every 4th response is rate limited
                    responses.append(openai.RateLimitError(
                        "Rate limit exceeded", 
                        response=MagicMock(status_code=429), 
                        body={}
                    ))
                
                # Always follow with successful response
                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message.content = str(MOCK_OPENAI_RESPONSES['medium_quality'])
                mock_response.usage.total_tokens = 1000
                mock_response.model = "gpt-4"
                responses.append(mock_response)
            
            return responses
        
        engine_with_custom_limits.client.chat.completions.create.side_effect = create_response_sequence()
        
        # Create concurrent requests
        tasks = []
        for i in range(8):
            task_type = TaskType.TASK_1 if i % 2 == 0 else TaskType.TASK_2
            tasks.append(engine_with_custom_limits.assess_writing(f"Test text {i}", task_type))
        
        # Execute concurrently
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        
        # Verify all requests succeeded
        successful_results = [r for r in results if isinstance(r, RawAssessment)]
        failed_results = [r for r in results if isinstance(r, Exception)]
        
        assert len(successful_results) == 8, f"Expected 8 successful results, got {len(successful_results)}"
        assert len(failed_results) == 0, f"Unexpected failures: {failed_results}"
        
        # Verify reasonable execution time
        total_time = end_time - start_time
        assert total_time < 5.0, f"Concurrent rate limit handling took too long: {total_time:.2f}s"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])