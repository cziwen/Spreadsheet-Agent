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

    # Catalog of safe, declarative operations for LLM to use
    AVAILABLE_OPERATIONS = {
        "modify_column": {
            "description": "Modify column values by percentage",
            "params": {
                "table": "Table name",
                "column": "Column name to modify",
                "percentage": "Percentage change (positive for increase, negative for decrease)",
                "condition": "Optional: Filter condition (e.g., 'amount > 200')"
            }
        },
        "conditional_modify": {
            "description": "Apply different modifications based on conditions",
            "params": {
                "table": "Table name",
                "column": "Column to modify",
                "rules": "List of {condition, percentage} rules to apply"
            }
        }
    }

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
            result["query"] = query  # Add original query for plan generation
            return result
        except Exception as e:
            print(f"  Warning: Could not parse operation: {e}")
            return {"type": "unknown", "query": query}

    def _generate_modification_plan(
        self, query: str, workbook: Dict[str, pd.DataFrame], parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate modification plan using LLM.

        Args:
            query: Original user query
            workbook: Available tables
            parameters: Parsed parameters from _parse_operation()

        Returns:
            Structured plan with steps to execute
        """
        # Build context: table schemas
        schemas = {}
        for table_name, df in workbook.items():
            numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
            schemas[table_name] = {
                "columns": list(df.columns),
                "numeric_columns": numeric_cols,
                "sample_values": {col: df[col].head(2).tolist() for col in numeric_cols[:3]}
            }

        prompt = f"""
User query: "{query}"
Parsed parameters: {json.dumps(parameters)}

Available tables and columns:
{json.dumps(schemas, indent=2)}

Available operations for scenario modification:
{json.dumps(self.AVAILABLE_OPERATIONS, indent=2)}

Your task: Generate a modification plan that transforms the data according to the user's intent.

Important rules:
1. Only modify numeric columns (not IDs, dates, or text)
2. Skip columns ending in '_id' or named 'id'
3. For conditional queries (e.g., "orders above $200 increase by 20%"), use conditional_modify operation
4. For simple queries (e.g., "all orders increase by 10%"), use modify_column operation
5. Match column names intelligently (e.g., "revenue" → "amount", "sales" → "amount")
6. Each step must reference actual table/column names from the schemas

Examples:

Query: "Create scenario where order amounts increase by 10%"
→ {{
    "steps": [
        {{
            "operation": "modify_column",
            "params": {{
                "table": "orders",
                "column": "amount",
                "percentage": 10,
                "condition": null
            }},
            "description": "Increase all order amounts by 10%"
        }}
    ],
    "reasoning": "Simple percentage increase to all order amounts"
}}

Query: "Create scenario where orders above $200 increase by 20% and below increase by 5%"
→ {{
    "steps": [
        {{
            "operation": "conditional_modify",
            "params": {{
                "table": "orders",
                "column": "amount",
                "rules": [
                    {{"condition": "amount > 200", "percentage": 20}},
                    {{"condition": "amount <= 200", "percentage": 5}}
                ]
            }},
            "description": "Apply 20% increase to high-value orders, 5% to others"
        }}
    ],
    "reasoning": "Differentiated strategy based on order value"
}}

Generate the modification plan:
"""

        try:
            plan = self.llm.call_structured(prompt)
            return plan
        except Exception as e:
            print(f"  Warning: Could not generate plan: {e}")
            # Fallback: generate simple plan
            return self._generate_fallback_plan(parameters, workbook)

    def _generate_fallback_plan(
        self, parameters: Dict[str, Any], workbook: Dict[str, pd.DataFrame]
    ) -> Dict[str, Any]:
        """Generate fallback plan when LLM fails."""
        steps = []

        for param_name, param_value in parameters.items():
            if isinstance(param_value, (int, float)):
                # Try to find matching table/column
                for table_name, df in workbook.items():
                    for col in df.columns:
                        if "amount" in col.lower() or "value" in col.lower():
                            if pd.api.types.is_numeric_dtype(df[col]) and not (col.endswith("id") or "_id" in col):
                                steps.append({
                                    "operation": "modify_column",
                                    "params": {
                                        "table": table_name,
                                        "column": col,
                                        "percentage": param_value,
                                        "condition": None
                                    },
                                    "description": f"Modify {table_name}.{col} by {param_value}%"
                                })
                                break

        return {
            "steps": steps,
            "reasoning": "Fallback plan: applied modifications to likely business metric columns"
        }

    def _execute_plan(
        self, plan: Dict[str, Any], scenario_data: Dict[str, Any]
    ) -> Dict[str, List[str]]:
        """Execute modification plan safely.

        Args:
            plan: LLM-generated plan with steps
            scenario_data: Scenario data with tables as DataFrames

        Returns:
            Dictionary of modified columns per table
        """
        modified_columns = {}
        steps = plan.get("steps", [])

        for i, step in enumerate(steps, 1):
            operation = step.get("operation")
            params = step.get("params", {})
            description = step.get("description", "")

            try:
                if operation == "modify_column":
                    self._execute_modify_column(scenario_data, params, modified_columns)
                elif operation == "conditional_modify":
                    self._execute_conditional_modify(scenario_data, params, modified_columns)
                else:
                    print(f"  ⚠ Unknown operation: {operation}")
                    continue

                print(f"  ✓ {description}")

            except Exception as e:
                print(f"  ✗ {description}: {e}")
                continue

        return modified_columns

    def _execute_modify_column(
        self, scenario_data: Dict[str, Any], params: Dict[str, Any], modified_columns: Dict[str, List[str]]
    ) -> None:
        """Execute simple column modification."""
        table = params["table"]
        column = params["column"]
        percentage = params["percentage"]
        condition = params.get("condition")

        # Validate
        if table not in scenario_data["tables"]:
            raise ValueError(f"Table '{table}' not found")

        df = scenario_data["tables"][table]

        if column not in df.columns:
            raise ValueError(f"Column '{column}' not found in {table}")

        if not pd.api.types.is_numeric_dtype(df[column]):
            raise ValueError(f"Column '{column}' is not numeric")

        # Apply modification
        multiplier = 1 + (percentage / 100)

        if condition:
            # Apply condition using pandas query
            mask = df.eval(condition)
            df.loc[mask, column] = df.loc[mask, column] * multiplier
        else:
            df[column] = df[column] * multiplier

        # Track modification
        if table not in modified_columns:
            modified_columns[table] = []
        if column not in modified_columns[table]:
            modified_columns[table].append(column)

    def _execute_conditional_modify(
        self, scenario_data: Dict[str, Any], params: Dict[str, Any], modified_columns: Dict[str, List[str]]
    ) -> None:
        """Execute conditional modification with multiple rules."""
        table = params["table"]
        column = params["column"]
        rules = params["rules"]

        # Validate
        if table not in scenario_data["tables"]:
            raise ValueError(f"Table '{table}' not found")

        df = scenario_data["tables"][table]

        if column not in df.columns:
            raise ValueError(f"Column '{column}' not found in {table}")

        # Apply each rule
        for rule in rules:
            condition = rule["condition"]
            percentage = rule["percentage"]
            multiplier = 1 + (percentage / 100)

            mask = df.eval(condition)
            df.loc[mask, column] = df.loc[mask, column] * multiplier

        # Track modification
        if table not in modified_columns:
            modified_columns[table] = []
        if column not in modified_columns[table]:
            modified_columns[table].append(column)

    def _generate_summary(self, plan: Dict[str, Any], metrics: Dict[str, Any]) -> str:
        """Generate natural language summary of scenario impact.

        Args:
            plan: Execution plan with reasoning and steps
            metrics: Calculated before/after metrics

        Returns:
            Human-readable summary of business impact
        """
        summary_parts = []

        # Add plan reasoning
        if "reasoning" in plan:
            summary_parts.append(f"• Scenario: {plan['reasoning']}")

        # Add metric impacts
        metric_impacts = []
        for table_name, table_metrics in metrics.items():
            for column_name, metric_data in table_metrics.items():
                baseline = metric_data.get("baseline", 0)
                scenario = metric_data.get("scenario", 0)
                change = metric_data.get("change", 0)
                change_pct = metric_data.get("change_pct", 0)

                if baseline > 0:
                    metric_impacts.append(
                        f"• {table_name}.{column_name}: ${baseline:.2f} → ${scenario:.2f} "
                        f"(+${change:.2f}, +{change_pct}%)"
                    )

        if metric_impacts:
            summary_parts.append("Impact:")
            summary_parts.extend(metric_impacts)

        return "\n".join(summary_parts) if summary_parts else "No measurable impact"

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

        # Generate modification plan using LLM
        query = operation.get("query", "")
        plan = self._generate_modification_plan(query, workbook, parameters)

        print(f"  • Generated plan: {len(plan.get('steps', []))} step(s)")
        if "reasoning" in plan:
            print(f"  • Reasoning: {plan['reasoning']}\n")

        # Execute the plan
        modified_columns = self._execute_plan(plan, scenario_data)

        # Calculate before/after metrics for ONLY modified columns
        for table_name, modified_cols in modified_columns.items():
            if not modified_cols:
                continue

            baseline_df = workbook[table_name]
            scenario_df = scenario_data["tables"][table_name]

            scenario_data["metrics"][table_name] = {}

            for col in modified_cols:
                # Skip ID columns from metrics
                if "_id" in col.lower() or col.lower().endswith("id"):
                    continue

                if pd.api.types.is_numeric_dtype(baseline_df[col]):
                    baseline_sum = float(baseline_df[col].sum())
                    scenario_sum = float(scenario_df[col].sum())
                    change = scenario_sum - baseline_sum
                    change_pct = (change / baseline_sum * 100) if baseline_sum != 0 else 0

                    scenario_data["metrics"][table_name][col] = {
                        "baseline": baseline_sum,
                        "scenario": scenario_sum,
                        "change": change,
                        "change_pct": round(change_pct, 2)
                    }

        # Generate natural language summary of business impact
        scenario_data["summary"] = self._generate_summary(plan, scenario_data["metrics"])

        # Save scenario (DataFrames will be converted to JSON)
        self.data_engine.save_scenario(scenario_name, scenario_data)

        print(f"  ✓ Scenario '{scenario_name}' created successfully\n")

        return {
            "type": "scenario",
            "operation": "create",
            "scenario_name": scenario_name,
            "parameters": parameters,
            "metrics": scenario_data["metrics"],
            "summary": scenario_data.get("summary", ""),
            "message": f"Scenario '{scenario_name}' created with parameters: {parameters}",
        }

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
