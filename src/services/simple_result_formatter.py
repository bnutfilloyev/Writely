"""
Simplified Result Formatter Service for IELTS Writing Evaluation

This module provides formatting services for displaying evaluation results,
band scores, and feedback in Telegram-friendly format without database dependencies.
"""

import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from datetime import datetime

from src.services.ai_assessment_engine import StructuredAssessment
from src.models.enums import TaskType

logger = logging.getLogger(__name__)


@dataclass
class FormattedResult:
    """Formatted result ready for display"""
    text: str
    parse_mode: str = "Markdown"


class ResultFormatter:
    """Formats AI assessment results for Telegram display"""
    
    def format_structured_assessment(self, assessment: StructuredAssessment, task_type: TaskType) -> FormattedResult:
        """
        Format a structured assessment into Telegram-friendly text.
        
        Args:
            assessment: StructuredAssessment from AI evaluation
            task_type: Task 1 or Task 2
            
        Returns:
            FormattedResult with formatted text
        """
        task_emoji = "📊" if task_type == TaskType.TASK_1 else "📝"
        task_name = "Task 1" if task_type == TaskType.TASK_1 else "Task 2"
        
        # Format the main result
        text = f"""
{task_emoji} *IELTS Writing {task_name} Assessment*

🎯 *Overall Band Score: {assessment.overall_band_score:.1f}*

📋 *Detailed Scores:*
• Task Achievement: {assessment.task_achievement_score:.1f}/9
• Coherence & Cohesion: {assessment.coherence_cohesion_score:.1f}/9  
• Lexical Resource: {assessment.lexical_resource_score:.1f}/9
• Grammatical Accuracy: {assessment.grammatical_accuracy_score:.1f}/9

💬 *Feedback:*
{assessment.detailed_feedback}

💡 *Improvement Suggestions:*"""
        
        for i, suggestion in enumerate(assessment.improvement_suggestions, 1):
            text += f"\n{i}. {suggestion}"
        
        text += f"""

📝 *Score Justifications:*"""
        
        for criterion, justification in assessment.score_justifications.items():
            text += f"\n\n*{criterion}:* {justification}"
        
        text += f"""

🚀 *100% FREE* - No registration required!
✨ Submit another writing for instant feedback!
"""
        
        return FormattedResult(text=text, parse_mode="Markdown")
    
    def format_error_message(self, error_message: str) -> FormattedResult:
        """Format an error message for display."""
        text = f"""
❌ **Assessment Error**

{error_message}

Please try again or contact support if the issue persists.
"""
        return FormattedResult(text=text, parse_mode="Markdown")
