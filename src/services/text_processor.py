"""
Text Processing Services for IELTS Writing Evaluation

This module provides text processing capabilities including task type detection,
text validation, and content analysis for IELTS writing submissions.
"""

import re
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Dict, Any
from langdetect import detect, DetectorFactory
from langdetect.lang_detect_exception import LangDetectException

from src.models.submission import TaskType

logger = logging.getLogger(__name__)

# Set seed for consistent language detection results
DetectorFactory.seed = 0


class ValidationError(Enum):
    """Enumeration for text validation errors"""
    TOO_SHORT = "too_short"
    TOO_LONG = "too_long" 
    NOT_ENGLISH = "not_english"
    INVALID_CONTENT = "invalid_content"
    EMPTY_TEXT = "empty_text"


@dataclass
class ValidationResult:
    """Result of text validation"""
    is_valid: bool
    errors: List[ValidationError]
    warnings: List[str]
    word_count: int
    detected_language: Optional[str] = None
    confidence_score: float = 0.0


@dataclass
class TaskDetectionResult:
    """Result of task type detection"""
    detected_type: Optional[TaskType]
    confidence_score: float
    reasoning: str
    requires_clarification: bool = False


class TaskTypeDetector:
    """
    Detects whether a text is IELTS Task 1 or Task 2 based on content analysis
    """
    
    def __init__(self):
        # Task 1 indicators (data description, charts, graphs, processes)
        self.task1_keywords = {
            'data_description': [
                'chart', 'graph', 'table', 'diagram', 'figure', 'data', 'statistics',
                'percentage', 'proportion', 'shows', 'illustrates', 'depicts', 'presents',
                'according to', 'as shown', 'as can be seen', 'the chart shows',
                'the graph illustrates', 'the table presents', 'the diagram depicts'
            ],
            'trends': [
                'increase', 'decrease', 'rise', 'fall', 'grew', 'declined', 'dropped',
                'climbed', 'soared', 'plummeted', 'fluctuated', 'remained stable',
                'peaked', 'reached a peak', 'hit a low', 'trend', 'pattern'
            ],
            'comparisons': [
                'higher than', 'lower than', 'compared to', 'in comparison',
                'whereas', 'while', 'however', 'on the other hand', 'similarly',
                'likewise', 'in contrast', 'difference', 'similar'
            ],
            'time_periods': [
                'from', 'to', 'between', 'during', 'over the period', 'throughout',
                'initially', 'finally', 'at the beginning', 'at the end'
            ],
            'process_description': [
                'process', 'stage', 'step', 'phase', 'procedure', 'method',
                'first', 'second', 'third', 'next', 'then', 'after that',
                'finally', 'lastly', 'subsequently'
            ]
        }
        
        # Task 2 indicators (opinion, argument, discussion)
        self.task2_keywords = {
            'opinion': [
                'i think', 'i believe', 'in my opinion', 'from my perspective',
                'i agree', 'i disagree', 'personally', 'i feel that',
                'it seems to me', 'i would argue', 'my view is'
            ],
            'argument': [
                'because', 'since', 'therefore', 'thus', 'consequently',
                'as a result', 'due to', 'owing to', 'for this reason',
                'evidence', 'proof', 'example', 'instance', 'case'
            ],
            'discussion': [
                'on one hand', 'on the other hand', 'some people think',
                'others believe', 'it is argued', 'supporters claim',
                'critics argue', 'proponents suggest', 'opponents contend'
            ],
            'conclusion': [
                'in conclusion', 'to conclude', 'in summary', 'to summarize',
                'overall', 'all things considered', 'taking everything into account'
            ],
            'social_issues': [
                'society', 'government', 'education', 'environment', 'technology',
                'health', 'economy', 'culture', 'family', 'work', 'lifestyle',
                'development', 'progress', 'change', 'impact', 'effect'
            ]
        }
    
    def detect_task_type(self, text: str) -> TaskDetectionResult:
        """
        Detect whether text is Task 1 or Task 2 based on content analysis
        
        Args:
            text: The writing text to analyze
            
        Returns:
            TaskDetectionResult with detection outcome
        """
        if not text or not text.strip():
            return TaskDetectionResult(
                detected_type=None,
                confidence_score=0.0,
                reasoning="Empty text provided",
                requires_clarification=True
            )
        
        text_lower = text.lower()
        
        # Calculate scores for each task type
        task1_score = self._calculate_task1_score(text_lower)
        task2_score = self._calculate_task2_score(text_lower)
        
        # Determine confidence and result
        total_score = task1_score + task2_score
        
        if total_score == 0:
            return TaskDetectionResult(
                detected_type=None,
                confidence_score=0.0,
                reasoning="No clear indicators found for either task type",
                requires_clarification=True
            )
        
        task1_confidence = task1_score / total_score
        task2_confidence = task2_score / total_score
        
        # Decision thresholds
        high_confidence_threshold = 0.65
        medium_confidence_threshold = 0.55
        
        if task1_confidence >= high_confidence_threshold:
            return TaskDetectionResult(
                detected_type=TaskType.TASK_1,
                confidence_score=task1_confidence,
                reasoning=f"Strong Task 1 indicators detected (data description, trends, comparisons)",
                requires_clarification=False
            )
        elif task2_confidence >= high_confidence_threshold:
            return TaskDetectionResult(
                detected_type=TaskType.TASK_2,
                confidence_score=task2_confidence,
                reasoning=f"Strong Task 2 indicators detected (opinions, arguments, discussions)",
                requires_clarification=False
            )
        elif task1_confidence >= medium_confidence_threshold:
            return TaskDetectionResult(
                detected_type=TaskType.TASK_1,
                confidence_score=task1_confidence,
                reasoning=f"Moderate Task 1 indicators detected",
                requires_clarification=task1_confidence < 0.6
            )
        elif task2_confidence >= medium_confidence_threshold:
            return TaskDetectionResult(
                detected_type=TaskType.TASK_2,
                confidence_score=task2_confidence,
                reasoning=f"Moderate Task 2 indicators detected",
                requires_clarification=task2_confidence < 0.6
            )
        else:
            return TaskDetectionResult(
                detected_type=None,
                confidence_score=max(task1_confidence, task2_confidence),
                reasoning="Ambiguous content - could be either task type",
                requires_clarification=True
            )
    
    def _calculate_task1_score(self, text: str) -> float:
        """Calculate Task 1 likelihood score"""
        score = 0.0
        
        # Weight different categories
        weights = {
            'data_description': 3.0,
            'trends': 2.5,
            'comparisons': 2.0,
            'time_periods': 1.5,
            'process_description': 2.0
        }
        
        for category, keywords in self.task1_keywords.items():
            category_score = 0
            for keyword in keywords:
                # Use word boundaries for single words to avoid false matches
                if len(keyword.split()) == 1:
                    import re
                    pattern = r'\b' + re.escape(keyword) + r'\b'
                    if re.search(pattern, text, re.IGNORECASE):
                        category_score += 1
                else:
                    # For phrases, use simple substring matching
                    if keyword in text:
                        category_score += 1
            
            # Apply weight and normalize by category size
            normalized_score = (category_score / len(keywords)) * weights[category]
            score += normalized_score
        
        return score
    
    def _calculate_task2_score(self, text: str) -> float:
        """Calculate Task 2 likelihood score"""
        score = 0.0
        
        # Weight different categories
        weights = {
            'opinion': 3.0,
            'argument': 2.5,
            'discussion': 2.0,
            'conclusion': 1.5,
            'social_issues': 1.0
        }
        
        for category, keywords in self.task2_keywords.items():
            category_score = 0
            for keyword in keywords:
                # Use word boundaries for single words to avoid false matches
                if len(keyword.split()) == 1:
                    import re
                    pattern = r'\b' + re.escape(keyword) + r'\b'
                    if re.search(pattern, text, re.IGNORECASE):
                        category_score += 1
                else:
                    # For phrases, use simple substring matching
                    if keyword in text:
                        category_score += 1
            
            # Apply weight and normalize by category size
            normalized_score = (category_score / len(keywords)) * weights[category]
            score += normalized_score
        
        return score


