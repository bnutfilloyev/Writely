"""
Simplified models package without database dependencies.
"""

# Only export the enums that we need for the simplified version
from .enums import TaskType

__all__ = [
    "TaskType"
]