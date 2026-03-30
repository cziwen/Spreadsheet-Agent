"""Data engine for spreadsheet operations."""

import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
import numpy as np

from .context_manager import ContextManager


class DataEngine:
    """Engine for loading and manipulating spreadsheet data."""

    def __init__(self, workbook_path: str = "data/demo_workbook"):
        """Initialize data engine.

        Args:
            workbook_path: Path to workbook directory
        """
        self.workbook_path = workbook_path
        self.tables: Dict[str, pd.DataFrame] = {}
        self.scenarios: Dict[str, dict] = {}
        self.history: List[dict] = []
        self.context_manager = ContextManager(workbook_path)

    def load_workbook(self) -> Dict[str, pd.DataFrame]:
        """Load all CSV files from workbook directory.

        Returns:
            Dictionary mapping table names to DataFrames
        """
        self.tables = {}

        table_dir = Path(self.workbook_path)

        if not table_dir.exists():
            table_dir.mkdir(parents=True, exist_ok=True)
            return {}

        for csv_file in table_dir.glob("*.csv"):
            table_name = csv_file.stem
            try:
                self.tables[table_name] = pd.read_csv(csv_file)
            except Exception as e:
                print(f"Error loading {csv_file}: {e}")

        return self.tables

    def save_table(self, table_name: str, df: pd.DataFrame) -> None:
        """Save table to CSV file.

        Args:
            table_name: Name of the table
            df: DataFrame to save
        """
        table_path = Path(self.workbook_path) / f"{table_name}.csv"
        table_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(table_path, index=False)
        self.tables[table_name] = df

    def load_scenarios(self) -> Dict[str, dict]:
        """Load all scenario files.

        Returns:
            Dictionary mapping scenario names to scenario data
        """
        self.scenarios = {}

        scenarios_dir = Path(self.workbook_path) / "scenarios"

        if not scenarios_dir.exists():
            scenarios_dir.mkdir(parents=True, exist_ok=True)
            return {}

        for scenario_file in scenarios_dir.glob("*.json"):
            scenario_name = scenario_file.stem
            try:
                with open(scenario_file, "r") as f:
                    self.scenarios[scenario_name] = json.load(f)
            except Exception as e:
                print(f"Error loading {scenario_file}: {e}")

        return self.scenarios

    def save_scenario(self, name: str, scenario_data: dict) -> None:
        """Save scenario to JSON file.

        Args:
            name: Scenario name
            scenario_data: Scenario data dictionary
        """
        scenarios_dir = Path(self.workbook_path) / "scenarios"
        scenarios_dir.mkdir(parents=True, exist_ok=True)

        scenario_path = scenarios_dir / f"{name}.json"

        with open(scenario_path, "w") as f:
            json.dump(scenario_data, f, indent=2, default=str)

        self.scenarios[name] = scenario_data

    def load_history(self) -> List[dict]:
        """Load operation history.

        Returns:
            List of operation records
        """
        history_file = Path(self.workbook_path) / "history.json"

        if history_file.exists():
            try:
                with open(history_file, "r") as f:
                    self.history = json.load(f)
            except Exception as e:
                print(f"Error loading history: {e}")
                self.history = []
        else:
            self.history = []

        return self.history

    def save_history(self) -> None:
        """Save operation history to file."""
        history_file = Path(self.workbook_path) / "history.json"
        history_file.parent.mkdir(parents=True, exist_ok=True)

        with open(history_file, "w") as f:
            json.dump(self.history, f, indent=2, default=str)

    def record_operation(self, operation: dict) -> None:
        """Record an operation to history.

        Args:
            operation: Operation record
        """
        from datetime import datetime

        record = {
            "timestamp": datetime.now().isoformat(),
            **operation,
        }

        self.history.append(record)
        self.save_history()

    def get_table(self, name: str) -> Optional[pd.DataFrame]:
        """Get table by name.

        Args:
            name: Table name

        Returns:
            DataFrame or None if not found
        """
        return self.tables.get(name)

    def list_tables(self) -> List[str]:
        """List all loaded table names.

        Returns:
            List of table names
        """
        return list(self.tables.keys())

    def get_table_info(self, table_name: str) -> dict:
        """Get information about a table.

        Args:
            table_name: Name of the table

        Returns:
            Dictionary with table info
        """
        df = self.get_table(table_name)

        if df is None:
            return {}

        return {
            "name": table_name,
            "rows": len(df),
            "columns": list(df.columns),
            "dtypes": df.dtypes.to_dict(),
            "sample_data": df.head(3).to_dict(orient="records"),
        }

    # ============================================================================
    # Context Management (Delegated to ContextManager)
    # ============================================================================

    def get_workbook_context(self) -> Dict[str, Any]:
        """Get workbook context.

        Returns:
            Workbook context dictionary
        """
        return self.context_manager.load_workbook_context()

    def update_workbook_context(self, key: str, value: Any) -> None:
        """Update workbook context.

        Args:
            key: Context key
            value: Context value
        """
        self.context_manager.update_workbook_metadata(key, value)


