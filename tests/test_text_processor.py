"""
Unit tests for text processing services
"""

import pytest
from unittest.mock import patch, MagicMock

from src.services.text_processor import (
    TextValidator, TaskTypeDetector, ValidationResult, TaskDetectionResult,
    ValidationError
)
from src.models.submission import TaskType


class TestTaskTypeDetector:
    """Test cases for TaskTypeDetector"""
    
    def setup_method(self):
        self.detector = TaskTypeDetector()
    
    def test_detect_task1_chart_description(self):
        """Test detection of Task 1 with chart description"""
        text = """
        The chart shows the percentage of households with different types of internet 
        connections from 2010 to 2020. According to the data, broadband connections 
        increased significantly from 45% to 78% over the period, while dial-up 
        connections decreased from 30% to 5%. The graph illustrates a clear trend 
        towards faster internet technologies.
        """
        
        result = self.detector.detect_task_type(text)
        
        assert result.detected_type == TaskType.TASK_1
        assert result.confidence_score > 0.7
        assert not result.requires_clarification
        assert "Task 1 indicators" in result.reasoning
    
    def test_detect_task1_process_description(self):
        """Test detection of Task 1 with process description"""
        text = """
        The diagram depicts the process of chocolate production. First, cocoa beans 
        are harvested from cocoa trees. Next, the beans are fermented for several days. 
        After that, they are dried in the sun. Subsequently, the beans are roasted 
        at high temperatures. Finally, the roasted beans are ground to produce 
        chocolate liquor, which is then processed into various chocolate products.
        """
        
        result = self.detector.detect_task_type(text)
        
        assert result.detected_type == TaskType.TASK_1
        assert result.confidence_score > 0.6
        assert "process" in result.reasoning.lower() or "task 1" in result.reasoning.lower()
    
    def test_detect_task2_opinion_essay(self):
        """Test detection of Task 2 with opinion essay"""
        text = """
        I strongly believe that technology has had a positive impact on education. 
        In my opinion, digital tools have made learning more accessible and engaging 
        for students worldwide. For example, online courses allow people to study 
        from anywhere, breaking down geographical barriers. Furthermore, interactive 
        software helps students understand complex concepts more easily. However, 
        some critics argue that technology can be distracting. Nevertheless, I think 
        the benefits outweigh the drawbacks. In conclusion, technology should be 
        embraced in educational settings.
        """
        
        result = self.detector.detect_task_type(text)
        
        assert result.detected_type == TaskType.TASK_2
        assert result.confidence_score > 0.55
        assert "Task 2 indicators" in result.reasoning
    
    def test_detect_task2_discussion_essay(self):
        """Test detection of Task 2 with discussion essay"""
        text = """
        Some people think that governments should invest more in public transportation, 
        while others believe that private car ownership should be encouraged. On one 
        hand, supporters of public transport argue that it reduces traffic congestion 
        and environmental pollution. They claim that buses and trains can carry many 
        passengers efficiently. On the other hand, proponents of private cars contend 
        that personal vehicles offer greater convenience and flexibility. Taking 
        everything into account, both transportation methods have their merits and 
        should coexist in modern society.
        """
        
        result = self.detector.detect_task_type(text)
        
        assert result.detected_type == TaskType.TASK_2
        assert result.confidence_score > 0.55
        assert "task 2" in result.reasoning.lower() or result.detected_type == TaskType.TASK_2
    
    def test_detect_ambiguous_text(self):
        """Test detection with ambiguous text"""
        text = """
        This is a text that doesn't have clear indicators for either task type.
        It's just some general writing without specific IELTS task characteristics.
        There are no charts, graphs, opinions, or arguments here.
        """
        
        result = self.detector.detect_task_type(text)
        
        assert result.detected_type is None or result.requires_clarification
        assert result.confidence_score < 0.8
    
    def test_detect_empty_text(self):
        """Test detection with empty text"""
        result = self.detector.detect_task_type("")
        
        assert result.detected_type is None
        assert result.confidence_score == 0.0
        assert result.requires_clarification
        assert "Empty text" in result.reasoning
    
    def test_detect_mixed_indicators(self):
        """Test detection with mixed Task 1 and Task 2 indicators"""
        text = """
        The chart shows education spending from 2010 to 2020. I believe this data 
        demonstrates that governments should invest more in education. In my opinion, 
        the increase from 5% to 8% of GDP is significant. However, some people think 
        this is not enough. The graph illustrates steady growth over the period.
        """
        
        result = self.detector.detect_task_type(text)
        
        # Should detect the stronger signal or require clarification
        assert result.detected_type is not None or result.requires_clarification


