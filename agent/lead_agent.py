"""Lead Agent that routes queries to appropriate subagents."""

import json
import re
from typing import Dict, Any, Optional
from agent.core.llm_client import LLMClient
from agent.core.data_engine import DataEngine


class LeadAgent:
    """Lead agent that routes queries to subagents."""

    def __init__(self, llm_client: LLMClient, workbook_path: str = "data/demo_workbook"):
        """Initialize lead agent.

        Args:
            llm_client: LLMClient instance
            workbook_path: Path to workbook
        """
        self.llm = llm_client
        self.data_engine = DataEngine(workbook_path)
        self.workbook = self.data_engine.load_workbook()
        self.data_engine.load_history()
        self.workbook_path = workbook_path
        self.session_id: Optional[str] = None  # Set by chat.py when needed

        # Lazy imports to avoid circular dependency
        self._subagents = {}

    def set_session(self, session_id: str) -> None:
        """Set the current session ID for context tracking.

        Args:
            session_id: Session ID
        """
        self.session_id = session_id

    def _get_subagents(self):
        """Lazily import subagents."""
        if not self._subagents:
            from agent.subagents.cross_table_agent import CrossTableAgent
            from agent.subagents.quality_agent import QualityAgent
            from agent.subagents.scenario_agent import ScenarioAgent

            self._subagents = {
                "cross_table": CrossTableAgent(self.llm, self.data_engine),
                "quality": QualityAgent(self.llm, self.data_engine),
                "scenario": ScenarioAgent(self.llm, self.data_engine),
            }

        return self._subagents

    def process_query(self, query: str, use_context: bool = True) -> Dict[str, Any]:
        """Process a natural language query.

        Args:
            query: User's natural language query
            use_context: Whether to use conversation context (default True)

        Returns:
            Result dictionary
        """
        print(f"\n📝 Processing query: {query}\n")

        # Step 1: Load context if available
        context = None
        if use_context and self.session_id:
            context = self._load_query_context()

        # Step 2: Classify query intent
        intent = self._classify_query(query, context)
        print(f"🎯 Query type: {intent['type']} (confidence: {intent.get('confidence', 0):.1%})\n")

        # Step 3: Reload workbook (in case of changes)
        self.workbook = self.data_engine.load_workbook()
        self.data_engine.load_scenarios()

        # Step 4: Route to appropriate subagent
        subagents = self._get_subagents()

        query_type = intent["type"]

        try:
            if query_type == "meta":
                result = self._handle_meta_query(query)
            elif query_type == "cross_table":
                result = subagents["cross_table"].execute(query, self.workbook, context)
            elif query_type == "quality":
                result = subagents["quality"].execute(query, self.workbook)
            elif query_type == "scenario":
                result = subagents["scenario"].execute(query, self.workbook)
            else:
                result = {
                    "error": "Unknown query type",
                    "type": "error",
                    "query": query,
                }

            # Determine status based on whether result contains an error
            status = "error" if "error" in result else "success"

            # Record operation in history
            operation_record = {
                "query": query,
                "query_type": query_type,
                "status": status,
            }

            # Include error message if present
            if "error" in result:
                operation_record["error"] = result["error"]

            self.data_engine.record_operation(operation_record)

            # Update session context if available
            if self.session_id:
                self._update_session_context(query, result)

        except Exception as e:
            print(f"❌ Error: {str(e)}\n")
            result = {
                "error": str(e),
                "type": "error",
                "query": query,
            }

            self.data_engine.record_operation(
                {
                    "query": query,
                    "query_type": query_type,
                    "status": "error",
                    "error": str(e),
                }
            )

            # Update session context with error
            if self.session_id:
                self._update_session_context(query, result)

        return result

    def _handle_meta_query(self, query: str) -> Dict[str, Any]:
        """Handle capability/meta questions about what analyses are possible.

        Args:
            query: User's meta query

        Returns:
            Result with capability description
        """
        tables = self.data_engine.list_tables()
        table_info = []

        for table in tables:
            df = self.data_engine.get_table(table)
            columns = df.columns.tolist()
            table_info.append(f"- {table}: {', '.join(columns)}")

        tables_desc = "\n".join(table_info) if table_info else "No tables available"

        prompt = f"""
You are a helpful data analysis assistant. A user is asking about what kinds of analysis are possible with their data.

Available tables and columns:
{tables_desc}

User question: "{query}"

Provide a natural language response describing the types of analyses they can perform. Include:
1. Simple analyses (filtering, sorting, basic statistics)
2. Cross-table analyses (joins, comparisons)
3. Aggregations and summaries
4. Data quality checks
5. What-if scenarios

Be specific about what they can do with their data tables and columns. Keep the response concise but informative.
"""

        try:
            response = self.llm.call(prompt)
            return {
                "type": "meta",
                "result": response,
                "query": query,
            }
        except Exception as e:
            return {
                "type": "meta",
                "error": str(e),
                "query": query,
            }

    def _classify_query(self, query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Classify query intent using LLM.

        Args:
            query: User query
            context: Optional query context with recent history

        Returns:
            Classification result
        """
        table_list = ", ".join(self.data_engine.list_tables()) or "No tables loaded"

        # Build context section for prompt
        context_section = ""
        if context:
            wb_meta = context.get("workbook_metadata", {})
            if wb_meta:
                context_section = f"""
Workbook Context:
- Business Domain: {wb_meta.get('business_domain', 'Unknown')}
- Description: {wb_meta.get('description', 'N/A')}

"""
            recent = context.get("recent_queries", [])
            if recent:
                history_text = "\n".join([
                    f"  - {q['query']} ({q['query_type']})"
                    for q in recent
                ])
                context_section += f"""
Recent Conversation:
{history_text}

"""

        prompt = f"""
{context_section}Classify this spreadsheet query into ONE category:

Available tables: {table_list}

Categories:
1. meta: Query asks about CAPABILITIES - what analyses are possible, what can be done, system info
   - Key indicators: "what kind", "what can", "what's possible", "what analysis", "what operations", "how can I", "capabilities"
   - Does NOT request specific data, asks about possibilities
   Examples: "What kind of analysis is possible?", "What can I do with this data?", "What analyses are supported?"

2. cross_table: Query asks for ANALYTICAL RESULTS - specific rows, aggregations, statistics, filtering
   - Key indicators: "which", "show me", "list", "find", "how many", "what is", "calculate", "statistical", "outliers" (asking for them)
   Examples: "哪个客户购买最多", "月度销售汇总", "Which orders have amounts that are statistical outliers", "Show me customers with >$5000 spent"

3. quality: Query asks to SCAN/CHECK data quality - validation, completeness, consistency checks
   - Key indicators: "check", "validate", "scan", "diagnose", "audit", "quality assessment"
   - Does NOT ask for specific results, asks about data integrity
   Examples: "检查数据质量", "检查重复数据", "Validate data completeness", "Audit the customer table"

4. scenario: Query about creating scenarios, what-if analysis, scenario comparison
   Examples: "创建场景: budget增加20%", "对比不同场景", "保存当前场景", "乐观估计"

User query: "{query}"

Return JSON with this exact format:
{{
  "type": "meta" OR "cross_table" OR "quality" OR "scenario",
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation"
}}
"""

        try:
            result = self.llm.call_structured(prompt)
            return result
        except Exception as e:
            print(f"Warning: Failed to classify query: {e}")
            # Default to cross_table if classification fails
            return {"type": "cross_table", "confidence": 0.5, "reasoning": "Default classification"}

    def _load_query_context(self) -> Dict[str, Any]:
        """Load relevant context for current query.

        Returns:
            Context dictionary with workbook metadata, data dictionary, and recent queries
        """
        workbook_ctx = self.data_engine.get_workbook_context()
        session_ctx = self.data_engine.context_manager.load_session(self.session_id)

        return {
            "workbook_metadata": workbook_ctx.get("metadata", {}),
            "data_dictionary": workbook_ctx.get("data_dictionary", {}),
            "recent_queries": self.data_engine.context_manager.get_recent_history(
                self.session_id, limit=3
            ),
            "current_focus": session_ctx.get("current_focus", {})
        }

    def _update_session_context(self, query: str, result: Dict[str, Any]) -> None:
        """Update session context with latest query and result.

        Args:
            query: User query
            result: Query result
        """
        try:
            # Add to conversation history
            self.data_engine.context_manager.add_to_history(self.session_id, query, result)

            # Record query pattern if it's a successful cross_table query
            if result.get("type") == "cross_table" and "error" not in result:
                tables_used = result.get("tables_used", [])
                if len(tables_used) > 1:
                    # Try to find join key from result metadata
                    join_key = result.get("join_key")
                    if join_key:
                        self.data_engine.context_manager.record_query_pattern(tables_used, join_key)

            # Record frequent query pattern
            self.data_engine.context_manager.record_frequent_query(query)

            # Update session focus
            tables_used = result.get("tables_used", [])
            self.data_engine.context_manager.update_session_focus(
                self.session_id,
                active_tables=tables_used,
                last_result_table=result.get("result_table"),
            )

        except Exception as e:
            print(f"Warning: Failed to update session context: {e}")
