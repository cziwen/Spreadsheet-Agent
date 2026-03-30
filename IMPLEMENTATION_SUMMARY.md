# 数据质量检查行号定位功能 - 实现总结

## 📋 实现概览

**问题:** Data Quality Agent 检查出错误但不说是哪行哪列，用户难以定位和修复。

**解决方案:** 为所有检测方法添加行号和位置信息，在 CLI 中清晰展示。

**状态:** ✅ 完成并测试

---

## 📝 修改的文件

### 1. `agent/subagents/quality_agent.py`

**改进的方法:**

| 方法 | 添加信息 |
|------|---------|
| `_check_missing_values()` | row_indices, locations, total_affected_rows, sample_rows |
| `_check_format_consistency()` | format_details, row_indices, sample_rows with format examples |
| `_detect_outliers()` | row_indices, bounds (Q1/Q3/IQR), sample_rows with deviation |
| `_check_duplicates()` | row_indices, locations, sample_rows showing duplicate values |

**关键改进:**
- 使用 `df[mask].index.tolist()` 获取受影响行的确切索引
- 显示前 3 行样本数据，展示实际内容
- 为每种检测方法提供上下文信息（如统计边界、格式名称等）
- 保持向后兼容性，现有字段不变

### 2. `cli.py` 中的 `_display_quality_result()`

**改进的显示逻辑:**

```python
# 显示位置信息
locations = issue.get("locations")
if locations:
    rprint(f"     [dim]📍 {locations}[/dim]")

# 显示样本行
sample_rows = issue.get("sample_rows", [])
if sample_rows:
    rprint(f"     [dim]Sample rows:[/dim]")
    for sample in sample_rows[:2]:
        # 根据问题类型显示不同格式的样本
```

**关键特性:**
- 使用 emoji (📍) 快速定位位置信息
- 显示人类可读的格式 "Rows: X, Y, Z"
- 针对不同问题类型显示合适的样本数据
- 保留颜色编码便于扫描

### 3. `test_quality_locations.py` (新增)

**测试覆盖:**
- 创建包含多种问题的测试数据
- 验证所有检测方法返回位置信息
- 检查样本行数据完整性
- ✅ 所有 3 个问题类型通过测试

---

## 📊 功能对比

### 缺失值检测

**之前:**
```json
{
  "type": "missing_values",
  "column": "email",
  "count": 5,
  "percentage": 10.0,
  "description": "Column 'email' has 5 null values (10.0%)"
}
```

**之后:**
```json
{
  "type": "missing_values",
  "column": "email",
  "count": 2,
  "percentage": 20.0,
  "row_indices": [1, 4],           // ✨ 新增
  "total_affected_rows": 2,        // ✨ 新增
  "locations": "Rows: 1, 4",       // ✨ 新增
  "sample_rows": [                 // ✨ 新增
    {"row": 1, "values": {...}},
    {"row": 4, "values": {...}}
  ],
  "description": "Column 'email' has 2 null values (20.0%)"
}
```

### 异常值检测

**新增信息:**
```json
{
  "row_indices": [4],
  "total_affected_rows": 1,
  "locations": "Rows: 4",
  "bounds": {
    "lower": -500.0,
    "upper": 1700.0,
    "Q1": 200.0,
    "Q3": 900.0,
    "IQR": 700.0
  },
  "sample_rows": [
    {
      "row": 4,
      "value": 5000.0,
      "deviation": "278.2% above mean"
    }
  ]
}
```

### 重复值检测

**新增信息:**
```json
{
  "row_indices": [1, 2],
  "total_affected_rows": 2,
  "locations": "Rows: 1, 2",
  "sample_rows": [
    {
      "row": 1,
      "id_value": "2",
      "all_values": {...}
    }
  ]
}
```

---

## 🔍 输出示例

### CLI 显示效果

```
✓ Data Quality Scan Complete
Table: orders
Size: 10 rows × 4 columns
Quality Score: 85/100

Issues Found: 3

  1. [red]MISSING_VALUES[/red] Column 'email' has 2 null values (20.0%)
     [dim]📍 Rows: 1, 4[/dim]
     [dim]Sample rows:[/dim]
       • Row 1: email = [NULL]
       • Row 4: email = [NULL]

  2. [blue]OUTLIERS[/blue] Column 'amount' has 1 potential outliers
     [dim]📍 Rows: 4[/dim]
     [dim]Sample rows:[/dim]
       • Row 4: 5000.0 (278.2% above mean)
     [dim]Valid range: [-500.00, 1700.00][/dim]

  3. [red]DUPLICATE_VALUES[/red] Column 'id' (ID) has 1 duplicate values across 2 rows
     [dim]📍 Rows: 1, 2[/dim]
     [dim]Sample rows:[/dim]
       • Row 1: ID=2
```

---

## ✅ 测试结果

### 运行 test_quality_locations.py

```
================================================================================
QUALITY AGENT TEST RESULTS
================================================================================

Table: test_table
Quality Score: 85/100
Total Issues: 3

1. MISSING_VALUES [Severity: high]
   Description: Column 'email' has 2 null values (20.0%)
   📍 Locations: Rows: 1, 4
   Row indices: [1, 4]
   Total affected rows: 2
   ✓ Sample rows provided

2. OUTLIERS [Severity: low]
   Description: Column 'amount' has 1 potential outliers
   📍 Locations: Rows: 4
   Row indices: [4]
   Total affected rows: 1
   ✓ Valid range bounds provided
   ✓ Sample rows with deviation

3. DUPLICATE_VALUES [Severity: high]
   Description: Column 'id' (ID) has 1 duplicate values across 2 rows
   📍 Locations: Rows: 1, 2
   ✓ Sample rows showing duplicate IDs

================================================================================
✅ All 3 issues have location information!
```

---

## 🎯 用户收益

### 快速定位
- ✅ 知道确切是第几行有问题
- ✅ 可在 Excel 中用 Ctrl+G 快速导航
- ✅ 支持批量处理多个问题行

### 理解上下文
- ✅ 看到实际数据样本
- ✅ 了解问题的严重程度
- ✅ 获得修复建议

### 高效修复
- ✅ 定向修复而非盲目删除
- ✅ 验证修复结果（重新扫描）
- ✅ 建立预防措施

---

## 🔄 向后兼容

- ✅ 现有的所有报告字段保留
- ✅ 新字段是可选的
- ✅ 现有代码无需修改
- ✅ 现有的数据处理流程继续工作

---

## 📚 相关文档

创建了三份文档帮助用户：

1. **IMPROVEMENT_DEMO.md** - 改进前后对比和示例
2. **DATA_QUALITY_GUIDE.md** - 详细的用户使用指南
3. **test_quality_locations.py** - 自动化测试脚本

---

## 🚀 下一步改进（可选）

1. **导出功能**: 将检查结果导出为 Excel 格式，直接在表格中高亮问题行
2. **自动修复**: 为某些问题类型提供一键修复（如去重、标准化格式）
3. **规则引擎**: 让用户自定义数据验证规则
4. **历史跟踪**: 记录数据质量的演变趋势
5. **与 chat.py 深度集成**: 让 AI 建议具体修复步骤

---

## 📦 提交信息

```
commit c9b608e
Author: Claude Haiku 4.5
Date: 2026-03-29

Improve: Add row/column location tracking to Data Quality Agent

Enhanced Data Quality Agent to report exact row numbers and sample data
for all detected issues, making it easier for users to locate and fix problems.
```

---

**实现完成时间:** 2026-03-29
**状态:** ✅ 完成、测试、文档齐全
