"""Context management for workbook-specific conversation and metadata."""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any


class ContextManager:
    """Manages per-workbook context and session conversations."""

    def __init__(self, workbook_path: str):
        """Initialize context manager.

        Args:
            workbook_path: Path to workbook directory
        """
        self.workbook_path = Path(workbook_path)
        self.context_dir = self.workbook_path / "context"
        self.sessions_dir = self.context_dir / "sessions"
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Create context directories if they don't exist."""
        self.context_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    # ============================================================================
    # Workbook Context Management
    # ============================================================================

    def load_workbook_context(self) -> Dict[str, Any]:
        """Load persistent workbook context.

        Returns:
            Workbook context dictionary with metadata, data_dictionary, etc.
        """
        context_file = self.context_dir / "workbook_context.json"

        if context_file.exists():
            try:
                with open(context_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading workbook context: {e}")

        # Return default structure if file doesn't exist
        return self._get_default_context()

    def save_workbook_context(self, context: Dict[str, Any]) -> None:
        """Save workbook context to file.

        Args:
            context: Workbook context dictionary
        """
        context_file = self.context_dir / "workbook_context.json"

        try:
            with open(context_file, "w") as f:
                json.dump(context, f, indent=2, default=str)
        except Exception as e:
            print(f"Error saving workbook context: {e}")

    def update_workbook_metadata(self, key: str, value: Any) -> None:
        """Update a single metadata field in workbook context.

        Args:
            key: Metadata key (e.g., 'business_domain', 'description')
            value: Metadata value
        """
        context = self.load_workbook_context()

        if "metadata" not in context:
            context["metadata"] = {}

        context["metadata"][key] = value
        context["last_updated"] = datetime.now().isoformat()

        self.save_workbook_context(context)

    def _get_default_context(self) -> Dict[str, Any]:
        """Get default context structure.

        Returns:
            Default workbook context
        """
        return {
            "workbook_id": self.workbook_path.name,
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "metadata": {
                "business_domain": "Not specified",
                "description": "Not specified",
                "purpose": "Not specified",
            },
            "data_dictionary": {},
            "learned_patterns": {
                "common_joins": [],
                "frequent_queries": [],
            },
            "user_corrections": [],
        }

    # ============================================================================
    # Session Management
    # ============================================================================

    def create_session(self) -> str:
        """Create a new session.

        Returns:
            Session ID
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S%f")[:-3]  # Include milliseconds
        session_id = f"session_{timestamp}"

        session_data = {
            "session_id": session_id,
            "workbook_id": self.workbook_path.name,
            "started_at": datetime.now().isoformat(),
            "last_activity": datetime.now().isoformat(),
            "conversation_history": [],
            "current_focus": {
                "active_tables": [],
                "last_result_table": None,
                "applied_filters": [],
            },
        }

        session_file = self.sessions_dir / f"{session_id}.json"

        try:
            with open(session_file, "w") as f:
                json.dump(session_data, f, indent=2, default=str)
        except Exception as e:
            print(f"Error creating session: {e}")

        return session_id

    def load_session(self, session_id: str) -> Dict[str, Any]:
        """Load session data.

        Args:
            session_id: Session ID

        Returns:
            Session data dictionary
        """
        session_file = self.sessions_dir / f"{session_id}.json"

        if session_file.exists():
            try:
                with open(session_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading session {session_id}: {e}")

        return {}

    def save_session(self, session_id: str, context: Dict[str, Any]) -> None:
        """Save session data.

        Args:
            session_id: Session ID
            context: Session context dictionary
        """
        session_file = self.sessions_dir / f"{session_id}.json"

        context["last_activity"] = datetime.now().isoformat()

        try:
            with open(session_file, "w") as f:
                json.dump(context, f, indent=2, default=str)
        except Exception as e:
            print(f"Error saving session {session_id}: {e}")

    def list_sessions(self, limit: int = 10) -> List[Dict]:
        """List recent sessions.

        Args:
            limit: Maximum number of sessions to return

        Returns:
            List of session metadata dictionaries
        """
        sessions = []

        try:
            session_files = sorted(self.sessions_dir.glob("*.json"), reverse=True)

            for session_file in session_files[:limit]:
                try:
                    with open(session_file, "r") as f:
                        session = json.load(f)
                        sessions.append({
                            "session_id": session.get("session_id"),
                            "started_at": session.get("started_at"),
                            "last_activity": session.get("last_activity"),
                            "query_count": len(session.get("conversation_history", [])),
                        })
                except Exception:
                    continue

        except Exception as e:
            print(f"Error listing sessions: {e}")

        return sessions

    # ============================================================================
    # Conversation History
    # ============================================================================

    def add_to_history(
        self,
        session_id: str,
        query: str,
        result: Dict[str, Any],
    ) -> None:
        """Add query result to session conversation history.

        Args:
            session_id: Session ID
            query: User query text
            result: Query result dictionary
        """
        session = self.load_session(session_id)

        if not session:
            return

        history_entry = {
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "query_type": result.get("type", "unknown"),
            "tables_used": result.get("tables_used", []),
            "result_summary": self._summarize_result(result),
            "status": "success" if result.get("type") != "error" else "error",
            "error_message": result.get("error") if result.get("type") == "error" else None,
        }

        if "conversation_history" not in session:
            session["conversation_history"] = []

        session["conversation_history"].append(history_entry)

        self.save_session(session_id, session)

    def get_recent_history(self, session_id: str, limit: int = 5) -> List[Dict]:
        """Get recent queries from session history.

        Args:
            session_id: Session ID
            limit: Maximum number of recent queries to return

        Returns:
            List of recent query records
        """
        session = self.load_session(session_id)

        if not session:
            return []

        history = session.get("conversation_history", [])
        return history[-limit:] if history else []

    def get_conversation_summary(self, session_id: str) -> str:
        """Generate a natural language summary of the conversation.

        Args:
            session_id: Session ID

        Returns:
            Conversation summary string
        """
        history = self.get_recent_history(session_id, limit=10)

        if not history:
            return "No conversation history yet."

        lines = []
        for i, entry in enumerate(history, 1):
            status = "✓" if entry["status"] == "success" else "✗"
            lines.append(f"{i}. {status} {entry['query']}")
            if entry.get("result_summary"):
                lines.append(f"   Result: {entry['result_summary']}")

        return "\n".join(lines)

    # ============================================================================
    # Context Learning
    # ============================================================================

    def record_correction(
        self,
        query: str,
        correction: str,
        explanation: str,
    ) -> None:
        """Record user correction for learning.

        Args:
            query: Original query
            correction: Corrected query or output
            explanation: User's explanation
        """
        context = self.load_workbook_context()

        if "user_corrections" not in context:
            context["user_corrections"] = []

        context["user_corrections"].append({
            "timestamp": datetime.now().isoformat(),
            "original_query": query,
            "correction": correction,
            "explanation": explanation,
        })

        self.save_workbook_context(context)

    def record_query_pattern(self, tables: List[str], join_key: str) -> None:
        """Record learned query pattern (common join).

        Args:
            tables: List of table names involved in join
            join_key: Column used for joining
        """
        context = self.load_workbook_context()

        if "learned_patterns" not in context:
            context["learned_patterns"] = {}

        if "common_joins" not in context["learned_patterns"]:
            context["learned_patterns"]["common_joins"] = []

        pattern = {"tables": sorted(tables), "join_key": join_key}

        # Check if pattern already exists
        joins = context["learned_patterns"]["common_joins"]
        if pattern not in joins:
            joins.append(pattern)
            self.save_workbook_context(context)

    def record_frequent_query(self, query: str) -> None:
        """Record frequently used query pattern.

        Args:
            query: Query text
        """
        context = self.load_workbook_context()

        if "learned_patterns" not in context:
            context["learned_patterns"] = {}

        if "frequent_queries" not in context["learned_patterns"]:
            context["learned_patterns"]["frequent_queries"] = []

        queries = context["learned_patterns"]["frequent_queries"]

        # Keep unique queries, most recent first
        if query not in queries:
            queries.insert(0, query)
            # Keep only last 20 frequent queries
            context["learned_patterns"]["frequent_queries"] = queries[:20]
            self.save_workbook_context(context)

    # ============================================================================
    # Utilities
    # ============================================================================

    def _summarize_result(self, result: Dict[str, Any]) -> str:
        """Generate a brief summary of query result.

        Args:
            result: Query result dictionary

        Returns:
            Summary string
        """
        if result.get("type") == "error":
            return f"Error: {result.get('error', 'Unknown error')}"

        if result.get("type") == "meta":
            return "Returned capability information"

        if result.get("type") == "quality":
            summary = result.get("summary", "")
            if summary:
                # Take first 100 characters
                return summary[:100] + "..." if len(summary) > 100 else summary
            return "Data quality check completed"

        if result.get("type") == "scenario":
            return f"Scenario created: {result.get('scenario_name', 'Unknown')}"

        if result.get("type") == "cross_table":
            # Try to get row count from result
            if "result" in result and hasattr(result["result"], "__len__"):
                return f"Returned {len(result['result'])} rows"
            return "Query executed successfully"

        return "Query executed"

    def update_session_focus(
        self,
        session_id: str,
        active_tables: List[str],
        last_result_table: Optional[str] = None,
        applied_filters: Optional[List[str]] = None,
    ) -> None:
        """Update the current focus of a session.

        Args:
            session_id: Session ID
            active_tables: List of currently active tables
            last_result_table: Name of last result table
            applied_filters: List of applied filters
        """
        session = self.load_session(session_id)

        if not session:
            return

        session["current_focus"] = {
            "active_tables": active_tables,
            "last_result_table": last_result_table,
            "applied_filters": applied_filters or [],
        }

        self.save_session(session_id, session)
