# MoVES 语义完整性人工审计 Rubric

> 版本：1.0
> 日期：2026-05-21
> 目的：对 Move Prover 通过的合成函数进行人工语义审计，检测 false-verified 案例

---

## 1. 背景

Move Prover 通过 **不等于** 语义正确。已有证据：
- GPT 5.5 在 `stake_update_perf` 上 Prover 通过，但**遗漏了整个 `failed_proposer_indices` 循环**
- Kimi + auto-diagnose 在 `stake_update_perf` 上 Prover 通过，但**遗漏了 while-header invariant 和 overflow assume**

因此，对每个 Prover 通过的函数，必须进行人工语义审计。

---

## 2. 审计流程

### 2.1 审计者
- 至少 1 名熟悉 Move 语言和目标函数的审计者
- 建议 2 名独立审计者，对分歧 case 讨论后达成一致

### 2.2 审计对象
- **仅审计 Prover 通过的函数**（exit_code == 0）
- Prover 失败的函数直接标记为失败，无需审计

### 2.3 审计输入
1. `reference_body.txt`（参考实现）
2. `extracted_body.txt`（LLM 生成的实现）
3. `spec.txt`（形式化规范）
4. `verify.json`（Prover 输出，确认 passed=True）

### 2.4 审计步骤

```
Step 1: 阅读 spec，列出该函数的所有语义义务（参见 §3 模板）
Step 2: 对比 reference_body 和 extracted_body
Step 3: 逐条义务打分（0-3 分，参见 §4）
Step 4: 计算 Semantic Coverage Score (SCS)
Step 5: 判定是否 false-verified
Step 6: 记录未通过的义务及原因
```

---

## 3. 语义义务模板

每个函数的义务清单因复杂度而异。以下按层级给出模板，审计者根据具体函数调整。

### 3.1 L1 Trivial 义务清单（2-3 项）

| 义务 ID | 检查内容 | 说明 |
|---------|---------|------|
| O1 | 返回值正确 | 函数是否返回 spec 要求的值 |
| O2 | 无副作用 | 纯读取函数是否确实未修改任何状态 |
| O3 | 不 abort | `aborts_if false` 的函数是否确实无 assert/abort |

### 3.2 L2 Simple 义务清单（3-4 项）

| 义务 ID | 检查内容 | 说明 |
|---------|---------|------|
| O1 | 成功路径状态更新正确 | `ensures` 描述的状态变化是否实现 |
| O2 | 失败路径处理正确 | `aborts_if` 条件是否正确触发（参数检查、exists 检查等） |
| O3 | 资源创建/销毁正确 | `move_to`、`move_from` 等是否正确使用 |
| O4 | 常量/辅助函数使用正确 | 是否使用了正确的常量、是否调用了正确的 sibling 函数 |

### 3.3 L3 Medium 义务清单（4-5 项）

| 义务 ID | 检查内容 | 说明 |
|---------|---------|------|
| O1 | 成功路径状态更新正确 | `ensures` 描述的状态变化是否完整实现 |
| O2 | 失败路径处理正确 | 所有 `aborts_if` 条件是否覆盖 |
| O3 | Modifies 义务完整 | `modifies` 声明的每个资源是否都被正确修改 |
| O4 | Schema 包含的义务满足 | 被 `include` 的 schema 中的条件是否满足 |
| O5 | 边界条件处理 | 空 vector、Option::none 等边界情况 |

### 3.4 L4 Complex 义务清单（5-6 项）

| 义务 ID | 检查内容 | 说明 |
|---------|---------|------|
| O1 | 成功路径状态更新正确 | 核心状态变化是否实现 |
| O2 | 失败路径处理正确 | `aborts_if` 条件覆盖 |
| O3 | **Ghost 变量更新** | 模块级 ghost 变量是否通过 `spec { update ... }` 正确同步 |
| O4 | **Loop invariant 结构** | Invariant 是否放在 while-header 中（`while ({ spec { invariant ... }; cond })`） |
| O5 | **Overflow assume 完整** | 每个 `u64` 自增/加法前是否有 `spec { assume X + 1 <= MAX_U64; }` |
| O6 | 循环逻辑完整 | 循环是否遍历了所有应遍历的元素，循环体内逻辑是否正确 |

---

## 4. 评分标准

每条义务独立打分：

