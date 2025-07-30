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
        
        # Helper function to create score bars
        def create_score_bar(score: float) -> str:
            filled = int(score)
            empty = 9 - filled
            return "🟢" * filled + "⚪" * empty
        
        # Helper function to get score emoji
        def get_score_emoji(score: float) -> str:
            if score >= 7.0:
                return "🟢"
            elif score >= 5.5:
                return "🟡"
            else:
                return "🔴"
        
        # Format criterion names
        def format_criterion_name(key: str) -> str:
            mapping = {
                'task_achievement': '🎯 Task Achievement',
                'coherence_cohesion': '🔗 Coherence & Cohesion',
                'lexical_resource': '📖 Lexical Resource',
                'grammatical_accuracy': '📝 Grammatical Accuracy'
            }
            return mapping.get(key, key.replace('_', ' ').title())
        
        # Format the main result
        text = f"""
{task_emoji} *IELTS Writing {task_name} Assessment*


� *OVERALL BAND SCORE*
{get_score_emoji(assessment.overall_band_score)} *{assessment.overall_band_score:.1f}/9.0*


� *DETAILED BREAKDOWN*

{get_score_emoji(assessment.task_achievement_score)} *Task Achievement:* `{assessment.task_achievement_score:.1f}/9`
{create_score_bar(assessment.task_achievement_score)}

{get_score_emoji(assessment.coherence_cohesion_score)} *Coherence & Cohesion:* `{assessment.coherence_cohesion_score:.1f}/9`
{create_score_bar(assessment.coherence_cohesion_score)}

{get_score_emoji(assessment.lexical_resource_score)} *Lexical Resource:* `{assessment.lexical_resource_score:.1f}/9`
{create_score_bar(assessment.lexical_resource_score)}

{get_score_emoji(assessment.grammatical_accuracy_score)} *Grammatical Accuracy:* `{assessment.grammatical_accuracy_score:.1f}/9`
{create_score_bar(assessment.grammatical_accuracy_score)}


� *EXAMINER FEEDBACK*

{assessment.detailed_feedback}


💡 *KEY IMPROVEMENT AREAS*"""
        
        for i, suggestion in enumerate(assessment.improvement_suggestions, 1):
            text += f"\n\n{i}️⃣ {suggestion}"
        
        text += f"""


📝 *DETAILED SCORE JUSTIFICATIONS*"""
        
        for criterion, justification in assessment.score_justifications.items():
            formatted_name = format_criterion_name(criterion)
            text += f"\n\n*{formatted_name}*\n_{justification}_"
        
        text += f"""


🎉 *Keep Practicing!*

🆓 *Completely FREE* • No limits • No registration
🚀 Ready for another assessment? Just send your next writing!

⭐ *Tip:* Focus on the improvement areas above for your next submission
"""
        
        return FormattedResult(text=text, parse_mode="Markdown")
    
    def format_error_message(self, error_message: str) -> FormattedResult:
        """Format an error message for display."""
        text = f"""
❌ *Assessment Error*


{error_message}


🔄 *What to do next:*

1️⃣ Wait a moment and try again
2️⃣ Check your writing length (minimum 150 words for Task 1, 250 for Task 2)
3️⃣ Make sure your text is in English

💬 Need help? Contact @bnutfilloyev
"""
        return FormattedResult(text=text, parse_mode="Markdown")
