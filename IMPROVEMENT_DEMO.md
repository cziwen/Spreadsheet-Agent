# Data Quality Agent Location Tracking - 改进展示

## 问题

用户在运行数据质量检查时，只能看到"有哪个列有问题"，但不知道**具体是第几行**。定位错误很困难。

## 改进后的效果

### ✅ 缺失值检测

**之前输出:**
```
Column 'email' has 5 null values (10.0%)
```

**现在输出:**
```
1. MISSING_VALUES [Severity: high]
   Description: Column 'email' has 2 null values (20.0%)
   📍 Locations: Rows: 1, 4
   Row indices: [1, 4]
   Total affected rows: 2
   Sample rows:
     • Row 1: email = [NULL]
     • Row 4: email = [NULL]
```

用户可以立即看到第 1 行和第 4 行的 email 列为空。

---

### ✅ 异常值检测

**之前输出:**
```
Column 'amount' has 3 potential outliers
```

**现在输出:**
```
2. OUTLIERS [Severity: low]
   Description: Column 'amount' has 1 potential outliers (values outside [-500.00, 1700.00])
   📍 Locations: Rows: 4
   Row indices: [4]
   Total affected rows: 1
   Sample rows:
     • Row 4: 5000.0 (278.2% above mean)
   Valid range: [-500.00, 1700.00]
```

用户知道：
- 第 4 行有问题
- 值是 5000.0
- 这比平均值高 278%
- 有效范围应该在 -500 到 1700 之间

---

### ✅ 重复值检测

**之前输出:**
```
Column 'id' (ID) has 3 duplicate values
```

**现在输出:**
```
3. DUPLICATE_VALUES [Severity: high]
   Description: Column 'id' (ID) has 1 duplicate values across 2 rows
   📍 Locations: Rows: 1, 2
   Row indices: [1, 2]
   Total affected rows: 2
   Sample rows:
     • Row 1: ID=2
```

用户知道：
- 第 1 和第 2 行有相同的 ID
- 重复的 ID 值是 2

---

### ✅ 格式不一致检测

**之前输出:**
```
Column 'date' has 2 different date formats
```

**现在输出:**
```
4. FORMAT_INCONSISTENCY [Severity: medium]
   Description: Column 'date' has 2 different date formats: YYYY-MM-DD, MM/DD/YYYY
   📍 Locations: Rows: 0, 1, 3, ... and 2 more
   Sample rows:
     • Row 0: 2024-01-01 [YYYY-MM-DD]
     • Row 1: 2024/01/02 [MM/DD/YYYY]
```

用户知道：
- 哪些行的日期格式不同
- 具体是什么格式（YYYY-MM-DD vs MM/DD/YYYY）
- 每种格式的示例

---

## 关键改进

| 特性 | 之前 | 之后 |
|------|------|------|
| 行号定位 | ❌ | ✅ 显示具体行号 |
| 样本数据 | ❌ | ✅ 显示前 3 行样本 |
| 上下文信息 | ❌ | ✅ 显示实际值、偏差等 |
| 便于修复 | ❌ | ✅ 用户可直接定位到 Excel 行 |
| 理解问题 | 猜测 | ✅ 清晰的问题上下文 |

## 使用场景

### 场景 1: 快速定位数据问题

```bash
$ python chat.py
>>> Check the orders table for data quality

✓ Data Quality Scan Complete
Table: orders
Size: 1000 rows × 5 columns
Quality Score: 72/100

Issues Found: 5

1. MISSING_VALUES [Severity: high]
   Description: Column 'customer_phone' has 45 null values (4.5%)
   📍 Locations: Rows: 23, 45, 67, 89, 102, ... and 40 more
   Sample rows:
     • Row 23: customer_phone = [NULL]
     • Row 45: customer_phone = [NULL]
```

用户现在可以在 Excel 中按 Ctrl+G 打开 Go To 对话框，输入 23 直接跳到出问题的行！

### 场景 2: 理解异常值的背景

```
2. OUTLIERS [Severity: low]
   Description: Column 'order_amount' has 2 potential outliers
   📍 Locations: Rows: 512, 789
   Sample rows:
     • Row 512: 99999.99 (1520.5% above mean)
     • Row 789: 50000.00 (850.2% above mean)
   Valid range: [-15.00, 5000.00]
```

用户知道这两笔订单金额异常高，可以检查是否是大客户订单或数据输入错误。

### 场景 3: 修复重复数据

```
3. DUPLICATE_VALUES [Severity: high]
   Description: Column 'order_id' (ID) has 15 duplicate values across 30 rows
   📍 Locations: Rows: 12, 34, 56, 78, 100, ... and 25 more
   Sample rows:
     • Row 12: ID=ORD-2024-001
     • Row 34: ID=ORD-2024-002
```

用户可以批量选择这些行进行审查或删除。

---

## 技术细节

### 改进的代码特性

每个检测方法现在返回以下信息：

```python
{
    "type": "issue_type",
    "severity": "high|medium|low",
    "column": "column_name",
    "count": 5,
    "percentage": 10.5,
    # ✨ 新增：位置信息
    "row_indices": [1, 4, 7, 10, 13],           # 所有受影响的行号
    "total_affected_rows": 5,                    # 总数
    "locations": "Rows: 1, 4, 7, 10, 13",       # 人类可读格式
    "sample_rows": [                             # 样本数据
        {"row": 1, "value": "...", ...},
        {"row": 4, "value": "...", ...},
    ],
    "description": "...",
}
```

### 适配多种界面

改进同时支持：
- ✅ `cli.py` - 命令行界面
- ✅ `chat.py` - 交互式聊天界面
- ✅ 任何使用 `_display_quality_result()` 的地方

### 向后兼容

- ✅ 现有的报告字段保留
- ✅ 新字段是可选的
- ✅ 现有代码无需修改