class TestTextValidator:
    """Test cases for TextValidator"""
    
    def setup_method(self):
        self.validator = TextValidator()
    
    def test_validate_good_english_text(self):
        """Test validation of good English text"""
        text = """
        Technology has revolutionized the way we communicate and work. Modern devices 
        like smartphones and laptops have made it possible to stay connected with 
        people around the world. This has created new opportunities for collaboration 
        and business development. However, it has also raised concerns about privacy 
        and social isolation. Overall, the benefits of technology outweigh its 
        drawbacks when used responsibly.
        """
        
        with patch('src.services.text_processor.detect') as mock_detect:
            mock_detect.return_value = 'en'
            
            result = self.validator.validate_submission(text)
            
            assert result.is_valid
            assert len(result.errors) == 0
            assert result.word_count > 50
            assert result.detected_language == 'en'
    
    def test_validate_too_short_text(self):
        """Test validation of text that's too short"""
        text = "This is a very short text with only a few words."
        
        with patch('src.services.text_processor.detect') as mock_detect:
            mock_detect.return_value = 'en'
            
            result = self.validator.validate_submission(text)
            
            assert not result.is_valid
            assert ValidationError.TOO_SHORT in result.errors
            assert result.word_count < 50
    
    def test_validate_empty_text(self):
        """Test validation of empty text"""
        result = self.validator.validate_submission("")
        
        assert not result.is_valid
        assert ValidationError.EMPTY_TEXT in result.errors
        assert result.word_count == 0
    
    def test_validate_whitespace_only_text(self):
        """Test validation of whitespace-only text"""
        result = self.validator.validate_submission("   \n\t   ")
        
        assert not result.is_valid
        assert ValidationError.EMPTY_TEXT in result.errors
        assert result.word_count == 0
    
    def test_validate_non_english_text(self):
        """Test validation of non-English text"""
        text = """
        Esta es una prueba en español para verificar la detección de idioma. 
        El sistema debería identificar que este texto no está en inglés y 
        rechazar la evaluación. Necesitamos al menos cincuenta palabras para 
        que la validación funcione correctamente y podamos probar todos los 
        aspectos del sistema de validación de texto.
        """
        
        with patch('src.services.text_processor.detect') as mock_detect:
            mock_detect.return_value = 'es'  # Spanish
            
            result = self.validator.validate_submission(text)
            
            assert not result.is_valid
            assert ValidationError.NOT_ENGLISH in result.errors
            assert result.detected_language == 'es'
    
    def test_validate_very_long_text(self):
        """Test validation of very long text"""
        # Create a text with over 1000 words but with varied vocabulary
        sentences = [
            "Technology has revolutionized modern education systems worldwide.",
            "Students now have access to online learning platforms and digital resources.",
            "Teachers can utilize interactive tools to enhance classroom engagement.",
            "Educational institutions are adapting to new technological trends.",
            "Distance learning has become increasingly popular among learners.",
            "Digital literacy skills are essential for academic success today.",
            "Virtual classrooms provide flexible learning opportunities for students.",
            "Educational software helps personalize learning experiences effectively.",
            "Online assessments offer immediate feedback to both students and instructors.",
            "Collaborative learning platforms facilitate group projects and discussions."
        ]
        long_text = " ".join(sentences * 25)  # Creates ~2500 words
        
        with patch('src.services.text_processor.detect') as mock_detect:
            mock_detect.return_value = 'en'
            
            result = self.validator.validate_submission(long_text)
            
            assert result.is_valid  # Still valid but with warnings
            assert len(result.warnings) > 0
            assert result.word_count > 1000
            assert any("words" in warning for warning in result.warnings)
    
    def test_validate_repetitive_text(self):
        """Test validation of text with excessive repetition"""
        repetitive_text = """
        The same word appears repeatedly in this text. The same word appears 
        repeatedly in this text. The same word appears repeatedly in this text. 
        The same word appears repeatedly in this text. The same word appears 
        repeatedly in this text. The same word appears repeatedly in this text.
        The same word appears repeatedly in this text. The same word appears 
        repeatedly in this text.
        """
        
        with patch('src.services.text_processor.detect') as mock_detect:
            mock_detect.return_value = 'en'
            
            result = self.validator.validate_submission(repetitive_text)
            
            assert not result.is_valid
            assert ValidationError.INVALID_CONTENT in result.errors
            assert any("repetition" in warning.lower() for warning in result.warnings)
    
    def test_validate_poor_sentence_structure(self):
        """Test validation of text with poor sentence structure"""
        poor_text = "word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word word"
        
        with patch('src.services.text_processor.detect') as mock_detect:
            mock_detect.return_value = 'en'
            
            result = self.validator.validate_submission(poor_text)
            
            assert not result.is_valid
            assert ValidationError.INVALID_CONTENT in result.errors
            assert any("sentence structure" in warning for warning in result.warnings)
    
    def test_validate_no_punctuation(self):
        """Test validation of text without punctuation"""
        no_punct_text = """
        This is a text without any proper punctuation marks it just goes on and on
        without any periods or question marks or exclamation points which makes it
        very difficult to read and understand the structure and meaning of the content
        that is being presented to the reader who expects proper formatting
        """
        
        with patch('src.services.text_processor.detect') as mock_detect:
            mock_detect.return_value = 'en'
            
            result = self.validator.validate_submission(no_punct_text)
            
            assert not result.is_valid
            assert ValidationError.INVALID_CONTENT in result.errors
            assert any("punctuation" in warning for warning in result.warnings)
    
    @patch('src.services.text_processor.detect')
    def test_language_detection_failure(self, mock_detect):
        """Test handling of language detection failure"""
        from langdetect.lang_detect_exception import LangDetectException
        
        mock_detect.side_effect = LangDetectException(code=0, message="Detection failed")
        
        text = "This is a test text with enough words to pass the word count validation."
        
        result = self.validator.validate_submission(text)
        
        assert not result.is_valid
        assert ValidationError.NOT_ENGLISH in result.errors
        assert result.detected_language == 'unknown'
        assert result.confidence_score == 0.0
    
    def test_word_count_accuracy(self):
        """Test word counting accuracy"""
        text = "One two three four five six seven eight nine ten."
        
        with patch('src.services.text_processor.detect') as mock_detect:
            mock_detect.return_value = 'en'
            
            result = self.validator.validate_submission(text)
            
            assert result.word_count == 10
    
    def test_word_count_with_extra_whitespace(self):
        """Test word counting with extra whitespace"""
        text = "  One   two    three     four   five  \n\n  six   seven  \t eight   nine    ten.  "
        
        with patch('src.services.text_processor.detect') as mock_detect:
            mock_detect.return_value = 'en'
            
            result = self.validator.validate_submission(text)
            
            assert result.word_count == 10


