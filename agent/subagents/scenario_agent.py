"""Subagent for scenario management and what-if analysis."""

import json
from datetime import datetime
from typing import Dict, List, Any, Optional
import pandas as pd
from copy import deepcopy
from agent.core.llm_client import LLMClient
from agent.core.data_engine import DataEngine


class ScenarioAgent:
    """Agent for scenario management and scenario comparison."""

    def __init__(self, llm_client: LLMClient, data_engine: DataEngine):
        """Initialize scenario agent.

        Args:
            llm_client: LLM client
            data_engine: Data engine
        """
        self.llm = llm_client
        self.data_engine = data_engine

    def execute(self, query: str, workbook: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """Execute scenario management operation.

        Args:
            query: User query
            workbook: Dictionary of tables

        Returns:
            Result dictionary
        """
        print("🎬 Scenario Management Agent\n")

        # Parse what operation is needed
        operation = self._parse_operation(query)
        op_type = operation.get("type", "unknown")

        print(f"  • Operation: {op_type}")

        if op_type == "create":
            result = self._create_scenario(operation, workbook)

        elif op_type == "compare":
            result = self._compare_scenarios(operation)

        elif op_type == "list":
            result = self._list_scenarios()

        else:
            result = {
                "type": "scenario",
                "error": f"Unknown scenario operation: {op_type}",
                "query": query,
            }

        return result

    def _parse_operation(self, query: str) -> Dict[str, Any]:
        """Parse what scenario operation is requested.

        Args:
            query: User query

        Returns:
            Operation specification
        """
        prompt = f"""
User query: "{query}"

Parse the scenario operation. Determine:
1. Type: "create", "compare", "list", or "save"
2. Scenario name (if creating) - generate from description if not explicitly named
3. Parameters to modify (if creating)
4. Scenarios to compare (if comparing)

Examples of create operations:
- "创建场景: marketing_budget增加20%" →
  {{"type": "create", "scenario_name": "marketing_budget_increase_20", "parameters": {{"budget_increase": 20}}}}

- "创建一个场景，订单金额增加10%" →
  {{"type": "create", "scenario_name": "order_amounts_increase_10", "parameters": {{"order_amounts_increase": 10}}}}

- "创建乐观估计，成本降低15%" →
  {{"type": "create", "scenario_name": "optimistic_estimate", "parameters": {{"cost_decrease": 15}}}}

- "Create scenario where revenue increases by 20%" →
  {{"type": "create", "scenario_name": "revenue_increase_20", "parameters": {{"revenue_increase": 20}}}}

If no explicit name is mentioned in the query, generate one from the parameters or description.

Return JSON:
{{
  "type": "create|compare|list|save",
  "scenario_name": "name" (if creating, null if not provided),
  "parameters": {{"param": value}} (if modifying),
  "scenarios_to_compare": ["scenario1", "scenario2"] (if comparing),
  "reasoning": "explanation"
}}
"""

        try:
            result = self.llm.call_structured(prompt)
            return result
        except Exception as e:
            print(f"  Warning: Could not parse operation: {e}")
            return {"type": "unknown"}

    def _create_scenario(
        self, operation: Dict[str, Any], workbook: Dict[str, pd.DataFrame]
    ) -> Dict[str, Any]:
        """Create a new scenario.

        Args:
            operation: Operation specification
            workbook: Current workbook data

        Returns:
            Result dictionary
        """
        scenario_name = operation.get("scenario_name")
        parameters = operation.get("parameters", {})

        # Handle None or missing scenario name
        if not scenario_name or scenario_name == "None":
            if parameters:
                # Generate name from parameters (e.g., "order_amounts_increase_10")
                param_parts = []
                for k, v in parameters.items():
                    param_parts.append(f"{k}_{v}")
                scenario_name = "_".join(param_parts)[:50]  # limit length
            else:
                # Use incremental default
                from pathlib import Path
                scenarios_dir = Path(self.data_engine.workbook_dir) / "scenarios"
                existing_scenarios = list(scenarios_dir.glob("scenario_*.json")) if scenarios_dir.exists() else []
                scenario_name = f"scenario_{len(existing_scenarios) + 1}"

        print(f"  • Creating scenario: {scenario_name}")
        print(f"  • Parameters: {parameters}\n")

        # Create scenario by cloning current workbook
        scenario_data = {
            "name": scenario_name,
            "created_at": datetime.now().isoformat(),
            "base_scenario": "baseline",
            "parameters": parameters,
            "tables": {},
            "metrics": {},
        }

        # Copy tables to scenario
        for table_name, df in workbook.items():
            scenario_data["tables"][table_name] = df.copy()

        # Apply parameter modifications
        scenario_data = self._apply_parameters(scenario_data, parameters)

        # Calculate metrics BEFORE saving (while tables are still DataFrames)
        for table_name, df in scenario_data["tables"].items():
            numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
            if numeric_cols:
                scenario_data["metrics"][table_name] = {
                    col: float(df[col].sum()) for col in numeric_cols[:3]
                }

        # Save scenario (DataFrames will be converted to JSON)
        self.data_engine.save_scenario(scenario_name, scenario_data)

        print(f"  ✓ Scenario '{scenario_name}' created successfully\n")

        return {
            "type": "scenario",
            "operation": "create",
            "scenario_name": scenario_name,
            "parameters": parameters,
            "metrics": scenario_data["metrics"],
            "message": f"Scenario '{scenario_name}' created with parameters: {parameters}",
        }

    def _apply_parameters(
        self, scenario_data: Dict[str, Any], parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply parameter modifications to scenario tables.

        Args:
            scenario_data: Scenario data
            parameters: Parameters to apply

        Returns:
            Modified scenario data
        """
        # Process different types of parameters
        for param_name, param_value in parameters.items():
            param_lower = param_name.lower()

            # Look for numeric parameters (increase/decrease percentages)
            if isinstance(param_value, (int, float)):
                # Determine if increase or decrease
                is_increase = "increase" in param_lower or "rise" in param_lower
                is_decrease = "decrease" in param_lower or "reduce" in param_lower or "decline" in param_lower

                if not (is_increase or is_decrease):
                    # Legacy handling for "budget_increase", "cost_decrease" style params
                    is_increase = True  # Default to increase

                # Extract keywords from parameter name
                # e.g., "order_amounts_increase" → ["order", "amounts"]
                keywords = [word for word in param_lower.replace("_", " ").split()
                           if word not in ["increase", "decrease", "rise", "reduce", "decline"]]

                # Find matching columns across all tables
                multiplier = (1 + param_value / 100) if is_increase else (1 - param_value / 100)

                for table_name, df in scenario_data["tables"].items():
                    for col in df.columns:
                        col_lower = col.lower()
                        # Match if any keyword appears in column name OR column name appears in keyword
                        # This handles both "amount" matching "amounts" and "order" matching "order_id"
                        matches = any(
                            keyword in col_lower or col_lower in keyword
                            for keyword in keywords
                        )
                        if matches:
                            # Only apply to numeric columns
                            if pd.api.types.is_numeric_dtype(df[col]):
                                # Skip ID columns (prefer amount/value/price/quantity columns)
                                if "_id" in col_lower or col_lower.endswith("id"):
                                    # Only modify ID if explicitly mentioned in keywords
                                    if not any(id_word in keyword for keyword in keywords for id_word in ["id", "identifier"]):
                                        continue

                                scenario_data["tables"][table_name][col] = df[col] * multiplier
                                print(f"  Applied {param_value}% {'increase' if is_increase else 'decrease'} to {table_name}.{col}")

        return scenario_data

    def _compare_scenarios(self, operation: Dict[str, Any]) -> Dict[str, Any]:
        """Compare multiple scenarios.

        Args:
            operation: Operation specification

        Returns:
            Result dictionary
        """
        scenarios_to_compare = operation.get("scenarios_to_compare", ["baseline"])

        print(f"  • Comparing scenarios: {scenarios_to_compare}\n")

        # Load scenarios
        scenarios = {}

        for scenario_name in scenarios_to_compare:
            if scenario_name in self.data_engine.scenarios:
                scenarios[scenario_name] = self.data_engine.scenarios[scenario_name]
            else:
                print(f"  Warning: Scenario '{scenario_name}' not found")

        if not scenarios:
            return {
                "type": "scenario",
                "error": "No scenarios to compare",
                "operation": "compare",
            }

        # Generate comparison
        comparison = self._generate_comparison(scenarios)

        print(f"  ✓ Comparison complete\n")

        return {
            "type": "scenario",
            "operation": "compare",
            "scenarios_compared": list(scenarios.keys()),
            "comparison": comparison,
        }

    def _generate_comparison(self, scenarios: Dict[str, dict]) -> Dict[str, Any]:
        """Generate comparison between scenarios.

        Args:
            scenarios: Dictionary of scenarios

        Returns:
            Comparison result
        """
        # Extract metrics from each scenario
        metrics_comparison = {}

        for scenario_name, scenario_data in scenarios.items():
            scenario_metrics = scenario_data.get("metrics", {})

            for table_name, metrics in scenario_metrics.items():
                if table_name not in metrics_comparison:
                    metrics_comparison[table_name] = {}

                for metric_name, value in metrics.items():
                    if metric_name not in metrics_comparison[table_name]:
                        metrics_comparison[table_name][metric_name] = {}

                    metrics_comparison[table_name][metric_name][scenario_name] = value

        # Calculate differences
        differences = {}

        for table_name, metrics in metrics_comparison.items():
            differences[table_name] = {}

            for metric_name, scenario_values in metrics.items():
                scenario_list = list(scenario_values.items())

                if len(scenario_list) >= 2:
                    baseline_name, baseline_value = scenario_list[0]
                    other_name, other_value = scenario_list[1]

                    if baseline_value != 0:
                        pct_change = (other_value - baseline_value) / baseline_value * 100
                        differences[table_name][f"{metric_name}_change"] = {
                            "percentage": pct_change,
                            "absolute": other_value - baseline_value,
                            "from": baseline_name,
                            "to": other_name,
                        }

        return {
            "metrics_comparison": metrics_comparison,
            "differences": differences,
            "recommendation": "Review differences to choose optimal scenario",
        }

    def _list_scenarios(self) -> Dict[str, Any]:
        """List all saved scenarios.

        Returns:
            Result dictionary
        """
        scenario_names = list(self.data_engine.scenarios.keys())

        print(f"  • Found {len(scenario_names)} scenario(s)")

        if scenario_names:
            for name in scenario_names:
                print(f"    - {name}")

        print()

        scenario_list = []

        for name, scenario_data in self.data_engine.scenarios.items():
            scenario_list.append(
                {
                    "name": name,
                    "created_at": scenario_data.get("created_at"),
                    "base_scenario": scenario_data.get("base_scenario"),
                    "parameters": scenario_data.get("parameters", {}),
                }
            )

        return {
            "type": "scenario",
            "operation": "list",
            "scenarios": scenario_list,
            "total": len(scenario_list),
        }
