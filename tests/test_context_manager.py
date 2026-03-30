"""Tests for ContextManager and context management system."""

import json
import tempfile
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.core.context_manager import ContextManager


class TestContextManager:
    """Test suite for ContextManager class."""

    @staticmethod
    def setup_test_workbook():
        """Create a temporary test workbook directory."""
        temp_dir = tempfile.mkdtemp()
        return temp_dir

    def test_context_manager_initialization(self):
        """Test ContextManager initialization and directory creation."""
        workbook_path = self.setup_test_workbook()
        ctx_mgr = ContextManager(workbook_path)

        assert ctx_mgr.workbook_path == Path(workbook_path)
        assert (ctx_mgr.context_dir / "sessions").exists()
        print("✓ ContextManager initialization test passed")

    def test_workbook_context_persistence(self):
        """Test saving and loading workbook context."""
        workbook_path = self.setup_test_workbook()
        ctx_mgr = ContextManager(workbook_path)

        # Update metadata
        ctx_mgr.update_workbook_metadata("business_domain", "E-commerce")
        ctx_mgr.update_workbook_metadata("description", "Customer and order data")

        # Load and verify
        wb_ctx = ctx_mgr.load_workbook_context()
        assert wb_ctx["metadata"]["business_domain"] == "E-commerce"
        assert wb_ctx["metadata"]["description"] == "Customer and order data"
        print("✓ Workbook context persistence test passed")

    def test_session_creation(self):
        """Test session creation."""
        workbook_path = self.setup_test_workbook()
        ctx_mgr = ContextManager(workbook_path)

        session_id = ctx_mgr.create_session()
        assert session_id is not None
        assert session_id.startswith("session_")

        # Verify session file exists
        session_file = ctx_mgr.sessions_dir / f"{session_id}.json"
        assert session_file.exists()
        print("✓ Session creation test passed")

    def test_session_loading(self):
        """Test loading session data."""
        workbook_path = self.setup_test_workbook()
        ctx_mgr = ContextManager(workbook_path)

        # Create session
        session_id = ctx_mgr.create_session()

        # Load it back
        session = ctx_mgr.load_session(session_id)
        assert session["session_id"] == session_id
        assert "conversation_history" in session
        assert "current_focus" in session
        print("✓ Session loading test passed")

    def test_conversation_history(self):
        """Test adding and retrieving conversation history."""
        workbook_path = self.setup_test_workbook()
        ctx_mgr = ContextManager(workbook_path)

        # Create session
        session_id = ctx_mgr.create_session()

        # Add queries
        result1 = {"type": "cross_table", "tables_used": ["customers"]}
        result2 = {"type": "cross_table", "tables_used": ["orders"]}

        ctx_mgr.add_to_history(session_id, "Query 1", result1)
        ctx_mgr.add_to_history(session_id, "Query 2", result2)

        # Retrieve history
        history = ctx_mgr.get_recent_history(session_id, limit=10)
        assert len(history) == 2
        assert history[0]["query"] == "Query 1"
        assert history[1]["query"] == "Query 2"
        print("✓ Conversation history test passed")

    def test_conversation_history_limit(self):
        """Test that get_recent_history respects the limit parameter."""
        workbook_path = self.setup_test_workbook()
        ctx_mgr = ContextManager(workbook_path)

        # Create session
        session_id = ctx_mgr.create_session()

        # Add 10 queries
        for i in range(10):
            result = {"type": "cross_table"}
            ctx_mgr.add_to_history(session_id, f"Query {i+1}", result)

        # Get only last 3
        history = ctx_mgr.get_recent_history(session_id, limit=3)
        assert len(history) == 3
        assert history[0]["query"] == "Query 8"
        assert history[2]["query"] == "Query 10"
        print("✓ Conversation history limit test passed")

    def test_record_query_pattern(self):
        """Test recording learned query patterns."""
        workbook_path = self.setup_test_workbook()
        ctx_mgr = ContextManager(workbook_path)

        # Record patterns
        ctx_mgr.record_query_pattern(["customers", "orders"], "customer_id")
        ctx_mgr.record_query_pattern(["orders", "products"], "product_id")

        # Load and verify
        wb_ctx = ctx_mgr.load_workbook_context()
        joins = wb_ctx["learned_patterns"]["common_joins"]
        assert len(joins) == 2
        assert {"tables": ["customers", "orders"], "join_key": "customer_id"} in joins
        print("✓ Query pattern recording test passed")

    def test_record_frequent_query(self):
        """Test recording frequently used queries."""
        workbook_path = self.setup_test_workbook()
        ctx_mgr = ContextManager(workbook_path)

        # Record queries
        ctx_mgr.record_frequent_query("Show me total sales by customer")
        ctx_mgr.record_frequent_query("List orders with amount > 1000")

        # Load and verify
        wb_ctx = ctx_mgr.load_workbook_context()
        queries = wb_ctx["learned_patterns"]["frequent_queries"]
        assert len(queries) == 2
        assert "Show me total sales by customer" in queries
        print("✓ Frequent query recording test passed")

    def test_record_correction(self):
        """Test recording user corrections."""
        workbook_path = self.setup_test_workbook()
        ctx_mgr = ContextManager(workbook_path)

        # Record correction
        ctx_mgr.record_correction(
            query="List customers",
            correction="Show customers with more than 5 orders",
            explanation="User clarified they only want customers with multiple orders"
        )

        # Load and verify
        wb_ctx = ctx_mgr.load_workbook_context()
        corrections = wb_ctx["user_corrections"]
        assert len(corrections) == 1
        assert corrections[0]["original_query"] == "List customers"
        print("✓ User correction recording test passed")

    def test_session_focus_update(self):
        """Test updating session focus."""
        workbook_path = self.setup_test_workbook()
        ctx_mgr = ContextManager(workbook_path)

        # Create session
        session_id = ctx_mgr.create_session()

        # Update focus
        ctx_mgr.update_session_focus(
            session_id,
            active_tables=["customers", "orders"],
            last_result_table="query_result",
            applied_filters=["amount > 500"]
        )

        # Load and verify
        session = ctx_mgr.load_session(session_id)
        focus = session["current_focus"]
        assert focus["active_tables"] == ["customers", "orders"]
        assert focus["last_result_table"] == "query_result"
        assert "amount > 500" in focus["applied_filters"]
        print("✓ Session focus update test passed")

    def test_list_sessions(self):
        """Test listing recent sessions."""
        import time
        workbook_path = self.setup_test_workbook()
        ctx_mgr = ContextManager(workbook_path)

        # Create multiple sessions
        session_ids = []
        for i in range(3):
            session_id = ctx_mgr.create_session()
            session_ids.append(session_id)

            # Add some queries to each
            for j in range(i + 1):
                result = {"type": "cross_table"}
                ctx_mgr.add_to_history(session_id, f"Query {j+1}", result)

            # Small delay to ensure different timestamps
            time.sleep(0.01)

        # List sessions
        sessions = ctx_mgr.list_sessions(limit=10)
        assert len(sessions) >= 3, f"Expected at least 3 sessions, got {len(sessions)}"
        assert all("session_id" in s for s in sessions)
        assert all("started_at" in s for s in sessions)
        print("✓ Session listing test passed")

    def test_error_handling(self):
        """Test error handling in context manager."""
        workbook_path = self.setup_test_workbook()
        ctx_mgr = ContextManager(workbook_path)

        # Try to load non-existent session
        session = ctx_mgr.load_session("non_existent_session")
        assert session == {}

        # Try to get history for non-existent session
        history = ctx_mgr.get_recent_history("non_existent_session")
        assert history == []

        print("✓ Error handling test passed")


