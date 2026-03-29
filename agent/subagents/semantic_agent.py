"""Subagent for LLM-powered semantic analysis of tables and columns."""

import json
import hashlib
import time
from typing import Dict, List, Any, Optional, Tuple
import pandas as pd
from agent.core.llm_client import LLMClient
from agent.core.data_engine import DataEngine, SemanticAnalyzer


class SemanticAgent:
    """LLM-powered semantic analysis agent with rule-based fallback."""

    def __init__(
        self,
        llm_client: LLMClient,
        data_engine: DataEngine,
        enable_caching: bool = True,
        cache_ttl_seconds: int = 3600,
    ):
        """Initialize semantic agent.

        Args:
            llm_client: LLM client for semantic understanding
            data_engine: Data engine
            enable_caching: Whether to cache analysis results
            cache_ttl_seconds: Cache time-to-live in seconds
        """
        self.llm = llm_client
        self.data_engine = data_engine
        self.fallback_analyzer = SemanticAnalyzer()  # Keep for fallback
        self.cache_enabled = enable_caching
        self.cache_ttl = cache_ttl_seconds
        self.cache: Dict[str, Dict[str, Any]] = {}  # Cache by table structure hash

    def analyze_table_semantics(
        self, table_name: str, df: pd.DataFrame
    ) -> Dict[str, Any]:
        """Analyze table schema using LLM.

        Replaces SemanticAnalyzer.analyze_table_schema() with enhanced semantic understanding.

        Args:
            table_name: Name of the table
            df: DataFrame to analyze

        Returns:
            Enhanced schema dictionary with semantic information
        """
        # Check cache first
        cache_key = self._get_cache_key(table_name, df)
        if self.cache_enabled:
            cached = self._get_from_cache(cache_key)
            if cached is not None:
                print(f"  ✓ Schema cached for {table_name}")
                return cached

        try:
            # Primary: LLM analysis
            result = self._llm_analyze_table(table_name, df)

            # Cache the result
            if self.cache_enabled:
                self._set_cache(cache_key, result)

            return result

        except Exception as e:
            # Fallback: Rule-based
            print(
                f"  ⚠️  LLM analysis failed for {table_name}, using rule-based fallback: {e}"
            )
            fallback = self.fallback_analyzer.analyze_table_schema(df)
            return self._convert_to_new_format(table_name, fallback)

    def discover_relationships(
        self, tables: Dict[str, pd.DataFrame]
    ) -> List[Dict[str, Any]]:
        """Discover relationships using LLM.

        Replaces SemanticAnalyzer.find_relationships() with semantic understanding.

        Args:
            tables: Dictionary of table name to DataFrame

        Returns:
            List of relationship records with reasoning
        """
        if not tables:
            return []

        try:
            # Primary: LLM analysis
            return self._llm_discover_relationships(tables)

        except Exception as e:
            # Fallback: Rule-based
            print(f"  ⚠️  LLM relationship discovery failed, using rule-based fallback: {e}")
            fallback = self.fallback_analyzer.find_relationships(tables)
            return self._convert_relationships_format(fallback)

    def analyze_column_semantics(
        self, col_name: str, series: pd.Series, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Analyze single column with LLM.

        Replaces SemanticAnalyzer.analyze_column_type() with richer semantic info.

        Args:
            col_name: Column name
            series: Pandas series
            context: Optional context about the table

        Returns:
            Dictionary with semantic information about the column
        """
        try:
            return self._llm_analyze_column(col_name, series, context)
        except Exception as e:
            # Fallback
            semantic_type = self.fallback_analyzer.analyze_column_type(col_name, series)
            return {"semantic_type": semantic_type, "confidence": 0.6}

    # Private helper methods

    def _llm_analyze_table(self, table_name: str, df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze table using LLM."""
        sample = self._sample_table_for_analysis(df)

        prompt = f"""Analyze this database table semantically and provide detailed understanding.

Table Name: {table_name}
Total Rows: {len(df)}
Total Columns: {len(df.columns)}

Column Details:
{json.dumps(sample['columns'], indent=2)}

Sample Data (first 5 rows):
{json.dumps(sample['sample_rows'], indent=2)}

Provide comprehensive analysis in JSON format with these fields:
- table_purpose: Business purpose of this table (1-2 sentences)
- entity_type: Type of entity ("fact", "dimension", "lookup", "bridge", "other")
- columns: Array with analysis for each column:
  - name: Column name
  - semantic_type: Type like "identifier", "date", "amount", "name", "category", "text", etc.
  - business_meaning: What this column represents
  - data_domain: Domain like "customer", "product", "transaction", "temporal", "financial", etc.
  - null_count: Number of nulls (from input)
  - null_percentage: Percentage of nulls (from input)
  - unique_count: Number of unique values (from input)
  - confidence: 0.0-1.0 confidence in the semantic type
  - is_identifier: Boolean - is this an identifier/key?
  - is_dimension: Boolean - is this a dimension for grouping?
  - is_metric: Boolean - is this a metric for aggregation?
- primary_keys: Array of column names that uniquely identify rows
- foreign_keys: Array of objects with "column" and "likely_references" fields
- temporal_columns: Array of date/time column names
- business_metrics: Array of columns suitable for aggregation (SUM, AVG, COUNT)
- category_dimensions: Array of columns suitable for GROUP BY operations

Analyze carefully and return valid JSON only, no other text."""

        response = self.llm.call_structured(prompt)
        if isinstance(response, str):
            response = json.loads(response)

        return response

    def _llm_discover_relationships(
        self, tables: Dict[str, pd.DataFrame]
    ) -> List[Dict[str, Any]]:
        """Discover relationships between tables using LLM."""
        # Build table summaries
        table_summaries = {}
        for table_name, df in tables.items():
            sample = self._sample_table_for_analysis(df)
            table_summaries[table_name] = {
                "rows": len(df),
                "columns": [
                    {
                        "name": col["name"],
                        "dtype": col["dtype"],
                        "unique_count": col["unique_count"],
                        "sample_values": col["sample_values"][:5],
                    }
                    for col in sample["columns"]
                ],
            }

        prompt = f"""Discover relationships between these database tables based on semantic understanding.

Tables:
{json.dumps(table_summaries, indent=2)}

Analyze and identify:
1. Foreign key relationships (which columns join tables)
2. One-to-many, many-to-many, or one-to-one relationships
3. Composite keys if needed

Consider:
- Column names and similarity (customer_id, cust_id, customerId)
- Semantic meaning (columns ending in _id often reference entities)
- Data types compatibility
- Value overlap patterns

Return JSON array of relationships:
[
  {{
    "left_table": "table1",
    "right_table": "table2",
    "join_keys": [["col1_in_table1", "col1_in_table2"], ...],
    "relationship_type": "one-to-many|many-to-many|one-to-one",
    "confidence": 0.0-1.0,
    "reasoning": "Brief explanation why these tables join",
    "overlap_count": 0,
    "overlap_percentage": 0.0
  }}
]

Return valid JSON only, sorted by confidence descending, no other text."""

        response = self.llm.call_structured(prompt)
        if isinstance(response, str):
            response = json.loads(response)

        # Ensure it's a list
        if not isinstance(response, list):
            if isinstance(response, dict) and "relationships" in response:
                response = response["relationships"]
            else:
                response = []

        # Enhance with actual value overlap analysis
        response = self._enhance_relationships_with_overlap(response, tables)

        return sorted(response, key=lambda x: x.get("confidence", 0), reverse=True)

    def _llm_analyze_column(
        self,
        col_name: str,
        series: pd.Series,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Analyze single column using LLM."""
        sample_values = series.dropna().unique()[:20].tolist()

        prompt = f"""Analyze this database column semantically:

Column Name: {col_name}
Data Type: {series.dtype}
Total Values: {len(series)}
Unique Values: {series.nunique()}
Null Count: {series.isnull().sum()}
Null Percentage: {series.isnull().sum() / len(series) * 100:.1f}%

Sample Values:
{sample_values}

{f'Table Context: {json.dumps(context)}' if context else ''}

Provide analysis in JSON:
{{
  "semantic_type": "identifier|name|email|phone|date|datetime|amount|quantity|category|boolean|text|url|address|other",
  "business_meaning": "What this column represents",
  "data_domain": "customer|product|transaction|temporal|financial|contact|other",
  "confidence": 0.0-1.0,
  "is_identifier": true/false,
  "is_foreign_key": true/false,
  "is_dimension": true/false,
  "is_metric": true/false,
  "quality_hints": ["observations about data quality"]
}}

Return valid JSON only, no other text."""

        response = self.llm.call_structured(prompt)
        if isinstance(response, str):
            response = json.loads(response)

        return response

    def _sample_table_for_analysis(
        self, df: pd.DataFrame, max_rows: int = 5
    ) -> Dict[str, Any]:
        """Sample table data intelligently for LLM analysis."""
        return {
            "sample_rows": df.head(max_rows).to_dict(orient="records"),
            "total_rows": len(df),
            "columns": [
                {
                    "name": col,
                    "dtype": str(df[col].dtype),
                    "unique_count": int(df[col].nunique()),
                    "null_count": int(df[col].isnull().sum()),
                    "sample_values": df[col].dropna().unique()[:10].tolist(),
                }
                for col in df.columns
            ],
        }

    def _enhance_relationships_with_overlap(
        self, relationships: List[Dict[str, Any]], tables: Dict[str, pd.DataFrame]
    ) -> List[Dict[str, Any]]:
        """Calculate actual value overlap for relationships."""
        for rel in relationships:
            try:
                # Handle both "join_keys" and "join_key" formats
                join_keys = rel.get("join_keys") or rel.get("join_key")
                if not join_keys:
                    continue

                # If join_key is a string, convert to list format
                if isinstance(join_keys, str):
                    join_keys = [[join_keys, join_keys]]
                    rel["join_keys"] = join_keys
                elif not isinstance(join_keys, list):
                    continue

                left_table = rel.get("left_table")
                right_table = rel.get("right_table")

                if left_table not in tables or right_table not in tables:
                    continue

                df_left = tables[left_table]
                df_right = tables[right_table]

                # Calculate overlap for first join key pair
                if join_keys and len(join_keys) > 0:
                    key_pair = join_keys[0]
                    if not isinstance(key_pair, (list, tuple)) or len(key_pair) < 2:
                        continue

                    left_col, right_col = key_pair[0], key_pair[1]

                    if left_col in df_left.columns and right_col in df_right.columns:
                        left_vals = set(df_left[left_col].dropna().astype(str))
                        right_vals = set(df_right[right_col].dropna().astype(str))
                        overlap = len(left_vals & right_vals)

                        rel["overlap_count"] = overlap
                        rel["overlap_percentage"] = (
                            overlap / min(len(left_vals), len(right_vals)) * 100
                            if min(len(left_vals), len(right_vals)) > 0
                            else 0
                        )
            except Exception as e:
                # Skip relationships that can't be processed
                pass

        return relationships

    def _convert_to_new_format(
        self, table_name: str, fallback_schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Convert fallback rule-based schema to new format."""
        # Extract columns from fallback
        columns_enhanced = []
        for col_info in fallback_schema.get("columns", []):
            col_info["confidence"] = 0.6  # Lower confidence for rule-based
            col_info["is_identifier"] = col_info["semantic_type"] == "identifier"
            col_info["is_dimension"] = col_info["semantic_type"] in [
                "category",
                "text",
                "identifier",
            ]
            col_info["is_metric"] = col_info["semantic_type"] in ["amount", "numeric"]
            col_info["business_meaning"] = col_info.get("semantic_type", "unknown")
            col_info["data_domain"] = "unknown"
            columns_enhanced.append(col_info)

        return {
            "table_purpose": f"Table: {table_name}",
            "entity_type": "unknown",
            "columns": columns_enhanced,
            "primary_keys": fallback_schema.get("potential_keys", []),
            "foreign_keys": [
                {"column": col, "likely_references": "unknown"}
                for col in fallback_schema.get("potential_foreign_keys", [])
            ],
            "temporal_columns": [
                col["name"]
                for col in columns_enhanced
                if col["semantic_type"] in ["date", "datetime"]
            ],
            "business_metrics": [
                col["name"]
                for col in columns_enhanced
                if col["semantic_type"] in ["amount", "numeric"]
            ],
            "category_dimensions": [
                col["name"]
                for col in columns_enhanced
                if col["semantic_type"] in ["category", "text", "identifier"]
            ],
        }

    def _convert_relationships_format(
        self, relationships: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Convert fallback relationships to new format."""
        converted = []
        for rel in relationships:
            # Handle missing join_key field
            join_key = rel.get("join_key")
            if not join_key:
                continue

            converted.append(
                {
                    "left_table": rel.get("left_table", ""),
                    "right_table": rel.get("right_table", ""),
                    "join_keys": [[join_key, join_key]],
                    "relationship_type": "unknown",
                    "confidence": 0.5,
                    "reasoning": f"Value overlap: {rel.get('overlap_percentage', 0):.1f}%",
                    "overlap_count": rel.get("overlap_count", 0),
                    "overlap_percentage": rel.get("overlap_percentage", 0),
                }
            )
        return converted

    def _get_cache_key(self, table_name: str, df: pd.DataFrame) -> str:
        """Generate cache key based on table structure."""
        structure = {
            "table": table_name,
            "columns": list(df.columns),
            "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
            "rows": len(df),
        }
        return hashlib.md5(
            json.dumps(structure, sort_keys=True).encode()
        ).hexdigest()

    def _get_from_cache(self, key: str) -> Optional[Dict[str, Any]]:
        """Get item from cache if not expired."""
        if key not in self.cache:
            return None

        entry = self.cache[key]
        if time.time() - entry["timestamp"] > self.cache_ttl:
            del self.cache[key]
            return None

        return entry["data"]

    def _set_cache(self, key: str, data: Dict[str, Any]):
        """Store item in cache."""
        self.cache[key] = {"data": data, "timestamp": time.time()}