# Sample IELTS texts for testing
SAMPLE_TASK1_TEXTS = [
    """
    The bar chart illustrates the number of visitors to three museums in London 
    between 2007 and 2012. Overall, the British Museum consistently attracted 
    the highest number of visitors, while the Science Museum had the lowest 
    attendance throughout the period. The National Gallery showed steady growth 
    over the six-year period. In detail, the British Museum started with 
    approximately 5.5 million visitors in 2007 and reached 6.2 million by 2012.
    """,
    """
    The process diagram shows how paper is recycled. First, waste paper is 
    collected from various sources. Next, it is sorted to remove any non-paper 
    materials. The sorted paper is then pulped by adding water and chemicals. 
    After cleaning and screening, the pulp is bleached to remove ink. Finally, 
    the clean pulp is formed into new paper sheets.
    """
]

SAMPLE_TASK2_TEXTS = [
    """
    I strongly believe that university education should be free for all students. 
    In my opinion, education is a fundamental right that should not be limited by 
    financial circumstances. Free university education would create equal 
    opportunities for all members of society, regardless of their economic 
    background. However, critics argue that free education would be too expensive 
    for governments to fund. Nevertheless, I think the long-term benefits to 
    society outweigh the costs.
    """,
    """
    Some people think that children should start learning a foreign language at 
    primary school, while others believe it is better to wait until secondary 
    school. On one hand, supporters of early language learning argue that young 
    children have a natural ability to acquire languages quickly. On the other 
    hand, those who favor later introduction claim that children should first 
    master their native language. In my view, both approaches have merit, but 
    early exposure to foreign languages provides greater long-term advantages.
    """
]


class TestTaskTypeDetectorWithSamples:
    """Test TaskTypeDetector with realistic IELTS samples"""
    
    def setup_method(self):
        self.detector = TaskTypeDetector()
    
    @pytest.mark.parametrize("text", SAMPLE_TASK1_TEXTS)
    def test_detect_task1_samples(self, text):
        """Test Task 1 detection with sample texts"""
        result = self.detector.detect_task_type(text)
        
        assert result.detected_type == TaskType.TASK_1
        assert result.confidence_score > 0.5
    
    @pytest.mark.parametrize("text", SAMPLE_TASK2_TEXTS)
    def test_detect_task2_samples(self, text):
        """Test Task 2 detection with sample texts"""
        result = self.detector.detect_task_type(text)
        
        assert result.detected_type == TaskType.TASK_2
        assert result.confidence_score > 0.5


class TestTextValidatorWithSamples:
    """Test TextValidator with realistic IELTS samples"""
    
    def setup_method(self):
        self.validator = TextValidator()
    
    @pytest.mark.parametrize("text", SAMPLE_TASK1_TEXTS + SAMPLE_TASK2_TEXTS)
    def test_validate_ielts_samples(self, text):
        """Test validation with sample IELTS texts"""
        with patch('src.services.text_processor.detect') as mock_detect:
            mock_detect.return_value = 'en'
            
            result = self.validator.validate_submission(text)
            
            assert result.is_valid
            assert len(result.errors) == 0
            assert result.word_count >= 50
            assert result.detected_language == 'en'