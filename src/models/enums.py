"""
Enumeration types for IELTS Writing Bot - simplified version without database dependencies.
"""
from enum import Enum


class TaskType(Enum):
    """Enumeration for IELTS task types."""
    TASK_1 = "TASK_1"
    TASK_2 = "TASK_2"
