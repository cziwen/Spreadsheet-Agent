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
            null_indices = df[df[col].isnull()].index.tolist()

            if len(null_indices) > 0:
                null_count = len(null_indices)
                null_pct = null_count / len(df) * 100

                # Get sample rows with null values
                sample_rows = df.iloc[null_indices[:3]] if null_indices else pd.DataFrame()

                issues.append(
                    {
                        "type": "missing_values",
                        "severity": "high" if null_pct > 10 else "medium",
                        "column": col,
                        "count": int(null_count),
                        "percentage": float(null_pct),
                        "row_indices": null_indices[:10],  # First 10 rows with null values
                        "total_affected_rows": len(null_indices),
                        "locations": f"Rows: {', '.join(str(i) for i in null_indices[:5])}" +
                                    (f", ... and {len(null_indices) - 5} more" if len(null_indices) > 5 else ""),
                        "sample_rows": [
                            {
                                "row": int(idx),
                                "values": {col_name: str(val) for col_name, val in sample_rows.loc[idx].items()}
                            }
                            for idx in sample_rows.index[:3]
                        ] if not sample_rows.empty else [],
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
        import re

        for col in df.columns:
            if df[col].dtype == "object":
                # Get non-null values with their indices
                non_null_mask = df[col].notna()
                non_null_data = df[col][non_null_mask]

                if len(non_null_data) > 0:
                    # Check for different date formats
                    date_patterns = {
                        r"^\d{4}-\d{2}-\d{2}": "YYYY-MM-DD",
                        r"^\d{2}/\d{2}/\d{4}": "MM/DD/YYYY",
                        r"^\d{2}-\d{2}-\d{4}": "DD-MM-YYYY",
                    }

                    patterns_found = {}
                    pattern_indices = {}  # Track which rows match each pattern

                    sample = non_null_data.astype(str).head(10)

                    for pattern, pattern_name in date_patterns.items():
                        # Find all rows matching this pattern
                        mask = df[col].astype(str).str.contains(pattern, regex=True, na=False)
                        matching_indices = df[mask].index.tolist()

                        if len(matching_indices) > 0:
                            patterns_found[pattern_name] = len(matching_indices)
                            pattern_indices[pattern_name] = matching_indices[:5]  # Store first 5 rows

                    if len(patterns_found) > 1:
                        # Get sample rows showing different formats
                        sample_rows = []
                        for fmt_name, indices in pattern_indices.items():
                            for idx in indices[:1]:  # Just one row per format
                                sample_rows.append({
                                    "row": int(idx),
                                    "format": fmt_name,
                                    "value": str(df.loc[idx, col])
                                })

                        issues.append(
                            {
                                "type": "format_inconsistency",
                                "severity": "medium",
                                "column": col,
                                "formats_found": len(patterns_found),
                                "format_details": patterns_found,
                                "row_indices": [idx for indices in pattern_indices.values() for idx in indices],
                                "sample_rows": sample_rows,
                                "description": f"Column '{col}' has {len(patterns_found)} different date formats: {', '.join(patterns_found.keys())}",
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

            outlier_mask = (df[col] < lower_bound) | (df[col] > upper_bound)
            outlier_indices = df[outlier_mask].index.tolist()
            outliers_df = df[outlier_mask]

            if len(outlier_indices) > 0:
                # Get sample rows with outlier values
                sample_rows = []
                for idx in outlier_indices[:3]:
                    sample_rows.append({
                        "row": int(idx),
                        "value": float(df.loc[idx, col]),
                        "deviation": f"{((df.loc[idx, col] - series.mean()) / series.std() * 100 if series.std() > 0 else 0):.1f}% above mean"
                    })

                issues.append(
                    {
                        "type": "outliers",
                        "severity": "low",
                        "column": col,
                        "count": len(outlier_indices),
                        "percentage": float(len(outlier_indices) / len(df) * 100),
                        "row_indices": outlier_indices[:10],  # First 10 outlier rows
                        "total_affected_rows": len(outlier_indices),
                        "locations": f"Rows: {', '.join(str(i) for i in outlier_indices[:5])}" +
                                    (f", ... and {len(outlier_indices) - 5} more" if len(outlier_indices) > 5 else ""),
                        "bounds": {
                            "lower": float(lower_bound),
                            "upper": float(upper_bound),
                            "Q1": float(Q1),
                            "Q3": float(Q3),
                            "IQR": float(IQR)
                        },
                        "examples": outliers_df[col].head(3).tolist(),
                        "sample_rows": sample_rows,
                        "description": f"Column '{col}' has {len(outlier_indices)} potential outliers (values outside [{lower_bound:.2f}, {upper_bound:.2f}])",
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
        dupe_mask = df.duplicated(keep=False)  # Mark all duplicates (including first)
        dupe_indices = df[dupe_mask].index.tolist()
        dupe_count = df.duplicated().sum()

        if dupe_count > 0:
            # Get sample duplicate rows
            sample_rows = []
            seen_values = set()

            for idx in dupe_indices[:6]:  # Get up to 6 rows showing duplicates
                row_tuple = tuple(df.loc[idx].values)
                if row_tuple not in seen_values:
                    sample_rows.append({
                        "row": int(idx),
                        "values": {col_name: str(val) for col_name, val in df.loc[idx].items()}
                    })
                    seen_values.add(row_tuple)
                    if len(sample_rows) >= 2:  # Show just 2 different duplicate groups
                        break

            issues.append(
                {
                    "type": "duplicate_rows",
                    "severity": "high",
                    "count": int(dupe_count),
                    "percentage": float(dupe_count / len(df) * 100),
                    "row_indices": dupe_indices[:10],  # First 10 duplicate rows
                    "total_affected_rows": len(dupe_indices),
                    "locations": f"Rows: {', '.join(str(i) for i in dupe_indices[:5])}" +
                                (f", ... and {len(dupe_indices) - 5} more" if len(dupe_indices) > 5 else ""),
                    "sample_rows": sample_rows,
                    "description": f"Found {dupe_count} completely duplicate rows (appears {len(dupe_indices)} total times including originals)",
                }
            )

        # Check for ID column duplicates
        for col in df.columns:
            if "id" in col.lower():
                dupe_mask = df[col].duplicated(keep=False)  # Mark all duplicates
                dupe_indices = df[dupe_mask].index.tolist()
                dupe_count = df[col].duplicated().sum()

                if dupe_count > 0:
                    # Get sample rows with duplicate IDs
                    sample_rows = []
                    seen_ids = set()

                    for idx in dupe_indices[:6]:
                        val = df.loc[idx, col]
                        if val not in seen_ids:
                            sample_rows.append({
                                "row": int(idx),
                                "id_value": str(val),
                                "all_values": {col_name: str(v) for col_name, v in df.loc[idx].items()}
                            })
                            seen_ids.add(val)
                            if len(sample_rows) >= 2:  # Show 2 different duplicate IDs
                                break

                    issues.append(
                        {
                            "type": "duplicate_values",
                            "severity": "high",
                            "column": col,
                            "count": int(dupe_count),
                            "percentage": float(dupe_count / len(df) * 100),
                            "row_indices": dupe_indices[:10],
                            "total_affected_rows": len(dupe_indices),
                            "locations": f"Rows: {', '.join(str(i) for i in dupe_indices[:5])}" +
                                        (f", ... and {len(dupe_indices) - 5} more" if len(dupe_indices) > 5 else ""),
                            "sample_rows": sample_rows,
                            "description": f"Column '{col}' (ID) has {dupe_count} duplicate values across {len(dupe_indices)} rows",
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
