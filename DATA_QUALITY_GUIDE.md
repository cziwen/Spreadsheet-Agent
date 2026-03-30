# Data Quality Check - 用户使用指南

## 快速开始

### 1️⃣ 运行数据质量检查

使用 CLI：
```bash
python chat.py
>>> Check data quality in the [table_name]
```

或直接使用 CLI 命令：
```bash
python -m cli query "Check the orders table"
```

### 2️⃣ 理解输出结果

每个发现的问题都会显示：

```
1. [问题类型] [严重程度]
   Description: 问题描述
   📍 Locations: Rows: X, Y, Z  ← 具体行号
   Sample rows:                  ← 样本数据
     • Row X: [具体值或说明]
     • Row Y: [具体值或说明]
```

### 3️⃣ 定位 Excel 中的问题

看到 `Rows: 5, 12, 18` 后：

**在 Excel/Google Sheets 中：**
1. 按 `Ctrl+G` (Windows) 或 `Cmd+Option+G` (Mac)
2. 输入行号 (例如 `5:5` 表示第 5 行)
3. 点击确定，直接跳到该行

或者直接点击行号选择整行数据。

---

## 问题类型说明

### 🔴 MISSING_VALUES (缺失值)

**严重程度:** HIGH / MEDIUM

**说明:** 某列有空值或 NULL

**示例:**
```
📍 Locations: Rows: 3, 7, 15, ... and 2 more
Sample rows:
  • Row 3: customer_email = [NULL]
  • Row 7: customer_email = [NULL]
```

**可能的原因:**
- 数据输入不完整
- 数据导入失败
- 可选字段未填写

**修复方案:**
- 填充缺失数据
- 删除包含缺失值的行（如果非关键）
- 用默认值或平均值填充

---

### 🔵 OUTLIERS (异常值)

**严重程度:** LOW / MEDIUM

**说明:** 某个值偏离统计范围太远

**示例:**
```
📍 Locations: Rows: 42
Sample rows:
  • Row 42: 50000.0 (1520.5% above mean)
Valid range: [-15.00, 5000.00]
```

**可能的原因:**
- 大订单或特殊交易
- 数据输入错误
- 多个数字输入在一起

**修复方案:**
- ✅ 如果是真实数据：保留（可能是 VIP 客户）
- ❌ 如果是错误数据：纠正或删除

---

### 🟡 FORMAT_INCONSISTENCY (格式不一致)

**严重程度:** MEDIUM

**说明:** 同一列中数据格式不统一

**示例:**
```
📍 Locations: Rows: 1, 3, 5, 7
Sample rows:
  • Row 1: 2024-01-01 [YYYY-MM-DD]
  • Row 3: 01/01/2024 [MM/DD/YYYY]
```

**可能的原因:**
- 多个数据源导入
- 手动输入时格式不统一
- 区域设置差异

**修复方案:**
- 使用数据验证规则强制统一格式
- 用 FIND & REPLACE 转换格式
- 在导入时标准化数据

---

### 🔴 DUPLICATE_VALUES (重复值)

**严重程度:** HIGH

**说明:** ID 列或唯一值列有重复

**示例:**
```
📍 Locations: Rows: 12, 34, 56
Sample rows:
  • Row 12: ID=ORD-2024-001
  • Row 34: ID=ORD-2024-001
```

**可能的原因:**
- 重复导入
- 重复数据输入
- 合并表格时产生重复

**修复方案:**
- 删除重复行（保留第一条）
- 检查重复的原因
- 建立唯一性约束防止未来重复

---

### 🔴 DUPLICATE_ROWS (完全重复行)

**严重程度:** HIGH

**说明:** 整行数据完全相同

**示例:**
```
Found 3 completely duplicate rows (appears 6 total times including originals)
📍 Locations: Rows: 10, 20, 30
```

**修复方案:**
- 删除重复副本，保留原始行
- 检查数据来源，防止重复导入

---

## 质量分数说明

```
Quality Score: 85/100

80-100: 优秀 🟢 - 数据可以直接使用
60-79:  良好 🟡 - 需要小部分修复
0-59:   需要改进 🔴 - 需要大量清理工作
```

---

## 常见问题

### Q: 行号从 0 开始还是从 1 开始？
**A:** 行号从 0 开始（编程风格）。在 Excel 中第 1 行是标题，数据行从第 2 行开始。
所以如果看到 `Row 0`，在 Excel 中对应第 1 行；`Row 1` 对应第 2 行，以此类推。

### Q: 如何批量修复多个问题？
**A:**
1. 先看位置信息，确认是否是同一个问题的不同实例
2. 用行号选择所有受影响的行
3. 批量操作（删除、填充等）
4. 重新运行数据质量检查验证修复

### Q: 可以忽略某些问题吗？
**A:** 根据严重程度判断：
- HIGH: 建议修复（可能影响分析）
- MEDIUM: 应该修复（可能有隐患）
- LOW: 可选修复（一般不影响分析）

### Q: 修复后如何验证？
**A:** 运行相同的质量检查命令，查看是否已解决。

---

## 修复工作流

### 1. 发现问题
```bash
>>> Check data quality in orders
```

### 2. 分析问题
查看 Locations、Sample rows、Valid range 等信息

### 3. 定位到 Excel
用给定的行号在 Excel 中快速定位

### 4. 修复数据
根据问题类型进行相应的修复

### 5. 重新检查
```bash
>>> Check data quality in orders
```
确认问题已解决，Quality Score 提高

### 6. 继续分析
现在可以放心地进行进一步的数据分析

---

## 最佳实践

✅ **DO:**
- 定期运行数据质量检查
- 优先修复 HIGH 严重程度的问题
- 在导入新数据后立即检查
- 建立数据验证规则防止未来问题

❌ **DON'T:**
- 忽视数据质量问题
- 盲目删除行而不先检查内容
- 用 NULL 填充不应有 NULL 的值
- 不验证修复是否成功就继续分析

---

## 技术细节（高级用户）

### 检测方法

**缺失值 (Missing Values)**
- 检查每列的 NULL 和 NaN 值
- 报告受影响的行号列表
- 高于 10% 则标记为 HIGH 严重程度

**异常值 (Outliers)**
- 使用 IQR (Interquartile Range) 方法
- 范围: Q1 - 1.5×IQR 到 Q3 + 1.5×IQR
- 显示统计偏差百分比

**格式不一致 (Format)**
- 检测日期格式变体 (YYYY-MM-DD, MM/DD/YYYY 等)
- 检测其他模式不一致

**重复值 (Duplicates)**
- ID 列唯一性检查
- 完整行重复检查

### 集成到工作流

```python
from agent.subagents.quality_agent import QualityAgent

result = agent.execute("Check data quality", workbook)

# 提取位置信息进行自动化处理
for issue in result['issues']:
    row_indices = issue.get('row_indices', [])
    # 对这些行进行处理...
```

---

需要帮助？运行 `chat.py` 并输入 `help` 查看所有可用命令。
