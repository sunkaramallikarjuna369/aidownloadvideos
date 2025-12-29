"""
In-memory state management for sessions and downloads.
This module provides a single source of truth for all shared state.
"""
from typing import Dict, Any

# In-memory storage for sessions
sessions: Dict[str, Any] = {}

# Download progress tracking
download_progress: Dict[str, Any] = {}

# Active download tasks
download_tasks: Dict[str, Any] = {}


def get_session(session_id: str) -> Dict[str, Any]:
    """Get a session by ID."""
    return sessions.get(session_id, {})


def set_session(session_id: str, data: Dict[str, Any]) -> None:
    """Set session data."""
    sessions[session_id] = data


def delete_session(session_id: str) -> bool:
    """Delete a session by ID."""
    if session_id in sessions:
        del sessions[session_id]
        return True
    return False


def get_progress(session_id: str) -> Dict[str, Any]:
    """Get download progress for a session."""
    return download_progress.get(session_id, {})


def set_progress(session_id: str, data: Dict[str, Any]) -> None:
    """Set download progress for a session."""
    download_progress[session_id] = data


def clear_progress(session_id: str) -> None:
    """Clear download progress for a session."""
    if session_id in download_progress:
        del download_progress[session_id]
