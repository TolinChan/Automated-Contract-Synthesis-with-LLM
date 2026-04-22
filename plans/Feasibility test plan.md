## 0. 核心问题

给定 Move Specification，LLM 能不能生成通过 Move Prover 验证的代码？

如果不加反馈循环不能，那加上反馈循环能不能？

---

## 1. 输入假设（设计约束）

### 1.1 Spec 语言

- **语言**：Move Specification Language（Move Prover 的 spec block）
- **格式**：结构化的 `requires` / `aborts_if` / `ensures` / `modifies` 子句
- **来源**：人工从 aptos-framework 源码中提取，**不做 NL→Spec 转换**
- **原因**：NL→Spec 不可自动验证

### 1.2 输入内容

| 字段                   | 内容                                           | 来源                     |
| ---------------------- | ---------------------------------------------- | ------------------------ |
| **Spec**               | requires/aborts_if/ensures/modifies            | 数据集给定               |
| **Function Signature** | `public(friend) fun name(params): return_type` | 数据集给定               |
| **Module Context**     | imports, constants, structs, sibling functions | 从源码提取               |
| **Cross-module API**   | 目标函数可能调用的外部模块函数签名             | **待定**                 |
| **NL Intent**          | 函数的自然语言描述（可选）                     | 数据集给定，当前实验不用 |

### 1.3 输出

- **纯 Function Body**（不含 signature、imports、module 声明）
- 替换到源码中编译 + Move Prover 验证

---

## 2. 为什么这样设计

### 2.1 为什么 Spec→Code，不是 NL→Spec→Code

**原因**：
1. 如果做 NL→Spec，多了一步不可验证的转换。我们无法自动判断"Spec 是否准确表达了 NL Intent"
2. 先搞清楚 Spec→Code 能不能做，再加 NL→Spec 才是合理顺序
3. Aptos Framework 里的函数本来就有人工写的 spec，可以直接拿来用

**代价**：实验结果不能推广到"从自然语言生成代码"的场景

### 2.2 为什么 Module Context 只给同模块信息

**原因**：
1. 同模块的 imports、constants、structs 容易自动提取
2. 跨模块 API 签名太多（Aptos Framework 有几百个函数），全部塞进去会超 token limit
3. 测试 LLM 在**有限上下文**下的表现，这是真实场景（LLM 有上下文窗口限制）

**问题**：LLM 会猜错跨模块 API 的参数类型（实验中已证实）

### 2.3 为什么只生成 Function Body，不生成完整模块

**原因**：
1. 模块结构（imports、structs、其他函数）已经是正确的，不需要 LLM 重造
2. 减少 LLM 的输出复杂度，聚焦核心任务：把 spec 翻译成代码逻辑
3. 验证时只替换 body，可以复用正确的模块上下文

---

## 3. Feasibility Test 流程设计

### 3.1 Step 1: Baseline 覆盖

Cover 之前 survey 过的所有 baseline 方法：

| #    | 方法                          | 输入                                                        | 设计动机                                        |
| ---- | ----------------------------- | ----------------------------------------------------------- | ----------------------------------------------- |
| B1   | **Zero-shot**                 | Spec + Signature                                            | 测 LLM 纯推理能力，不加任何引导                 |
| B2   | **Few-shot**                  | Spec + Signature + 同模块 examples                          | 测 LLM 模仿能力，看 examples 是否能传递正确模式 |
| B3   | **Enhanced (Module Context)** | Spec + Signature + Imports + Constants + Structs + Siblings | 测信息补全能否减少 API/常量误用（待定）         |
| B4   | **Enhanced + Examples**       | B3 + Few-shot examples                                      | 测两者叠加效果（待定）                          |
| B5   | **MSG-style (Spec Check)**    | 生成后做一次 spec completeness check                        | 测 spec 完整性检查能否过滤掉明显错误的生成      |
| B6   | **Error Feedback (1 round)**  | B3 生成 → 编译错误 → 反馈给 LLM → 修复                      | 核心测试：feedback loop 的第一步价值            |
| B7   | **Error Feedback (3 rounds)** | B6 重复最多 3 轮                                            | 测 feedback loop 的收敛性                       |

**为什么 cover 这些**：
- B1-B2 是传统 LLM 编程的标准做法，必须建立 baseline
- B3-B4 测试"信息补全"的效果，验证我们提供 module context 的假设（待定）
- B5 验证 MSG 论文的核心思想（spec check）对我们的场景是否有帮助
- B6-B7 验证本文的核心创新（feedback loop）是否有效

### 3.2 Step 2: 验证链路

```
生成 Function Body
      ↓
替换到源码中
      ↓
aptos move compile
      ↓
编译通过？
  ├─ 是 → aptos move prove → 验证通过？
  │              ├─ 是 → ✅ 成功
  │              └─ 否 → 提取 Move Prover 错误 → 进入 Feedback
  └─ 否 → 提取编译错误 → 进入 Feedback
```

### 3.3 Step 3: Feedback Loop 设计

