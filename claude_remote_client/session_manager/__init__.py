"""
Session manager module for the Claude Remote Client.

This module handles session lifecycle, project management, and session state persistence.
"""

from .session_manager import SessionManager
from .project_manager import ProjectManager

__all__ = [
    "SessionManager",
    "ProjectManager"
]