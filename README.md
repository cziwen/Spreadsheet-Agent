# Spreadsheet Agent CLI MVP

A lightweight CLI-based AI agent system for spreadsheet analysis with three core features. The system uses a Lead Agent + 3 Subagent architecture powered by Google Gemini API.

---

## Quick Start

### Setup 
```bash
# 1. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Get Gemini API key from https://aistudio.google.com
# and add to .env file: GOOGLE_API_KEY=your_key

# 4. Verify setup
python cli.py load-data
```

### Run Queries
```bash
# Cross-table analysis
python cli.py query "统计订单表的订单总数和平均金额"

# Data quality check
python cli.py query "检查订单表的数据质量"

# Create scenario
python cli.py query "创建一个场景，订单金额增加10%"

# View scenarios
python cli.py scenarios

# Run interactive demo
python cli.py demo
```

### Workbooks

**Default:** `data/demo_workbook` 

1. **customers.csv** (8 rows, 6 columns)
   - customer_id, name, email, channel, created_at, lifetime_value
   - Diverse customer data across organic/paid/referral channels

2. **orders.csv** (15 rows, 6 columns)
   - order_id, customer_id, product, amount, order_date, channel
   - Orders linked to customers via customer_id

**Use custom workbook:**
```bash
# 1. Create workbook directory
mkdir data/my_workbook

# 2. Add CSV files
cp your_data.csv data/my_workbook/
cp another_table.csv data/my_workbook/

# 3. Run agent on custom workbook
python cli.py query "your query" --workbook data/my_workbook
python cli.py load-data --workbook data/my_workbook
python cli.py scenarios --workbook data/my_workbook
```
---

## Core Components 

### 1. **LLM Client** (`agent/core/llm_client.py`)
- Wrapper around Google Generative AI (Gemini) API
- Handles both text generation and structured JSON parsing
- Robust error handling with multiple parsing strategies
- Automatically recovers from markdown formatting in responses

### 2. **Data Engine** (`agent/core/data_engine.py`)
- Loads/saves CSV files from workbook directory
- Manages scenario data persistence (JSON)
- Tracks operation history
- Provides table information and metadata
- SemanticAnalyzer class: rule-based fallback

### 3. **Lead Agent** (`agent/lead_agent.py`)
- **Main orchestrator** that routes queries to subagents
- Query classification using LLM
- Manages workbook loading and scenario persistence
- Error handling and operation history recording
- Returns structured results to CLI

### 4. **Semantic Analysis Subagent** (`agent/subagents/semantic_agent.py`)
**Demonstrates:**
- LLM-powered semantic understanding
- Intelligent relationship discovery with reasoning and confidence scores
- Intelligent caching to reduce LLM API cost
- Automatic fallback to rule-based analysis for reliability

**Key Methods:**
- `analyze_table_semantics()` - Analyzes table schema with business context and confidence scoring
- `discover_relationships()` - Discovers relationships with join keys, types, and reasoning
- `analyze_column_semantics()` - Granular column semantic analysis

**Example Usage:**
```
Automatic execution in CrossTableAgent
→ Analyzes customers/orders tables with LLM
→ Discovers customer_id foreign key relationship with 90%+ accuracy
→ Returns: Table purpose, entity types, business meanings, metrics/dimensions
```

### 5. **Subagent 1: Cross-Table Analysis** (`agent/subagents/cross_table_agent.py`)
**Demonstrates:**
- Automatic table relationship detection
- Multi-step query execution (join → filter → aggregate)
- Schema analysis and semantic understanding
- Execution plan generation
- Natural language to SQL-like operations

**Key Methods:**
- `_identify_tables()` - Find relevant tables for query
- `_generate_plan()` - Create step-by-step execution plan
- `_execute_plan()` - Execute operations using pandas
- Join operations with automatic key detection

**Example Usage:**
```
Query: "统计订单表的订单总数和平均金额"
→ Identifies: orders table
→ Plan: Count rows, calculate mean of amount column
→ Returns: Aggregated results
```

### 6. **Subagent 2: Data Quality Diagnosis** (`agent/subagents/quality_agent.py`)
**Demonstrates:**
- Missing value detection
- Format inconsistency detection
- Statistical outlier detection (IQR method)
- Duplicate record detection
- Repair suggestion generation

**Quality Checks Implemented:**
1. **Missing Values**: Detects null percentages per column
2. **Format Inconsistencies**: Finds multiple date/format patterns
3. **Outliers**: Uses IQR (Interquartile Range) method
4. **Duplicates**: Identifies full row and ID column duplicates

**Example Usage:**
```
Query: "检查订单表的数据质量"
→ Scans all columns for issues
→ Returns: Issues with severity levels + repair suggestions
```

### 7. **Subagent 3: Scenario Management** (`agent/subagents/scenario_agent.py`)
**Demonstrates:**
- Scenario creation with parameter modifications
- Scenario comparison with difference calculation
- History tracking and scenario listing
- Incremental metric calculation

**Features:**
1. **Create Scenario**: Clone tables, apply parameter changes
2. **Compare Scenarios**: Side-by-side metric comparison
3. **List Scenarios**: Display all saved scenarios

**Example Usage:**
```
Query: "创建一个场景，订单金额增加10%"
→ Clones baseline tables
→ Applies 10% increase to numeric columns
→ Saves scenario and calculates metrics
→ Returns: Scenario summary with metrics
```

---

## Agent Workflow
```
┌──────────────────────────────────────────┐
│        User Natural Language Query       │
└──────────────┬───────────────────────────┘
               │
┌──────────────▼───────────────────────────┐
│      LEAD AGENT (Query Router)           │
│  1. Classify query intent                │
│  2. Load workbook                        │
│  3. Route to subagent                    │
└──────────────┬───────────────────────────┘
               │
      ┌────────┴────────┬──────────────┬──────────────┐
      │                 │              │              │
      ▼                 ▼              ▼              ▼
┌────────────┐  ┌──────────────┐  ┌───────────┐  ┌──────────┐
│Cross-Table │  │Quality Scan  │  │ Scenarios │  │ Record   │
│ Analysis   │  │& Repair      │  │Management │  │ History  │
└────────────┘  └──────────────┘  └───────────┘  └──────────┘
      │                 │              │              │
      └────────────────┬┴──────────────┴──────────────┘
                       │
            ┌──────────▼──────────┐
            │  Format & Display   │
            │  Results to CLI     │
            └─────────────────────┘
```

## Data Flow
```
CSV Files
  ↓
DataEngine (load/save operations)
  ↓
Agents (process data)
  ↓
Results (formatted output)
  ↓
User-Friendly CLI Display
```

---

## Limitations & Future Work

### Current Limitations
- File-based storage (not suitable for millions of rows)
- Simple outlier detection (uses IQR only)
- Limited scenario comparison depth
- No multi-user collaboration
- No real-time updates


### Potential Enhancements
- Database backend (PostgreSQL, MongoDB)
- Advanced ML-based anomaly detection
- Web UI dashboard
- API endpoint exposures
- Data lineage and audit trails
- Scheduled analysis jobs
- Custom business logic rules
- Extend SemanticAgent to QualityAgent and ScenarioAgent
- Multi-language semantic understanding
- Custom domain-specific semantic models