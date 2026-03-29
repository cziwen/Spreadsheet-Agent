"""Subagent for data quality diagnosis and repair."""

import json
from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np
from agent.core.llm_client import LLMClient
from agent.core.data_engine import DataEngine


class QualityAgent:
    """Agent for data quality scanning and repair suggestions."""

    def __init__(self, llm_client: LLMClient, data_engine: DataEngine):
        """Initialize quality agent.

        Args:
            llm_client: LLM client
            data_engine: Data engine
        """
        self.llm = llm_client
        self.data_engine = data_engine

    def execute(self, query: str, workbook: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """Execute data quality scan.

        Args:
            query: User query
            workbook: Dictionary of tables

        Returns:
            Result dictionary
        """
        print("🔍 Data Quality Agent\n")

        # Identify target table from query
        table_name = self._identify_target_table(query, workbook)

        if not table_name or table_name not in workbook:
            return {
                "type": "quality",
                "error": f"Could not find table for quality check",
                "query": query,
            }

        df = workbook[table_name]
        print(f"  • Target table: {table_name}")
        print(f"  • Rows: {len(df)}, Columns: {len(df.columns)}\n")

        # Run quality checks
        issues = []

        print("  • Checking for missing values...")
        missing = self._check_missing_values(df)
        issues.extend(missing)

        print("  • Checking for format inconsistencies...")
        format_issues = self._check_format_consistency(df)
        issues.extend(format_issues)

        print("  • Detecting outliers...")
        outliers = self._detect_outliers(df)
        issues.extend(outliers)

        print("  • Checking for duplicates...")
        duplicates = self._check_duplicates(df)
        issues.extend(duplicates)

        print(f"  • Issues found: {len(issues)}\n")

        # Generate repair suggestions
        repairs = self._suggest_repairs(issues, df, table_name)

        return {
            "type": "quality",
            "table": table_name,
            "total_rows": len(df),
            "total_columns": len(df.columns),
            "total_issues": len(issues),
            "issues": issues[:10],  # Top 10 issues
            "repairs": repairs[:5],  # Top 5 repairs
            "quality_score": max(0, 100 - len(issues) * 5),
        }

    def _identify_target_table(self, query: str, workbook: Dict[str, pd.DataFrame]) -> Optional[str]:
        """Identify which table to scan.

        Args:
            query: User query
            workbook: Dictionary of tables

        Returns:
            Table name or None
        """
        if not workbook:
            return None

        table_names = list(workbook.keys())

        # Use LLM to identify target table
        prompt = f"""
Available tables: {table_names}

User query: "{query}"

Which single table should be checked for data quality?
Return JSON:
{{
  "table": "table_name",
  "reasoning": "brief explanation"
}}

If no specific table is mentioned, pick the first table.
"""

        try:
            result = self.llm.call_structured(prompt)
            table = result.get("table")
            if table and table in table_names:
                return table
        except:
            pass

        # Fallback: return first table
        return table_names[0] if table_names else None

    def _check_missing_values(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Detect missing values.

        Args:
            df: DataFrame to check

        Returns:
            List of issues
        """
        issues = []

        for col in df.columns:
            null_count = df[col].isnull().sum()

            if null_count > 0:
                null_pct = null_count / len(df) * 100

                issues.append(
                    {
                        "type": "missing_values",
                        "severity": "high" if null_pct > 10 else "medium",
                        "column": col,
                        "count": int(null_count),
                        "percentage": float(null_pct),
                        "description": f"Column '{col}' has {null_count} null values ({null_pct:.1f}%)",
                    }
                )

        return issues

    def _check_format_consistency(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Detect format inconsistencies.

        Args:
            df: DataFrame to check

        Returns:
            List of issues
        """
        issues = []

        for col in df.columns:
            if df[col].dtype == "object":
                # Sample non-null values
                sample = df[col].dropna().astype(str).head(10)

                if len(sample) > 0:
                    # Check for different date formats
                    date_patterns = [
                        r"^\d{4}-\d{2}-\d{2}",  # YYYY-MM-DD
                        r"^\d{2}/\d{2}/\d{4}",  # MM/DD/YYYY
                        r"^\d{2}-\d{2}-\d{4}",  # DD-MM-YYYY
                    ]

                    import re

                    patterns_found = {}

                    for pattern in date_patterns:
                        matches = sample.str.contains(pattern, regex=True).sum()
                        if matches > 0:
                            patterns_found[pattern] = matches

                    if len(patterns_found) > 1:
                        issues.append(
                            {
                                "type": "format_inconsistency",
                                "severity": "medium",
                                "column": col,
                                "formats_found": len(patterns_found),
                                "description": f"Column '{col}' has {len(patterns_found)} different date formats",
                            }
                        )

        return issues

    def _detect_outliers(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Detect outliers using statistical methods.

        Args:
            df: DataFrame to check

        Returns:
            List of issues
        """
        issues = []

        numeric_cols = df.select_dtypes(include=[np.number]).columns

        for col in numeric_cols:
            series = df[col].dropna()

            if len(series) < 4:  # Need at least 4 values for IQR
                continue

            Q1 = series.quantile(0.25)
            Q3 = series.quantile(0.75)
            IQR = Q3 - Q1

            if IQR == 0:  # All values are the same
                continue

            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR

            outliers = df[(df[col] < lower_bound) | (df[col] > upper_bound)]

            if len(outliers) > 0:
                issues.append(
                    {
                        "type": "outliers",
                        "severity": "low",
                        "column": col,
                        "count": len(outliers),
                        "percentage": float(len(outliers) / len(df) * 100),
                        "examples": outliers[col].head(3).tolist(),
                        "description": f"Column '{col}' has {len(outliers)} potential outliers",
                    }
                )

        return issues

    def _check_duplicates(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Check for duplicate rows.

        Args:
            df: DataFrame to check

        Returns:
            List of issues
        """
        issues = []

        # Check for complete duplicates
        complete_dupes = df.duplicated().sum()

        if complete_dupes > 0:
            issues.append(
                {
                    "type": "duplicate_rows",
                    "severity": "high",
                    "count": int(complete_dupes),
                    "percentage": float(complete_dupes / len(df) * 100),
                    "description": f"Found {complete_dupes} completely duplicate rows",
                }
            )

        # Check for ID column duplicates
        for col in df.columns:
            if "id" in col.lower():
                dupes = df[col].duplicated().sum()

                if dupes > 0:
                    issues.append(
                        {
                            "type": "duplicate_values",
                            "severity": "high",
                            "column": col,
                            "count": int(dupes),
                            "description": f"Column '{col}' (ID) has {dupes} duplicate values",
                        }
                    )

        return issues

    def _suggest_repairs(
        self, issues: List[Dict[str, Any]], df: pd.DataFrame, table_name: str
    ) -> List[Dict[str, Any]]:
        """Suggest repairs for detected issues.

        Args:
            issues: List of detected issues
            df: DataFrame
            table_name: Table name

        Returns:
            List of repair suggestions
        """
        repairs = []

        for issue in issues[:5]:  # Limit to top 5
            issue_type = issue.get("type", "")
            column = issue.get("column")

            if issue_type == "missing_values" and column:
                repair = {
                    "issue_type": issue_type,
                    "column": column,
                    "suggestion": "fill_missing",
                    "action": f"Fill missing values in '{column}' with median/mode",
                    "confidence": 0.8,
                }

            elif issue_type == "format_inconsistency" and column:
                repair = {
                    "issue_type": issue_type,
                    "column": column,
                    "suggestion": "standardize_format",
                    "action": f"Standardize '{column}' to consistent format (ISO 8601 for dates)",
                    "confidence": 0.9,
                }

            elif issue_type == "outliers" and column:
                repair = {
                    "issue_type": issue_type,
                    "column": column,
                    "suggestion": "review_outliers",
                    "action": f"Review outliers in '{column}' and decide to keep or flag",
                    "confidence": 0.7,
                }

            elif issue_type == "duplicate_rows":
                repair = {
                    "issue_type": issue_type,
                    "suggestion": "remove_duplicates",
                    "action": "Remove or mark duplicate rows",
                    "confidence": 0.9,
                }

            elif issue_type == "duplicate_values" and column:
                repair = {
                    "issue_type": issue_type,
                    "column": column,
                    "suggestion": "investigate_duplicates",
                    "action": f"Investigate duplicate values in ID column '{column}'",
                    "confidence": 0.8,
                }

            else:
                repair = {
                    "issue_type": issue_type,
                    "suggestion": "manual_review",
                    "action": "Manual review required",
                    "confidence": 0.5,
                }

            repairs.append(repair)

        return repairs
