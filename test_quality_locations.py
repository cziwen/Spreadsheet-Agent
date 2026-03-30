#!/usr/bin/env python3
"""Test script to verify quality agent location tracking improvements."""

import pandas as pd
import numpy as np
from agent.subagents.quality_agent import QualityAgent
from agent.core.llm_client import LLMClient
from agent.core.data_engine import DataEngine
import os
from dotenv import load_dotenv

load_dotenv()

def test_quality_agent_locations():
    """Test that quality agent reports row locations for all issues."""

    # Create test data with various issues
    test_df = pd.DataFrame({
        'id': [1, 2, 2, 4, 5, 6, 7, 8, 9, 10],  # Row 2 has duplicate ID
        'email': ['a@test.com', None, 'c@test.com', 'd@test.com', None, 'f@test.com',
                  'g@test.com', 'h@test.com', 'i@test.com', 'j@test.com'],  # Rows 1, 4 have None
        'date': ['2024-01-01', '2024/01/02', '2024-01-03', '01-04-2024', '2024-01-05',
                '2024/01/06', '2024-01-07', '2024-01-08', '2024-01-09', '2024-01-10'],  # Different formats
        'amount': [100, 200, 300, 400, 5000, 600, 700, 800, 900, 1000]  # Row 4 is outlier
    })

    # Initialize quality agent
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("❌ GOOGLE_API_KEY not set, skipping test")
        return

    llm = LLMClient(api_key=api_key)
    # Create a minimal data engine for initialization
    data_engine = DataEngine(workbook_path="data/demo_workbook")

    agent = QualityAgent(llm, data_engine)
    workbook = {'test_table': test_df}

    # Run quality checks
    result = agent.execute("Check the test table", workbook)

    print("\n" + "="*80)
    print("QUALITY AGENT TEST RESULTS")
    print("="*80)

    print(f"\nTable: {result['table']}")
    print(f"Quality Score: {result['quality_score']:.0f}/100")
    print(f"Total Issues: {result['total_issues']}")

    print("\n" + "-"*80)
    print("ISSUES WITH LOCATION INFORMATION")
    print("-"*80)

    for i, issue in enumerate(result.get('issues', [])[:10], 1):
        print(f"\n{i}. {issue['type'].upper()} [Severity: {issue['severity']}]")
        print(f"   Description: {issue['description']}")

        # Show locations
        if 'locations' in issue:
            print(f"   📍 Locations: {issue['locations']}")

        if 'row_indices' in issue:
            print(f"   Row indices: {issue['row_indices']}")

        if 'total_affected_rows' in issue:
            print(f"   Total affected rows: {issue['total_affected_rows']}")

        # Show sample rows
        if 'sample_rows' in issue and issue['sample_rows']:
            print(f"   Sample rows:")
            for sample in issue['sample_rows'][:2]:
                row = sample.get('row')
                if 'value' in sample:
                    print(f"     • Row {row}: {sample['value']} ({sample.get('deviation', '')})")
                elif 'format' in sample:
                    print(f"     • Row {row}: {sample['value']} [{sample['format']}]")
                elif 'id_value' in sample:
                    print(f"     • Row {row}: ID={sample['id_value']}")
                else:
                    print(f"     • Row {row}: {sample}")

        # Show bounds for outliers
        if 'bounds' in issue:
            bounds = issue['bounds']
            print(f"   Valid range: [{bounds['lower']:.2f}, {bounds['upper']:.2f}]")

    print("\n" + "="*80)
    print("✅ TEST COMPLETED SUCCESSFULLY")
    print("="*80)

    # Verify that all issues have location data
    issues = result.get('issues', [])
    missing_locations = []

    for issue in issues:
        if 'locations' not in issue and 'row_indices' not in issue:
            missing_locations.append(issue['type'])

    if missing_locations:
        print(f"\n⚠️  Warning: {len(missing_locations)} issues missing location data: {missing_locations}")
    else:
        print(f"\n✓ All {len(issues)} issues have location information!")

if __name__ == "__main__":
    test_quality_agent_locations()
