"""Subagent for cross-table analysis and queries."""

import json
from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np
from agent.core.llm_client import LLMClient
from agent.core.data_engine import DataEngine
from agent.subagents.semantic_agent import SemanticAgent


class CrossTableAgent:
    """Agent for analyzing data across multiple tables."""

    def __init__(self, llm_client: LLMClient, data_engine: DataEngine):
        """Initialize cross-table agent.

        Args:
            llm_client: LLM client
            data_engine: Data engine
        """
        self.llm = llm_client
        self.data_engine = data_engine
        self.semantic_agent = SemanticAgent(llm_client, data_engine)

    def execute(
        self,
        query: str,
        workbook: Dict[str, pd.DataFrame],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute cross-table analysis query.

        Args:
            query: User query
            workbook: Dictionary of tables
            context: Optional query context with recent history

        Returns:
            Result dictionary
        """
        print("🔗 Cross-Table Analysis Agent\n")

        # Step 1: Identify tables needed
        try:
            tables_needed = self._identify_tables(query, workbook)
        except ValueError as e:
            # Return error if user mentioned a table that doesn't exist
            return {
                "type": "error",
                "error": str(e),
                "query": query,
            }

        print(f"  • Tables identified: {tables_needed}")

        if not tables_needed:
            return {
                "type": "error",
                "error": "Could not identify relevant tables",
                "query": query,
            }

        # Step 2: Analyze table schemas
        print(f"  • Analyzing table schemas...")
        schemas = {
            name: self.semantic_agent.analyze_table_semantics(name, workbook[name])
            for name in tables_needed
            if name in workbook
        }

        # Step 3: Find relationships
        print(f"  • Finding relationships between tables...")
        try:
            relationships = self.semantic_agent.discover_relationships(
                {name: workbook[name] for name in tables_needed if name in workbook}
            )
        except Exception as e:
            print(f"  Warning: Could not discover relationships: {e}")
            relationships = []

        # Step 4: Generate execution plan
        print(f"  • Generating execution plan...")
        plan = self._generate_plan(query, schemas, relationships, tables_needed, workbook, context)

        # Step 5: Execute plan
        print(f"  • Executing plan...\n")
        result_df = self._execute_plan(plan, workbook)

        # Save result to a temporary table
        result_table_name = "query_result"
        self.data_engine.tables[result_table_name] = result_df

        return {
            "type": "cross_table",
            "query": query,
            "tables_used": tables_needed,
            "relationships": relationships[:3] if relationships else [],
            "plan": plan,
            "result": result_df,
            "result_summary": {
                "rows": len(result_df),
                "columns": list(result_df.columns),
            },
        }

    def _find_join_key(self, left_df: pd.DataFrame, right_df: pd.DataFrame) -> Optional[str]:
        """Find a common column to join on between two dataframes.

        Args:
            left_df: Left dataframe
            right_df: Right dataframe

        Returns:
            Common column name if found, None otherwise
        """
        left_cols = set(left_df.columns)
        right_cols = set(right_df.columns)
        common_cols = left_cols & right_cols

        if common_cols:
            # Prefer 'id' or columns ending with '_id'
            for col in ["id", "customer_id", "order_id", "product_id"]:
                if col in common_cols:
                    return col

            # Return first common column
            return list(common_cols)[0]

        return None

    def _identify_tables(self, query: str, workbook: Dict[str, pd.DataFrame]) -> List[str]:
        """Identify which tables are relevant to the query.

        Args:
            query: User query
            workbook: Dictionary of tables

        Returns:
            List of relevant table names
        """
        if not workbook:
            return []

        table_names = list(workbook.keys())

        # First, check if user explicitly mentions a table that doesn't exist
        mentioned_tables = self._extract_mentioned_tables(query, table_names)
        nonexistent_tables = [t for t in mentioned_tables if t not in table_names]
        if nonexistent_tables:
            raise ValueError(
                f"Table(s) not found: {', '.join(nonexistent_tables)}. "
                f"Available tables: {', '.join(table_names)}"
            )

        # Use LLM to identify relevant tables
        prompt = f"""
Available tables: {table_names}

Table schemas:
{json.dumps({name: list(workbook[name].columns)[:10] for name in table_names}, indent=2)}

User query: "{query}"

Which tables are relevant to this query? Return JSON:
{{
  "tables": ["table1", "table2", ...],
  "reasoning": "brief explanation"
}}
"""

        try:
            result = self.llm.call_structured(prompt)
            tables = result.get("tables", [])
            # Filter to only tables that exist
            return [t for t in tables if t in table_names]
        except ValueError:
            # Re-raise ValueError about missing tables
            raise
        except Exception as e:
            print(f"  Warning: Could not identify tables: {e}")
            # Fallback: use all tables if we have some
            return table_names if table_names else []

    def _extract_mentioned_tables(self, query: str, available_tables: List[str]) -> List[str]:
        """Extract table names that are explicitly mentioned in the query.

        Args:
            query: User query
            available_tables: List of available table names

        Returns:
            List of table names mentioned in the query (including non-existent ones)
        """
        query_lower = query.lower()
        mentioned = []

        # Use LLM to extract explicitly mentioned table names
        prompt = f"""
Available tables: {available_tables}

User query: "{query}"

If the user explicitly mentions a table by name (after keywords like "table", "in", "from"), what table names do they mention?
Return JSON:
{{
  "mentioned_tables": ["table1", "table2", ...],
  "reasoning": "brief explanation"
}}

Return an empty array if no tables are explicitly mentioned.
"""

        try:
            result = self.llm.call_structured(prompt)
            mentioned = result.get("mentioned_tables", [])
        except Exception as e:
            print(f"  Warning: Could not extract mentioned tables: {e}")
            # Fallback: search for common table-related patterns
            import re

            # Look for patterns like "table X", "in X", "from X"
            patterns = [
                r"(?:table|in|from|on)\s+(\w+)",
                r"the\s+(\w+)\s+table",
            ]

            for pattern in patterns:
                matches = re.findall(pattern, query_lower)
                mentioned.extend(matches)

        return list(set(mentioned))  # Remove duplicates

    def _generate_plan(
        self,
        query: str,
        schemas: Dict[str, dict],
        relationships: List[dict],
        tables_needed: List[str],
        workbook: Dict[str, pd.DataFrame],
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Generate execution plan for the query.

        Args:
            query: User query
            schemas: Table schemas
            relationships: Relationships between tables
            tables_needed: Tables to use
            workbook: Data
            context: Optional query context with data dictionary and recent queries

        Returns:
            Execution plan (list of steps)
        """
        # Build context section for prompt
        context_section = ""
        if context:
            dd = context.get("data_dictionary", {})
            if dd:
                table_desc = "\n".join([
                    f"  - {table}: {dd.get(table, {}).get('description', 'N/A')}"
                    for table in tables_needed if table in dd
                ])
                if table_desc:
                    context_section = f"""
Table Descriptions (from business context):
{table_desc}

"""
            recent = context.get("recent_queries", [])
            if recent:
                last_query = recent[-1]
                context_section += f"""
Previous Query for context:
- Query: "{last_query.get('query', 'N/A')}"
- Tables used: {', '.join(last_query.get('tables_used', []))}

"""

        prompt = f"""
{context_section}User query: "{query}"

Available tables: {tables_needed}

Table schemas:
{json.dumps(schemas, indent=2)[:1000]}  # Limit schema size

Relationships:
{json.dumps(relationships[:3], indent=2) if relationships else "No relationships found"}

Generate a step-by-step execution plan. Return JSON:
{{
  "steps": [
    {{"operation": "operation_name", "params": {{}}, "description": "..."}}
  ],
  "reasoning": "brief explanation"
}}

Available operations:
- select: Select from a table, params: {{"table": "table_name", "columns": ["col1", "col2"]}} (optional columns)
- filter: Filter rows by condition, params: {{"condition": "col > 100"}}
- join: Join tables, params: {{"left_table": "t1", "right_table": "t2", "join_key": "id"}}
- aggregate: Aggregate data, params: {{"table": "table_name" (if starting aggregate), "group_by": "col" (optional), "metrics": {{"col1": "sum", "col2": "mean"}}}}
- sort: Sort results, params: {{"by": "column_name", "ascending": true/false (optional, default true)}}
- limit: Limit results to top N rows, params: {{"n": 1}}
- outliers: Detect statistical outliers using IQR method, params: {{"column": "column_name"}}

Example 1 - Global aggregation: "what is the total revenue"
[
  {{"operation": "select", "params": {{"table": "sales"}}, "description": "Select sales table"}},
  {{"operation": "aggregate", "params": {{"metrics": {{"revenue": "sum"}}}}, "description": "Sum all revenue"}}
]

Example 2 - With filter: "total revenue where status = paid"
[
  {{"operation": "select", "params": {{"table": "sales"}}, "description": "Select sales"}},
  {{"operation": "filter", "params": {{"condition": "status == 'paid'"}}, "description": "Filter to paid transactions"}},
  {{"operation": "aggregate", "params": {{"metrics": {{"revenue": "sum"}}}}, "description": "Sum revenue"}}
]

Example 3 - With group_by and count: "count of customers by channel"
[
  {{"operation": "select", "params": {{"table": "customers"}}, "description": "Select customers"}},
  {{"operation": "aggregate", "params": {{"group_by": "channel", "metrics": {{"customer_id": "count"}}}}, "description": "Count customers by channel"}}
]

Example 3b - With group_by: "revenue by category"
[
  {{"operation": "select", "params": {{"table": "sales"}}, "description": "Select sales"}},
  {{"operation": "aggregate", "params": {{"group_by": "category", "metrics": {{"revenue": "sum"}}}}, "description": "Group by category"}}
]

Example 4 - With temporal filter: "total orders in April"
[
  {{"operation": "select", "params": {{"table": "orders"}}, "description": "Select orders"}},
  {{"operation": "filter", "params": {{"condition": "order_date >= '2024-04-01' and order_date < '2024-05-01'"}}, "description": "Filter to April orders"}},
  {{"operation": "aggregate", "params": {{"metrics": {{"order_id": "count", "amount": "mean"}}}}, "description": "Calculate count and average"}}
]

Example 5 - Find statistical outliers: "Which orders have amounts that are statistical outliers?"
[
  {{"operation": "select", "params": {{"table": "orders"}}, "description": "Select orders"}},
  {{"operation": "outliers", "params": {{"column": "amount"}}, "description": "Find orders with amounts outside normal range"}}
]

Example 6 - Top N with filter and sort: "What is Alice's highest spending product?"
[
  {{"operation": "select", "params": {{"table": "orders"}}, "description": "Select orders"}},
  {{"operation": "filter", "params": {{"condition": "name.str.contains('Alice', case=False)"}}, "description": "Filter to Alice's orders"}},
  {{"operation": "sort", "params": {{"by": "amount", "ascending": false}}, "description": "Sort by amount descending"}},
  {{"operation": "limit", "params": {{"n": 1}}, "description": "Take top 1 result"}}
]

Example 7 - Top 3 customers by revenue: "Show me the top 3 customers by total spending"
[
  {{"operation": "select", "params": {{"table": "orders"}}, "description": "Select orders"}},
  {{"operation": "aggregate", "params": {{"group_by": "customer_id", "metrics": {{"amount": "sum"}}}}, "description": "Group by customer and sum spending"}},
  {{"operation": "sort", "params": {{"by": "amount", "ascending": false}}, "description": "Sort by amount descending"}},
  {{"operation": "limit", "params": {{"n": 3}}, "description": "Take top 3 results"}}
]

IMPORTANT:
- For queries about "数量" (quantity/count), "个数" (number), or "多少" (how many), use "count" metric:
  * "每个channel的顾客数量" -> group_by: "channel", metrics: {{"customer_id": "count"}}
  * Only include the columns you're asked to calculate - don't add extra numeric columns
- Always include a filter step if the query mentions conditions (e.g., "where", "channel=", "status is", month/date references)
- Use == for equality comparisons in filter conditions
- String values should be quoted with single quotes in conditions: 'value'
- For temporal references (e.g., "四月"/April, "三月"/March, dates), use date filtering:
  * "四月" (April) -> "order_date >= '2024-04-01' and order_date < '2024-05-01'" or similar
  * "2024-03" (March 2024) -> extract month and year from query and create appropriate condition
  * Always convert month names to numbers (一月=1, 二月=2, 三月=3, 四月=4, etc.)
- Check table schema to find date columns (usually named "date", "order_date", "created_at", etc.)
- For queries asking for "highest", "lowest", "top N", "best", "worst", use sort + limit:
  * "最高" (highest) -> sort with ascending=false, then limit to n=1
  * "最低" (lowest) -> sort with ascending=true, then limit to n=1
  * "Top 3" or "前3个" (top 3) -> sort with ascending=false, then limit to n=3
"""

        try:
            result = self.llm.call_structured(prompt)
            # Handle both dict {"steps": [...]} and list [...] response formats
            if isinstance(result, list):
                return result
            elif isinstance(result, dict):
                return result.get("steps", [])
            else:
                return []
        except Exception as e:
            print(f"  Warning: Could not generate plan: {e}")
            # Return a simple default plan
            if len(tables_needed) > 1:
                # Try to find join key for fallback plan
                join_key = self._find_join_key(
                    workbook[tables_needed[0]], workbook[tables_needed[1]]
                )
                return [
                    {
                        "operation": "join",
                        "params": {
                            "left_table": tables_needed[0],
                            "right_table": tables_needed[1],
                            "join_key": join_key,
                        },
                        "description": "Join tables",
                    }
                ]
            else:
                return [
                    {
                        "operation": "select",
                        "params": {"table": tables_needed[0]},
                        "description": "Select from table",
                    }
                ]

    def _execute_plan(
        self, plan: List[Dict[str, Any]], workbook: Dict[str, pd.DataFrame]
    ) -> pd.DataFrame:
        """Execute the plan against the data.

        Args:
            plan: Execution plan
            workbook: Data

        Returns:
            Result DataFrame
        """
        if not plan:
            # Return first table if no plan
            first_table = list(workbook.values())[0] if workbook else pd.DataFrame()
            return first_table

        result = None

        for step in plan:
            operation = step.get("operation", "").lower()
            params = step.get("params", {})

            try:
                if operation == "join":
                    left_table = params.get("left_table") or params.get("table1")
                    right_table = params.get("right_table") or params.get("table2")
                    join_key = params.get("join_key") or params.get("on")

                    if left_table in workbook and right_table in workbook:
                        # If join_key is not provided, try to auto-discover it
                        if join_key is None:
                            join_key = self._find_join_key(
                                workbook[left_table], workbook[right_table]
                            )

                        if join_key is not None:
                            result = pd.merge(
                                workbook[left_table],
                                workbook[right_table],
                                on=join_key,
                                how="inner",
                            )

                elif operation == "filter":
                    if result is None and "table" in params:
                        result = workbook.get(params["table"])

                    if result is not None and "condition" in params:
                        condition = params["condition"]
                        try:
                            # Convert date columns to datetime for date comparisons
                            for col in result.columns:
                                if 'date' in col.lower() and result[col].dtype == 'object':
                                    try:
                                        result[col] = pd.to_datetime(result[col])
                                    except:
                                        pass

                            # Try direct pandas query first
                            result = result.query(condition)
                        except Exception as e:
                            # Try to parse and convert condition if query fails
                            try:
                                # Handle conditions like "channel = 'paid'" -> "channel == 'paid'"
                                import re
                                # Replace single = with == if not already ==, but not in >= or <=
                                parsed_condition = re.sub(r'([^=!<>])=([^=])', r'\1==\2', condition)
                                result = result.query(parsed_condition)
                            except:
                                # If still fails, try simple boolean indexing
                                try:
                                    # Handle conditions like "channel = paid" or "channel = 'paid'"
                                    if "=" in condition and "==" not in condition and "<" not in condition and ">" not in condition:
                                        parts = condition.split("=")
                                        col = parts[0].strip()
                                        val = parts[1].strip().strip("'\"")
                                        if col in result.columns:
                                            result = result[result[col] == val]
                                except:
                                    pass  # If all methods fail, keep data as is

                elif operation == "aggregate":
                    # If result is None but table is specified, get the table first
                    if result is None and "table" in params:
                        table = params.get("table")
                        if table in workbook:
                            result = workbook[table]

                    if result is not None:
                        group_by = params.get("group_by")
                        metrics = params.get("metrics", {})

                        if group_by:
                            if isinstance(group_by, str):
                                group_by = [group_by]

                            # Clean group_by columns: remove table prefixes (e.g., "customers.id" -> "id")
                            cleaned_group_by = []
                            for col in group_by:
                                if col in result.columns:
                                    cleaned_group_by.append(col)
                                elif "." in col:
                                    # Try removing table prefix
                                    col_name = col.split(".")[-1]
                                    if col_name in result.columns:
                                        cleaned_group_by.append(col_name)

                            if cleaned_group_by:
                                agg_dict = {}
                                # Clean metrics keys too (remove table prefixes)
                                cleaned_metrics = {}
                                for col_key, func in metrics.items():
                                    if col_key in result.columns:
                                        cleaned_metrics[col_key] = func
                                    elif "." in col_key:
                                        col_name = col_key.split(".")[-1]
                                        if col_name in result.columns:
                                            cleaned_metrics[col_name] = func

                                # Only aggregate columns explicitly specified in metrics
                                # Don't automatically add all numeric columns
                                for col in cleaned_metrics:
                                    agg_dict[col] = cleaned_metrics[col]

                                if agg_dict:
                                    result = result.groupby(cleaned_group_by).agg(agg_dict).reset_index()

                                    # Rename aggregated columns to be more descriptive
                                    # e.g., "customer_id" with "count" -> "customer_count"
                                    rename_dict = {}
                                    for col, func in agg_dict.items():
                                        if func in ["count", "size"]:
                                            new_name = f"{col}_count"
                                        elif func == "sum":
                                            new_name = f"{col}_sum"
                                        elif func in ["mean", "avg"]:
                                            new_name = f"{col}_average"
                                        elif func == "min":
                                            new_name = f"{col}_min"
                                        elif func == "max":
                                            new_name = f"{col}_max"
                                        else:
                                            new_name = f"{col}_{func}"

                                        if new_name != col:
                                            rename_dict[col] = new_name

                                    if rename_dict:
                                        result = result.rename(columns=rename_dict)
                            else:
                                # If no valid group_by columns, skip grouping
                                pass
                        else:
                            # Global aggregation (no group_by)
                            agg_result = {}

                            if metrics:
                                # Process requested metrics
                                for col_name, metric_func in metrics.items():
                                    if col_name in result.columns and pd.api.types.is_numeric_dtype(result[col_name]):
                                        if metric_func == "count":
                                            agg_result["Total Count"] = len(result)
                                        elif metric_func == "mean" or metric_func == "avg":
                                            agg_result[f"{col_name} - Average"] = result[col_name].mean()
                                        elif metric_func == "sum":
                                            agg_result[f"{col_name} - Sum"] = result[col_name].sum()
                            else:
                                # If no specific metrics, aggregate all numeric columns
                                for col in result.columns:
                                    if pd.api.types.is_numeric_dtype(result[col]):
                                        agg_result[f"{col} - Sum"] = result[col].sum()
                                        agg_result[f"{col} - Average"] = result[col].mean()

                            # Add total row count
                            agg_result["Total Rows"] = len(result)

                            if agg_result:
                                result = pd.DataFrame([agg_result])

                elif operation == "select":
                    if "table" in params:
                        table = params["table"]
                        if table in workbook:
                            result = workbook[table]

                    if "columns" in params and result is not None:
                        cols = params["columns"]
                        cols = [c for c in cols if c in result.columns]
                        if cols:
                            result = result[cols]

                elif operation == "sort":
                    if result is not None and "by" in params:
                        # Support ascending parameter (default True for backwards compatibility)
                        ascending = params.get("ascending", True)
                        result = result.sort_values(by=params["by"], ascending=ascending)

                elif operation == "limit":
                    # Limit results to top N rows (e.g., for "top 3 customers" queries)
                    if result is not None and "n" in params:
                        n = params.get("n", 1)
                        if isinstance(n, int) and n > 0:
                            result = result.head(n)

                elif operation == "outliers":
                    # Detect statistical outliers using IQR method
                    if result is not None and "column" in params:
                        col = params["column"]
                        if col in result.columns and pd.api.types.is_numeric_dtype(result[col]):
                            series = result[col].dropna()
                            if len(series) >= 4:  # Need at least 4 values for IQR
                                Q1 = series.quantile(0.25)
                                Q3 = series.quantile(0.75)
                                IQR = Q3 - Q1

                                if IQR > 0:  # Only filter if there's variation
                                    lower_bound = Q1 - 1.5 * IQR
                                    upper_bound = Q3 + 1.5 * IQR

                                    # Keep only outliers
                                    result = result[(result[col] < lower_bound) | (result[col] > upper_bound)]

            except Exception as e:
                import traceback
                print(f"  Warning: Step failed ({operation}): {e}")
                print(f"  Debug: {traceback.format_exc()}")
                continue

        # If no result, return first table
        if result is None:
            result = list(workbook.values())[0] if workbook else pd.DataFrame()

        return result
