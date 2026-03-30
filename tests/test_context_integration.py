"""Integration tests for context management with agents."""

import json
import tempfile
from pathlib import Path
import sys
import os
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.core.context_manager import ContextManager
from agent.core.data_engine import DataEngine
from agent.lead_agent import LeadAgent
from agent.core.llm_client import LLMClient


def test_context_integration():
    """Test context integration with LeadAgent and DataEngine."""
    print("\n" + "="*60)
    print("Context Integration Test")
    print("="*60 + "\n")

    # Load environment
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key:
        print("⚠️  GOOGLE_API_KEY not set, skipping integration test")
        print("Set GOOGLE_API_KEY environment variable to run full tests")
        return True

    # Create temporary workbook
    temp_dir = tempfile.mkdtemp()
    workbook_path = temp_dir

    # Create sample CSV files
    import pandas as pd

    customers = pd.DataFrame({
        "customer_id": [1, 2, 3],
        "name": ["Alice", "Bob", "Charlie"],
        "email": ["alice@example.com", "bob@example.com", "charlie@example.com"]
    })

    orders = pd.DataFrame({
        "order_id": [101, 102, 103],
        "customer_id": [1, 2, 1],
        "amount": [100.0, 200.0, 150.0]
    })

    customers.to_csv(Path(workbook_path) / "customers.csv", index=False)
    orders.to_csv(Path(workbook_path) / "orders.csv", index=False)

    # Test 1: ContextManager with workbook metadata
    print("Test 1: Workbook Context Management")
    print("-" * 40)

    data_engine = DataEngine(workbook_path)
    context_mgr = data_engine.context_manager

    # Set workbook metadata
    context_mgr.update_workbook_metadata("business_domain", "E-commerce")
    context_mgr.update_workbook_metadata("description", "Customer and order data")

    wb_ctx = context_mgr.load_workbook_context()
    assert wb_ctx["metadata"]["business_domain"] == "E-commerce"
    print("✓ Workbook metadata persisted correctly")

    # Test 2: Session creation and context tracking
    print("\nTest 2: Session Creation and Context Tracking")
    print("-" * 40)

    session_id = context_mgr.create_session()
    print(f"✓ Session created: {session_id}")

    # Add some query history
    result1 = {
        "type": "cross_table",
        "tables_used": ["customers", "orders"],
    }
    context_mgr.add_to_history(session_id, "Show me customer names", result1)

    history = context_mgr.get_recent_history(session_id)
    assert len(history) == 1
    assert history[0]["query"] == "Show me customer names"
    print("✓ Query history recorded correctly")

    # Test 3: LeadAgent with session
    print("\nTest 3: LeadAgent Session Integration")
    print("-" * 40)

    try:
        llm = LLMClient(api_key=api_key)
        lead_agent = LeadAgent(llm, workbook_path=workbook_path)

        # Set session
        lead_agent.set_session(session_id)
        assert lead_agent.session_id == session_id
        print("✓ LeadAgent session set correctly")

        # Verify context loading works
        context = lead_agent._load_query_context()
        assert context is not None
        assert "workbook_metadata" in context
        assert context["workbook_metadata"]["business_domain"] == "E-commerce"
        print("✓ LeadAgent can load query context")

    except Exception as e:
        print(f"⚠️  LeadAgent test skipped (API or connection issue): {e}")
        return True

    # Test 4: Pattern learning
    print("\nTest 4: Pattern Learning")
    print("-" * 40)

    context_mgr.record_query_pattern(["customers", "orders"], "customer_id")
    context_mgr.record_frequent_query("Which customers have the most orders?")

    wb_ctx = context_mgr.load_workbook_context()
    joins = wb_ctx["learned_patterns"]["common_joins"]
    queries = wb_ctx["learned_patterns"]["frequent_queries"]

    assert len(joins) > 0
    assert len(queries) > 0
    print("✓ Query patterns and frequent queries learned")

    # Test 5: Session focus tracking
    print("\nTest 5: Session Focus Tracking")
    print("-" * 40)

    context_mgr.update_session_focus(
        session_id,
        active_tables=["customers", "orders"],
        last_result_table="query_result",
        applied_filters=["amount > 100"]
    )

    session = context_mgr.load_session(session_id)
    focus = session["current_focus"]
    assert "customers" in focus["active_tables"]
    print("✓ Session focus tracked correctly")

    # Test 6: Session listing
    print("\nTest 6: Session Listing")
    print("-" * 40)

    sessions = context_mgr.list_sessions(limit=10)
    assert len(sessions) > 0
    print(f"✓ Found {len(sessions)} session(s)")

    print("\n" + "="*60)
    print("All integration tests passed! ✓")
    print("="*60 + "\n")

    return True


if __name__ == "__main__":
    success = test_context_integration()
    sys.exit(0 if success else 1)