class TextValidator:
    """
    Validates text submissions for language, length, and content quality
    """
    
    def __init__(self):
        self.min_word_count = 50
        self.max_word_count = 1000
        self.english_confidence_threshold = 0.8
    
    def validate_submission(self, text: str) -> ValidationResult:
        """
        Validate a text submission for IELTS evaluation
        
        Args:
            text: The text to validate
            
        Returns:
            ValidationResult with validation outcome
        """
        errors = []
        warnings = []
        
        # Check for empty text
        if not text or not text.strip():
            return ValidationResult(
                is_valid=False,
                errors=[ValidationError.EMPTY_TEXT],
                warnings=[],
                word_count=0
            )
        
        # Clean and count words
        cleaned_text = self._clean_text(text)
        word_count = self._count_words(cleaned_text)
        
        # Validate word count
        if word_count < self.min_word_count:
            errors.append(ValidationError.TOO_SHORT)
        elif word_count > self.max_word_count:
            warnings.append(f"Text is {word_count} words. IELTS tasks typically require 150-250 words (Task 1) or 250+ words (Task 2)")
        
        # Validate language
        language_result = self._detect_language(cleaned_text)
        detected_language = language_result.get('language')
        confidence = language_result.get('confidence', 0.0)
        
        if detected_language != 'en' or confidence < self.english_confidence_threshold:
            errors.append(ValidationError.NOT_ENGLISH)
        
        # Validate content quality
        content_issues = self._validate_content_quality(cleaned_text)
        if content_issues:
            errors.append(ValidationError.INVALID_CONTENT)
            warnings.extend(content_issues)
        
        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            word_count=word_count,
            detected_language=detected_language,
            confidence_score=confidence
        )
    
    def _clean_text(self, text: str) -> str:
        """Clean text for processing"""
        # Remove extra whitespace and normalize
        cleaned = re.sub(r'\s+', ' ', text.strip())
        return cleaned
    
    def _count_words(self, text: str) -> int:
        """Count words in text"""
        if not text.strip():
            return 0
        
        # Split by whitespace and filter out empty strings
        words = [word for word in text.split() if word.strip()]
        return len(words)
    
    def _detect_language(self, text: str) -> Dict[str, Any]:
        """Detect language of text"""
        try:
            detected_lang = detect(text)
            # langdetect doesn't provide confidence directly, so we estimate it
            # based on text length and detection success
            confidence = min(0.9, max(0.5, len(text) / 100))
            
            return {
                'language': detected_lang,
                'confidence': confidence
            }
        except LangDetectException as e:
            logger.warning(f"Language detection failed: {e}")
            return {
                'language': 'unknown',
                'confidence': 0.0
            }
    
    def _validate_content_quality(self, text: str) -> List[str]:
        """Validate content quality and return issues"""
        issues = []
        
        # Check for excessive repetition
        words = text.lower().split()
        if len(words) > 10:
            word_freq = {}
            for word in words:
                if len(word) > 3:  # Only check longer words
                    word_freq[word] = word_freq.get(word, 0) + 1
            
            # Check if any word appears too frequently
            total_words = len(words)
            for word, count in word_freq.items():
                if count / total_words > 0.1:  # More than 10% repetition
                    issues.append(f"Excessive repetition of word '{word}'")
        
        # Check for minimum sentence structure
        sentences = re.split(r'[.!?]+', text)
        valid_sentences = [s for s in sentences if len(s.strip().split()) >= 3]
        
        if len(valid_sentences) < 3:
            issues.append("Text appears to lack proper sentence structure")
        
        # Check for basic punctuation
        if not re.search(r'[.!?]', text):
            issues.append("Text lacks proper punctuation")
        
        return issues