```
编译错误 / 验证错误
      ↓
[Error Diagnosis Agent]
  - 分类错误类型
  - 定位出错代码位置
  - 判断是 Spec 问题还是 Code 问题
      ↓
[修复策略]
  - API 参数错误 → 提示正确参数类型（从源码查签名）
  - 常量不存在 → 提示可用常量列表
  - Import 缺失 → 提示需要添加的 use 语句
  - Spec 违反 → 提示哪个 spec 子句被违反
      ↓
LLM 重新生成 / 局部修改
      ↓
回到验证链路
```

**为什么这样设计**：
1. 直接给原始错误日志太杂，LLM 可能看不懂或抓错重点
2. Error Diagnosis Agent 做结构化解析，给出清晰的修复指令
3. 区分"编译错误"（语法/类型）和"验证错误"（语义/spec 违反），修复策略不同

### 3.4 Step 4: 评估指标

| 指标                        | 定义                       | 为什么重要                         |
| --------------------------- | -------------------------- | ---------------------------------- |
| **Compilation Pass Rate**   | 编译通过数 / 总数          | 基础门槛。编译不过就没法验证       |
| **Verification Pass Rate**  | Move Prover 通过数 / 总数  | 核心指标。验证通过 = 代码满足 spec |
| **Avg Feedback Rounds**     | 成功修复需要的平均轮数     | 测 feedback loop 效率              |
| **Error Type Distribution** | 编译错误 vs 验证错误的占比 | 判断主要瓶颈在哪                   |
| **Unfixed Error Rate**      | 3 轮后仍未修复的比例       | 测 feedback loop 的上限            |

---

## 4. 实验配置

### 4.1 数据集

- **来源**：aptos-framework（48 个函数，24 个有非 trivial spec）
- **抽样**：5 个代表性函数（简单到复杂覆盖）
- **选样标准**：
  - 简单（<10 行，1-2 spec 子句）：`chain_id::get`
  - 中等（10-30 行，2-4 spec 子句）：`coin::initialize`
  - 复杂（>30 行，>4 spec 子句）：`stake::update_performance_statistics`

**为什么选 5 个而不是全部 48 个**：
- Feasibility test 的目的是验证**方法是否可行**，不是测最终准确率
- 5 个函数足够暴露系统性问题（API 参数错误、常量缺失等）
- 全部 48 个跑一轮成本太高，等方法验证有效后再 scale up

### 4.2 LLM 配置

- **模型**：kimi-for-coding
- **Temperature**：0.2（低随机性，保证可重复性）
- **Max tokens**：2000

### 4.3 验证环境

- **Move Prover**：aptos CLI built-in
- **Boogie**：3.5.1（Move Prover 要求 ≤ 3.5.1）
- **Z3**：4.12.2（要求 ≥ 4.11.2）
- **验证方式**：修改源码替换 function body，再 compile + prove

---

## 5. 待定事项

| #    | 待定内容                                          | 影响                                  | 建议决策方向                                                 |
| ---- | ------------------------------------------------- | ------------------------------------- | ------------------------------------------------------------ |
| D1   | 是否提供跨模块 API 签名？                         | 高。LLM 当前常因 API 参数类型错误失败 | 先不提供，测试纯 module context 的上限；feedback loop 中按需查询 |
| D2   | Feedback prompt 的具体格式                        | 高。决定 LLM 修复效果                 | 先设计 2-3 个变体，A/B test                                  |
| D3   | Error Diagnosis Agent 是规则-based 还是 LLM-based | 中。规则快但覆盖不全，LLM 慢但灵活    | Phase A 用规则（快速验证概念），Phase B 换 LLM               |
| D4   | 是否测试 NL Intent 输入？                         | 中。当前设计排除 NL→Spec              | Phase A 不测，Phase B 可加一条 baseline                      |
| D5   | 是否加入 PropertyGPT / Clover 的 baseline？       | 低。这些方法不是 Spec→Code            | 不加入。这些方法是 Property-based / Fuzzing，与我们的 Spec-driven 范式不同 |
| D6   | 是否加入 RePair 的 Error-driven baseline？        | 中。RePair 也是 error feedback        | 加入作为对比。RePair 从代码生成 spec（反方向），可以测试 error feedback 在 Spec→Code 方向是否同样有效 |
| D7   | 函数抽样策略是否科学？                            | 中。5 个函数可能不够 representative   | 可先按复杂度分层抽样，后续扩大到 10-15 个                    |

---

## 6. 预期输出

Feasibility Test 完成后，应有：

1. **数据表**：每个 baseline 在每个函数上的编译/验证结果
2. **错误分析**：失败案例的错误类型分类
3. **Feedback Loop 效果**：修复成功率、平均轮数、不可修复错误列表
4. **结论**：
   - Feedback loop 是否有效？
   - 如果可以，进入 Phase B（扩大数据集 + 优化 feedback prompt）
   - 如果不行，分析根本原因，调整设计

---

## 