class SemanticAnalyzer:
    """Analyzer for semantic understanding of data."""

    def analyze_column_type(self, col_name: str, series: pd.Series) -> str:
        """Infer semantic type of a column using heuristics.

        Args:
            col_name: Column name
            series: Pandas series

        Returns:
            Semantic type string
        """
        col_lower = col_name.lower()

        # ID-like columns
        if "id" in col_lower or "code" in col_lower:
            if series.dtype in ["int64", "object"] and series.nunique() > len(series) * 0.9:
                return "identifier"

        # Date columns
        if "date" in col_lower or "time" in col_lower:
            return "date"

        # Email
        if "email" in col_lower:
            return "email"

        # Phone
        if "phone" in col_lower or "mobile" in col_lower:
            return "phone"

        # Amount/numeric
        if any(x in col_lower for x in ["amount", "price", "cost", "revenue", "total"]):
            return "amount"

        # Name
        if "name" in col_lower:
            return "name"

        # Category
        if "category" in col_lower or "type" in col_lower:
            return "category"

        # Boolean
        if series.dtype == "bool":
            return "boolean"

        # Numeric
        if pd.api.types.is_numeric_dtype(series):
            return "numeric"

        # Default
        return "text"

    def analyze_table_schema(self, df: pd.DataFrame) -> dict:
        """Analyze table schema.

        Args:
            df: DataFrame to analyze

        Returns:
            Schema dictionary
        """
        schema = {
            "columns": [],
            "potential_keys": [],
            "potential_foreign_keys": [],
        }

        for col in df.columns:
            col_info = {
                "name": col,
                "dtype": str(df[col].dtype),
                "semantic_type": self.analyze_column_type(col, df[col]),
                "null_count": int(df[col].isnull().sum()),
                "null_percentage": float(df[col].isnull().sum() / len(df) * 100),
                "unique_count": int(df[col].nunique()),
            }

            schema["columns"].append(col_info)

            # Detect potential primary key (mostly unique)
            if col_info["unique_count"] > len(df) * 0.9:
                schema["potential_keys"].append(col)

            # Detect potential foreign key (contains 'id')
            if "id" in col.lower() and col_info["semantic_type"] == "identifier":
                schema["potential_foreign_keys"].append(col)

        return schema

    def find_relationships(self, tables: Dict[str, pd.DataFrame]) -> List[dict]:
        """Find potential relationships between tables.

        Args:
            tables: Dictionary of table name to DataFrame

        Returns:
            List of relationship records
        """
        relationships = []

        table_names = list(tables.keys())

        for i, table1_name in enumerate(table_names):
            for table2_name in table_names[i + 1 :]:
                df1 = tables[table1_name]
                df2 = tables[table2_name]

                # Find common columns
                common_cols = set(df1.columns) & set(df2.columns)

                for col in common_cols:
                    # Check overlap
                    set1 = set(df1[col].dropna().astype(str))
                    set2 = set(df2[col].dropna().astype(str))
                    overlap = len(set1 & set2)

                    if overlap > 0:
                        relationships.append(
                            {
                                "left_table": table1_name,
                                "right_table": table2_name,
                                "join_key": col,
                                "overlap_count": overlap,
                                "overlap_percentage": overlap / min(len(set1), len(set2)) * 100,
                            }
                        )

        return sorted(relationships, key=lambda x: x["overlap_percentage"], reverse=True)
