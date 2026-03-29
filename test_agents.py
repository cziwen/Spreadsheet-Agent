#!/usr/bin/env python3
"""Test script to verify agent architecture without LLM calls."""

import sys
import os
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from agent.core.data_engine import DataEngine, SemanticAnalyzer


def test_data_engine():
    """Test data engine loading and operations."""
    print("=" * 60)
    print("Testing Data Engine")
    print("=" * 60 + "\n")

    engine = DataEngine(workbook_path="data/demo_workbook")
    tables = engine.load_workbook()

    print(f"✓ Loaded {len(tables)} tables:")
    for table_name, df in tables.items():
        print(f"  • {table_name}: {len(df)} rows × {len(df.columns)} columns")

    print()
    return engine, tables


def test_semantic_analyzer(tables):
    """Test semantic analysis capabilities."""
    print("=" * 60)
    print("Testing Semantic Analyzer")
    print("=" * 60 + "\n")

    analyzer = SemanticAnalyzer()

    # Analyze orders table
    orders_df = tables["orders"]
    print("Analyzing 'orders' table:")
    print(f"  Columns: {list(orders_df.columns)}\n")

    # Test column type inference
    for col in orders_df.columns:
        semantic_type = analyzer.analyze_column_type(col, orders_df[col])
        print(f"  • {col}: {semantic_type}")

    print()

    # Test relationship detection
    print("Finding relationships between tables:")
    relationships = analyzer.find_relationships(tables)

    if relationships:
        for rel in relationships[:3]:
            print(
                f"  • {rel['left_table']}.{rel['join_key']} = {rel['right_table']}.{rel['join_key']}"
                f" ({rel['overlap_count']} overlapping values)"
            )
    else:
        print("  No relationships found")

    print()
    return analyzer


def test_quality_checks(tables):
    """Test data quality checks."""
    print("=" * 60)
    print("Testing Data Quality Checks")
    print("=" * 60 + "\n")

    df = tables["orders"]

    # Missing values
    print("Missing values check:")
    for col in df.columns:
        null_count = df[col].isnull().sum()
        if null_count == 0:
            print(f"  ✓ {col}: No missing values")
        else:
            print(f"  ⚠ {col}: {null_count} missing values ({null_count/len(df)*100:.1f}%)")

    print()

    # Numeric columns
    print("Numeric columns (for potential aggregation):")
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    for col in numeric_cols:
        print(f"  • {col}: min={df[col].min():.2f}, max={df[col].max():.2f}, mean={df[col].mean():.2f}")

    print()


def test_agent_architecture():
    """Verify agent class imports work."""
    print("=" * 60)
    print("Testing Agent Architecture")
    print("=" * 60 + "\n")

    try:
        from agent.lead_agent import LeadAgent
        print("✓ Lead Agent importable")

        from agent.subagents.cross_table_agent import CrossTableAgent
        print("✓ Cross-Table Agent importable")

        from agent.subagents.quality_agent import QualityAgent
        print("✓ Quality Agent importable")

        from agent.subagents.scenario_agent import ScenarioAgent
        print("✓ Scenario Agent importable")

        print("\nAgent Architecture:")
        print("  Lead Agent")
        print("    ├─ Cross-Table Agent")
        print("    ├─ Quality Agent")
        print("    └─ Scenario Agent")

        print()
        return True

    except Exception as e:
        print(f"✗ Error importing agents: {e}")
        return False


def main():
    """Run all tests."""
    print("\n")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║         Spreadsheet Agent - Architecture Test              ║")
    print("╚════════════════════════════════════════════════════════════╝\n")

    # Test 1: Data Engine
    engine, tables = test_data_engine()

    # Test 2: Semantic Analyzer
    analyzer = test_semantic_analyzer(tables)

    # Test 3: Quality Checks
    test_quality_checks(tables)

    # Test 4: Agent Architecture
    success = test_agent_architecture()

    # Summary
    print("=" * 60)
    print("Summary")
    print("=" * 60 + "\n")

    if success:
        print("✓ All component tests passed!")
        print("\nNext steps:")
        print("  1. Set GOOGLE_API_KEY in .env file")
        print("  2. Run: python cli.py query \"your query\"")
        print("  3. Or run demo: python cli.py demo")
    else:
        print("✗ Some tests failed. Check errors above.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