def run_tests():
    """Run all tests."""
    test_suite = TestContextManager()
    tests = [
        ("Context Manager Initialization", test_suite.test_context_manager_initialization),
        ("Workbook Context Persistence", test_suite.test_workbook_context_persistence),
        ("Session Creation", test_suite.test_session_creation),
        ("Session Loading", test_suite.test_session_loading),
        ("Conversation History", test_suite.test_conversation_history),
        ("Conversation History Limit", test_suite.test_conversation_history_limit),
        ("Record Query Pattern", test_suite.test_record_query_pattern),
        ("Record Frequent Query", test_suite.test_record_frequent_query),
        ("Record User Correction", test_suite.test_record_correction),
        ("Session Focus Update", test_suite.test_session_focus_update),
        ("List Sessions", test_suite.test_list_sessions),
        ("Error Handling", test_suite.test_error_handling),
    ]

    passed = 0
    failed = 0

    print("\n" + "="*60)
    print("Running Context Manager Tests")
    print("="*60 + "\n")

    for test_name, test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"✗ {test_name} test failed: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test_name} test error: {e}")
            failed += 1

    print("\n" + "="*60)
    print(f"Tests passed: {passed}/{len(tests)}")
    if failed > 0:
        print(f"Tests failed: {failed}")
    print("="*60 + "\n")

    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
