"""
Result Formatter Service for IELTS Writing Evaluation

This module provides formatting services for displaying evaluation results,
band scores, feedback, and progress tracking in Telegram-friendly format.
"""

import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from datetime import datetime

from src.services.evaluation_service import EvaluationResult
from src.services.ai_assessment_engine import StructuredAssessment
from src.models.submission import TaskType

logger = logging.getLogger(__name__)


@dataclass
class FormattedResult:
    """Formatted evaluation result for display"""
    text: str
    parse_mode: str = "Markdown"


@dataclass
class ProgressSummary:
    """Summary of user progress for display"""
    trend_direction: str  # "improving", "declining", "stable"
    trend_value: float
    latest_score: float
    total_submissions: int
    average_score: float


class ResultFormatter:
    """
    Service for formatting evaluation results and progress tracking
    for display in Telegram bot interface
    """
    
    def __init__(self):
        self.score_emojis = {
            "excellent": "🟢",  # 7.0+
            "good": "🟡",       # 5.5-6.5
            "needs_work": "🔴"  # <5.5
        }
        
        self.task_type_display = {
            TaskType.TASK_1: "Task 1 (Charts/Graphs)",
            TaskType.TASK_2: "Task 2 (Essay)"
        }
    
    def format_evaluation_result(self, result: EvaluationResult) -> FormattedResult:
        """
        Format complete evaluation result for display
        
        Args:
            result: EvaluationResult from evaluation service
            
        Returns:
            FormattedResult with formatted text
        """
        if not result.success:
            return self._format_error_result(result)
        
        if not result.assessment:
            return FormattedResult(
                text="❌ No assessment data available",
                parse_mode="Markdown"
            )
        
        # Determine task type for display
        task_type = None
        if result.task_detection_result and result.task_detection_result.detected_type:
            task_type = result.task_detection_result.detected_type
        
        task_display = self.task_type_display.get(task_type, "IELTS Writing")
        
        # Build result text
        result_text = f"✅ **{task_display} Evaluation**\n\n"
        
        # Add band scores section
        result_text += self._format_band_scores(result.assessment)
        
        # Add detailed feedback
        result_text += self._format_detailed_feedback(result.assessment)
        
        # Add improvement suggestions
        result_text += self._format_improvement_suggestions(result.assessment)
        
        # Add submission metadata
        if result.validation_result:
            result_text += f"\n📏 **Word Count:** {result.validation_result.word_count} words"
        
        # Add task detection info if relevant
        if result.task_detection_result and result.task_detection_result.confidence_score < 0.8:
            result_text += f"\n🤖 **Detection Confidence:** {result.task_detection_result.confidence_score:.0%}"
        
        return FormattedResult(
            text=result_text,
            parse_mode="Markdown"
        )
    
    def format_history_display(
        self, 
        history: List[Dict[str, Any]], 
        user_name: str,
        total_submissions: int = None
    ) -> FormattedResult:
        """
        Format user history for display with progress tracking
        
        Args:
            history: List of evaluation history records
            user_name: Display name for the user
            total_submissions: Total number of submissions (optional)
            
        Returns:
            FormattedResult with formatted history
        """
        if not history:
            return self._format_no_history_message(user_name)
        
        # Calculate progress summary
        progress = self._calculate_progress_summary(history)
        
        # Build history text
        history_text = f"📊 **Band Score History - {user_name}**\n\n"
        
        # Add progress summary for multiple submissions
        if len(history) > 1:
            history_text += self._format_progress_summary(progress)
            history_text += "\n"
        
        # Add individual submissions
        history_text += "📝 **Recent Submissions:**\n\n"
        history_text += self._format_submission_list(history)
        
        # Add encouragement based on performance
        history_text += self._format_encouragement_message(progress)
        
        return FormattedResult(
            text=history_text,
            parse_mode="Markdown"
        )
    
    def format_progress_tracking(self, current_result: EvaluationResult, history: List[Dict[str, Any]]) -> str:
        """
        Format progress tracking information for current submission
        
        Args:
            current_result: Current evaluation result
            history: Previous submission history
            
        Returns:
            Formatted progress tracking text
        """
        if not history or not current_result.assessment:
            return ""
        
        current_score = current_result.assessment.overall_band_score
        
        # Compare with previous submission
        if len(history) >= 1:
            previous_score = history[0]['overall_band_score']
            improvement = current_score - previous_score
            
            if improvement > 0.2:
                return f"\n📈 **Progress:** +{improvement:.1f} from last submission! Great improvement!"
            elif improvement < -0.2:
                return f"\n📉 **Progress:** {improvement:.1f} from last submission. Keep practicing!"
            else:
                return f"\n➡️ **Progress:** Similar to last submission ({improvement:+.1f})"
        
        return ""
    
    def _format_error_result(self, result: EvaluationResult) -> FormattedResult:
        """Format error result for display"""
        error_text = f"❌ {result.error_message or 'Evaluation failed'}"
        
        # Add specific guidance based on error type
        if result.validation_result and not result.validation_result.is_valid:
            if result.validation_result.word_count < 50:
                error_text += "\n\n💡 **Tip:** IELTS essays should be at least 150 words for Task 1 and 250 words for Task 2."
            elif result.validation_result.word_count > 1000:
                error_text += "\n\n💡 **Tip:** Try to stay within typical IELTS word limits (150-200 for Task 1, 250-300 for Task 2)."
        
        if result.requires_task_clarification:
            error_text += "\n\n🤔 Please specify whether this is Task 1 (charts/graphs) or Task 2 (essay)."
        
        return FormattedResult(
            text=error_text,
            parse_mode="Markdown"
        )
    
    def _format_band_scores(self, assessment: StructuredAssessment) -> str:
        """Format band scores section"""
        overall_emoji = self._get_score_emoji(assessment.overall_band_score)
        
        scores_text = "📊 **Band Scores:**\n"
        scores_text += f"• Task Achievement/Response: **{assessment.task_achievement_score:.1f}**\n"
        scores_text += f"• Coherence and Cohesion: **{assessment.coherence_cohesion_score:.1f}**\n"
        scores_text += f"• Lexical Resource: **{assessment.lexical_resource_score:.1f}**\n"
        scores_text += f"• Grammatical Range & Accuracy: **{assessment.grammatical_accuracy_score:.1f}**\n\n"
        scores_text += f"🎯 **Overall Band Score: {overall_emoji} {assessment.overall_band_score:.1f}**\n\n"
        
        return scores_text
    
    def _format_detailed_feedback(self, assessment: StructuredAssessment) -> str:
        """Format detailed feedback section"""
        if not assessment.detailed_feedback:
            return ""
        
        feedback_text = "📝 **Detailed Feedback:**\n"
        feedback_text += f"{assessment.detailed_feedback}\n\n"
        
        return feedback_text
    
    def _format_improvement_suggestions(self, assessment: StructuredAssessment) -> str:
        """Format improvement suggestions section"""
        if not assessment.improvement_suggestions:
            return ""
        
        suggestions_text = "💡 **Improvement Suggestions:**\n"
        for i, suggestion in enumerate(assessment.improvement_suggestions, 1):
            suggestions_text += f"{i}. {suggestion}\n"
        
        return suggestions_text
    
    def _format_no_history_message(self, user_name: str) -> FormattedResult:
        """Format message when user has no history"""
        no_history_text = (
            f"📊 **Band Score History**\n\n"
            f"Hi {user_name}! You haven't submitted any writing for evaluation yet.\n\n"
            "🚀 **Get started by:**\n"
            "• Submitting a Task 1 writing (charts, graphs, tables)\n"
            "• Submitting a Task 2 essay (opinion, discussion, problem-solution)\n\n"
            "I'll provide detailed feedback and track your progress over time!"
        )
        
        return FormattedResult(
            text=no_history_text,
            parse_mode="Markdown"
        )
    
    def _format_progress_summary(self, progress: ProgressSummary) -> str:
        """Format progress summary section"""
        if progress.trend_direction == "improving":
            trend_emoji = "📈"
            trend_text = f"improving (+{progress.trend_value:.1f})"
        elif progress.trend_direction == "declining":
            trend_emoji = "📉"
            trend_text = f"declining ({progress.trend_value:.1f})"
        else:
            trend_emoji = "➡️"
            trend_text = "stable"
        
        summary_text = f"{trend_emoji} **Progress Trend:** {trend_text}\n"
        summary_text += f"📈 **Latest Score:** {progress.latest_score:.1f}\n"
        summary_text += f"📊 **Total Submissions:** {progress.total_submissions}\n"
        summary_text += f"📊 **Average Score:** {progress.average_score:.1f}\n"
        
        return summary_text
    
    def _format_submission_list(self, history: List[Dict[str, Any]]) -> str:
        """Format list of submissions"""
        submissions_text = ""
        
        for i, entry in enumerate(history, 1):
            # Format date
            submitted_date = entry['submitted_at']
            if isinstance(submitted_date, str):
                submitted_date = datetime.fromisoformat(submitted_date.replace('Z', '+00:00'))
            
            date_str = submitted_date.strftime("%b %d, %Y")
            
            # Task type display
            task_display = "Task 1" if entry['task_type'] == 'task_1' else "Task 2"
            
            # Score with emoji
            score = entry['overall_band_score']
            score_emoji = self._get_score_emoji(score)
            
            submissions_text += f"{i}. {score_emoji} **{task_display}** - Band {score:.1f}\n"
            submissions_text += f"   📅 {date_str} • {entry['word_count']} words\n\n"
        
        return submissions_text
    
    def _format_encouragement_message(self, progress: ProgressSummary) -> str:
        """Format encouragement message based on performance"""
        if progress.average_score >= 7.0:
            return "🎉 **Excellent work!** You're consistently achieving high band scores."
        elif progress.average_score >= 6.0:
            return "👍 **Good progress!** Keep practicing to reach higher band scores."
        else:
            return "💪 **Keep going!** Regular practice will help improve your scores."
    
    def _calculate_progress_summary(self, history: List[Dict[str, Any]]) -> ProgressSummary:
        """Calculate progress summary from history"""
        if not history:
            return ProgressSummary(
                trend_direction="stable",
                trend_value=0.0,
                latest_score=0.0,
                total_submissions=0,
                average_score=0.0
            )
        
        latest_score = history[0]['overall_band_score']
        total_submissions = len(history)
        average_score = sum(entry['overall_band_score'] for entry in history) / total_submissions
        
        # Calculate trend
        if len(history) > 1:
            oldest_score = history[-1]['overall_band_score']
            trend_value = latest_score - oldest_score
            
            if trend_value > 0.2:
                trend_direction = "improving"
            elif trend_value < -0.2:
                trend_direction = "declining"
            else:
                trend_direction = "stable"
        else:
            trend_direction = "stable"
            trend_value = 0.0
        
        return ProgressSummary(
            trend_direction=trend_direction,
            trend_value=trend_value,
            latest_score=latest_score,
            total_submissions=total_submissions,
            average_score=average_score
        )
    
    def _get_score_emoji(self, score: float) -> str:
        """Get emoji for score level"""
        if score >= 7.0:
            return self.score_emojis["excellent"]
        elif score >= 5.5:
            return self.score_emojis["good"]
        else:
            return self.score_emojis["needs_work"]