| 分数 | 描述 | 判定标准 |
|------|------|---------|
| **3** | 完全满足 | 与 reference body 语义等价，或等价变体（不同写法但效果相同） |
| **2** | 部分满足 | 有该逻辑但不够完整（如处理了大部分情况但漏了某个边界） |
| **1** | 表面满足 | 有语法但语义错误（如写了 loop 但逻辑错误、写了 assume 但条件不对） |
| **0** | 完全缺失 | 该义务对应的逻辑完全不存在 |

### 4.1 等价变体的判定

以下情况视为与 reference body **语义等价**，可打 3 分：
- 使用 `if-else` 替代 `match`
- 使用不同的临时变量名
- 将 `a = a + 1` 写成 `a = a + 1`（只要 overflow assume 完整）
- 调整语句顺序但不影响最终状态

以下情况**不等价**，不能打 3 分：
- 遗漏了某个分支或循环
- 使用了不同的条件判断（如 `>=` 写成 `>`）
- 遗漏了 ghost variable update
- Loop invariant 放在错误位置

---

## 5. False-Verified 判定

### 5.1 定义

一个函数如果满足以下两个条件，则判定为 **false-verified**：
1. Move Prover 通过（exit_code == 0）
2. 语义覆盖度不足（SCS < 0.8 或任何一项 O3-O6 义务得 0 分）

### 5.2 Semantic Coverage Score (SCS)

```
SCS = (所有义务得分之和) / (满分 = 3 × 义务数量)
```

| SCS 范围 | 评级 |
|---------|------|
| 1.0 | 完全语义等价 |
| 0.8 - 0.99 | 轻微不完整（可接受） |
| 0.6 - 0.79 | 明显不完整 |
| < 0.6 | 严重不完整 |

**False-verified 判定**：SCS < 0.8 **或** 任何一项 O3-O6（核心 idiom 义务）得 0 分。

> 为什么 O3-O6 单独判定：Ghost var update、loop invariant placement、overflow assume 是 Move-Prover-specific idiom，遗漏这些意味着 LLM 不理解验证器的要求，即使 Prover 通过也是"侥幸"。

### 5.3 False-Verified Rate（报告指标）

```
False-verified Rate = (false-verified 函数数量) / (Prover 通过的函数数量)
```

---

## 6. 审计记录模板

对每个审计的函数，填写以下记录：

```markdown
### Function: <function_id>

- **Prover passed**: Yes/No
- **Total obligations**: N
- **Obligation scores**:
  - O1 (成功路径): 3/2/1/0
  - O2 (失败路径): 3/2/1/0
  - ...
- **SCS**: 0.XX
- **False-verified**: Yes/No
- **Missing obligations** (if any):
  - <具体描述遗漏了什么>
- **Notes**:
  - <其他观察>
```

---

## 7. 审计者间一致性验证

在正式审计前，两名审计者用本 rubric 对以下 3 个 sample case 独立打分：

1. `chain_id_get`（L1，简单，应一致通过）
2. `coin_extract`（L3，中等复杂度）
3. `stake_update_perf`（L4，最复杂，已知的 false-verified 案例）

计算 **Cohen's Kappa 系数**：
- Kappa > 0.8：一致性良好，可开始正式审计
- Kappa 0.6-0.8：讨论分歧点，统一标准后再开始
- Kappa < 0.6：修订 rubric，重新培训

---

## 8. 已知 False-Verified 案例参考

| 函数 | 模型 | 遗漏的义务 | 原因 |
|------|------|-----------|------|
| `stake_update_perf` | GPT 5.5 zero-shot | O3, O4, O5, O6 | 完全遗漏 failed_proposer_indices 循环和全部 idiom |
| `stake_update_perf` | Kimi + auto-diag | O4, O5, O6 | Ghost var 修复了，但 loop invariant 和 overflow assume 仍缺失 |

---

## 9. 与 Related Work 的对比

| 工作 | 完整性检验方法 | 与 MoVES 的差异 |
|------|--------------|----------------|
| **Clover** | 6 边一致性检验（code↔annotation↔docstring） | Clover 用 LLM 做一致性判断（"LLM 判 LLM"）；MoVES 用 Move Prover 做真值源，人工审计做补充 |
| **MSG** | 随机删除覆盖率（规范完整性） | MSG 检查 spec 是否完整覆盖 code；MoVES 检查 code 是否完整实现 spec（反方向） |
| **RePair** | 测试用例通过率 | RePair 用单元测试判断正确性；MoVES 用形式化验证 + 人工审计 |

---

## 10. 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0 | 2026-05-21 | 初版，基于 feas_run_02 的 motivating example 经验定义 |
