# MoVES 实验执行计划

> 状态：定稿（2026-05-21）
> 本计划整合 MSG（ASE'25）、Clover（arXiv 2310.17807）、RePair（arXiv 2408.11296）、SYSSPEC（FAST'26）的实验设计模式。

---

## 1. 设计原则（借鉴 Related Work）

| 来源 | 核心模式 | 在 MoVES 中的落地 |
|------|---------|-----------------|
| **MSG** | 357 函数规模、3 次重复、模块化 agent 消融、随机删除覆盖度 | 24 函数 × 3 次重复（减少随机方差）；消融实验验证 two-role vs single-role |
| **Clover** | 对抗样本（4 类 adversarial）、6 边一致性检验、per-check breakdown、0% false-positive 目标 | 人工审计 5 项语义义务作为"对抗检验"；对通过 case 做义务覆盖度打分 |
| **RePair** | Easy/Medium/Hard 分层、pass@k、过程监督消融 | L1-L4 分层已对齐；pass@1 对应 B1/B3，rounds_to_success 对应 B6/B7；消融验证"过程监督"价值 |
| **SYSSPEC** | 渐进式消融（功能 → +模块化 → +并发）、多模型对比 | B1→B3→B6→B7 已是渐进式；多模型对比（Kimi/Claude/GPT）在 L4 case 上 |

---

## 2. Benchmark 选择

采用方案 B（24 个函数，L4 实际为 2 个——aptos-framework 中大量复杂函数被 `pragma verify = false;` 禁用，此为真实约束），分层覆盖 L1-L4：

### 2.1 分层定义

| 层级 | 定义 | 测试能力 |
|------|------|---------|
| **L1 Trivial** | 纯读取、无 abort / `aborts_if false`，spec < 5 行 | 验证 baseline 天花板；任何方法都应 100% 通过 |
| **L2 Simple** | `aborts_if` + `ensures`，无 loop/ghost，5-15 行 spec | 基础 codegen 能力；测试 LLM 对条件与后置条件的理解 |
| **L3 Medium** | `modifies` / schema / 多条件 / 15-30 行 spec | 测试 schema 包含、状态修改、跨函数引用 |
| **L4 Complex** | loop / invariant / ghost / >30 行 spec / 跨模块依赖 | 测试 Move-Prover 专用 idiom（ghost var、while-header invariant、overflow assume）|

### 2.2 函数列表（24 个）

| # | 函数 | 模块 | 层级 | 状态 |
|---|------|------|------|------|
| 1 | `chain_id::get` | chain_id | L1 | feas_run_02 已验证 |
| 2 | `guid::id` | guid | L1 | sanity check PASS |
| 3 | `guid::creator_address` | guid | L1 | sanity check PASS |
| 4 | `guid::eq_id` | guid | L1 | sanity check PASS |
| 5 | `coin::is_coin_initialized` | coin | L1 | sanity check PASS |
| 6 | `coin::is_account_registered` | coin | L1 | sanity check PASS |
| 7 | `chain_id::initialize` | chain_id | L2 | feas_run_02 已验证 |
| 8 | `guid::create` | guid | L2 | sanity check PASS |
| 9 | `version::initialize` | version | L2 | sanity check PASS |
| 10 | `account::get_sequence_number` | account | L2 | sanity check PASS |
| 11 | `account::create_account_if_does_not_exist` | account | L2 | sanity check PASS |
| 12 | `account::create_account` | account | L2 | sanity check PASS |
| 13 | `coin::merge` | coin | L2 | sanity check PASS |
| 14 | `staking_contract::stake_pool_address` | staking_contract | L2 | sanity check PASS |
| 15 | `coin::extract` | coin | L3 | feas_run_02 已验证 |
| 16 | `block::initialize` | block | L3 | feas_run_02 已验证 |
| 17 | `version::set_version` | version | L3 | sanity check PASS |
| 18 | `account::increment_sequence_number` | account | L3 | sanity check PASS |
| 19 | `staking_contract::update_voter` | staking_contract | L3 | sanity check PASS |
| 20 | `staking_contract::create_staking_contract` | staking_contract | L3 | sanity check PASS |
| 21 | `staking_contract::create_staking_contract_with_coins` | staking_contract | L3 | sanity check PASS |
| 22 | `staking_contract::request_commission` | staking_contract | L3 | sanity check PASS |
| 23 | `stake::update_performance_statistics` | stake | L4 | feas_run_02 已验证 |
| 24 | `staking_contract::add_stake` | staking_contract | L4 | sanity check PASS |

> **关于 L4 数量**：aptos-framework 中复杂函数（含 loop/ghost/invariant）大多被 `pragma verify = false;` 禁用。24 个函数中仅 2 个 L4，但这恰是真实约束——Move Prover 的验证开销使得复杂函数在生产代码中常被禁用。若需更多 L4，可从 `move-examples` 中补充。

### 2.3 每层内部的 spec 梯度（借鉴 RePair）

每层内部按 spec 行数/条件数量进一步排序，确保同层内也有难度梯度：

- **L1**：`chain_id_get` (1 spec line) → `guid_id` (2 spec lines) → ... → `coin_is_account_registered` (4 spec lines)
- **L2**：`chain_id_initialize` (6 spec lines) → ... → `coin_merge` (8 spec lines)
- **L3**：`coin_extract` (10 spec lines) → ... → `staking_contract_create_staking_contract_with_coins` (25+ spec lines)
- **L4**：`staking_contract_add_stake` (35+ spec lines) → `stake_update_perf` (45+ spec lines)

---

## 3. 实验矩阵

### 3.1 主实验

| Baseline | 输入 | 轮次 | 追踪指标 | 验证什么 |
|----------|------|------|----------|---------|
| **B1** | signature + spec | 0 | Pass@1 | Zero-shot 无上下文天花板 |
| **B3** | signature + spec + module_context | 0 | Pass@1 | Zero-shot 有上下文天花板 |
| **B6** | B3 + 1 轮 auto-diagnose feedback | 1 | rounds_to_success | 最小 feedback 是否有效 |
| **B7** | B3 + 3 轮 auto-diagnose feedback | 3 | rounds_to_success | 增加 budget 是否改善 |
| **Manual-diag** | B3 + 1 轮手写 structured diagnosis | 1 | rounds_to_success | Codegen 能力是否足够（控制变量：用完美 diagnosis 测试 codegen ceiling）|

### 3.2 消融实验（借鉴 MSG 组件消融 + RePair 过程监督消融）

| 消融项 | 与 B3/B6 的差异 | 验证哪个设计原则 | 抽样策略 |
|--------|----------------|-----------------|---------|
| **Single-role** | 同一 LLM 同时生成+诊断，不分离 diagnose 角色；prover stderr 直接扔进 feedback prompt | P1: Two-role separation | 5 个代表性函数（L1×1 + L2×2 + L3×1 + L4×1） |
| **Few-shot** | Round-0 prompt 加 1-2 个同模块已验证函数的 {spec + body} 示例 | 验证是否需要 feedback loop（若 Few-shot 已达 B6 水平，则 feedback loop 价值有限） | 5 个代表性函数 |
| **CoT** | Round-0 让 LLM 先分析 spec（"先逐条解释 requires/aborts_if/ensures/modifies 的含义"），再输出 body | 验证 spec 理解能力 | 5 个代表性函数 |

> **为什么只抽样 5 个函数跑消融**：消融实验的目的是验证**设计原则**，不是测最终准确率。5 个函数足够暴露系统性差异（如 Single-role 在 ghost var 上持续失败），且 API 成本可控。

### 3.3 跨模型对照（借鉴 SYSSPEC 多模型对比）

| 模型 | 场景 | 目的 |
|------|------|------|
| Kimi-for-coding | 全部 24 个函数 × 3 次重复 | 主实验 |
| Claude Opus 4.7 | L4 全部 + L3 抽样 3 个 | 验证最难 case 上模型能力差异 |
| GPT 5.5 | L4 全部 + L3 抽样 3 个 | 验证 hardest case 上是否存在 false-verified（GPT 5.5 在 stake_update_perf 上已发现此问题） |

> **重复次数**：借鉴 MSG 的 3 次重复，Kimi 主实验每个函数跑 3 次（temperature=0.2），报告均值和方差。消融和跨模型对照因成本限制，跑 1 次。

---

## 4. 指标设计（三层，借鉴 Clover per-check breakdown）

### 4.1 第一层：验证结果

| 指标 | 定义 | 适用 baseline |
|------|------|--------------|
| **Pass@1** | Round 0 通过率（无任何 feedback） | B1, B3 |
| **rounds_to_success** | 第几次尝试通过（1=round 0, 2=第 1 轮 feedback 后通过，...） | B6, B7, Manual-diag |
| **Compilation Pass Rate** | 编译通过数 / 总数 | 全部 |
| **Fail@k** | k 轮后仍未修复的比例 | B6, B7 |

### 4.2 第二层：语义完整性（核心差异化指标，借鉴 Clover 对抗检验）

**问题**：Verifier 通过 ≠ 语义正确。GPT 5.5 在 `stake_update_perf` 上 verifier 通过但遗漏了整个 `failed_proposer_indices` 循环（见 motivating example）。

**检测方法**：人工审计（5 项义务检查表）

对每个通过 verifier 的函数，审计者逐条检查以下义务（类似 Clover 的 per-check breakdown）：

| 义务 # | 检查内容 | 适用层级 |
|--------|---------|---------|
| O1 | 成功路径状态更新正确 | 全部 |
| O2 | 失败/边界路径处理正确（aborts_if 条件是否被正确触发） | L2-L4 |
| O3 | Ghost 变量更新正确（`spec { update ghost_xxx = ... }`） | L4 |
| O4 | Loop invariant 结构正确（while-header 放置） | L4 |
| O5 | Overflow assume 完整（每个 `u64` 自增/加法前有 assume） | L4 |

**评分标准**：
- 3 分：完全满足（与 reference body 语义等价）
- 2 分：部分满足（有该逻辑但不够完整）
- 1 分：表面满足（有语法但语义错误）
- 0 分：完全缺失

**派生指标**：
- **False-verified rate**：验证通过但总分 < 满分 × 80% 的比率
- **Semantic Coverage Score (SCS)**：平均义务得分 / 满分
- **Per-obligation breakdown**：每个义务在所有函数上的通过率（类似 Clover 的 per-check 表）

> **可重复性**：两名独立审计者用同一 rubric 对 3 个 sample case 预打分，Cohen's Kappa > 0.8 方可正式审计。

### 4.3 第三层：效率与成本

| 指标 | 为什么重要 |
|------|-----------|
| Avg Prove Time | Move Prover 开销是瓶颈之一 |
| Avg LLM Tokens per round | API 成本估算 |
| Total API calls | 总成本 |
| Avg Feedback Rounds（成功 case） | feedback loop 效率 |

---

## 5. 执行顺序

```
Phase 0: 24 函数提取 + sanity check（已完成 ✅）
Phase 1: B1/B3 全部 24 个（Kimi，3 次重复）← 当前优先
Phase 2: B6/B7 跑 Phase 1 失败的 case
Phase 3: Manual-diag 跑 Phase 2 仍失败的 case
Phase 4: 消融实验（Single-role / Few-shot / CoT，抽样 5 个代表性函数）
Phase 5: 跨模型对照（Claude/GPT 跑 L4 + L3 抽样）
Phase 6: False-verified 人工审计（对所有通过的 case 执行义务检查）
```

---

## 6. Evaluation 章节结构（论文 §5）

- **§5.1 Setup**：数据集（24 函数分层）、模型（Kimi/Claude/GPT）、环境（Aptos CLI 9.1.0, Boogie 3.5.1, Z3 4.13.0）、baseline 定义
- **§5.2 RQ1**：Zero-shot 天花板（B1 vs B3，Pass@1，3 次重复取均值）
- **§5.3 RQ2**：Feedback loop 价值（B3 vs B6/B7，rounds_to_success 分布）
- **§5.4 RQ3**：瓶颈定位（Auto-diag vs Manual-diag，隔离 diagnose 质量）
- **§5.5 RQ4**：语义完整性审计（False-verified rate、SCS、per-obligation breakdown）
- **§5.6 Ablation**：Single-role / Few-shot / CoT（抽样 5 函数）
- **§5.7 Cross-model**：Kimi vs Claude vs GPT（L4 + L3 抽样）
- **§5.8 Discussion**：成本、局限、威胁（L4 样本少、人工审计主观性）

---

## 7. 与 Related Work 的实验设计对比

本节用于论文 Related Work 或 Evaluation 中，说明我们的实验设计如何从 prior work 中借鉴并差异化。

### 7.1 从 MSG 借鉴

- **分层抽样**：MSG 按 clause 类型分层（aborts_if / ensures / modifies / loop_invariant agents），我们按函数复杂度分层（L1-L4）。
- **3 次重复**：MSG 报告 3 次试验均值，我们同样采用 3 次重复减少随机方差。
- **差异**：MSG 评估的是 spec **生成**（Code → Spec），我们评估的是 code **生成**（Spec → Code），指标不可直接对比，但实验结构（分层 + 重复 + 消融）可借鉴。

### 7.2 从 Clover 借鉴

- **对抗检验**：Clover 用 4 类 adversarial variants 检验 false positive；我们用**人工审计义务清单**达到同样目的（ verifier 通过但语义不完整）。
- **Per-check breakdown**：Clover 报告 6 条 consistency edge 各自的通过率；我们报告 5 项语义义务各自的通过率。
- **差异**：Clover 依赖 LLM 做 docstring/annotation 一致性判断（"LLM 判 LLM"），我们用 Move Prover 做唯一真值源，人工审计仅用于语义完整性（不替代 verifier）。

### 7.3 从 RePair 借鉴

- **Easy/Medium/Hard 分层**：RePair 按题目通过率分层；我们按 spec 复杂度（行数/条件数/idiom 需求）分层。
- **pass@k**：RePair 用 pass@1/@3/@5；我们用 Pass@1（zero-shot）和 rounds_to_success（feedback loop）。
- **过程监督消融**：RePair 消融"无过程监督"和"无反馈"；我们消融"无 structured diagnose"（Single-role）和"无 feedback loop"（Few-shot）。

### 7.4 从 SYSSPEC 借鉴

- **渐进式消融**：SYSSPEC 从功能规约 → +模块化 → +并发规约；我们从 signature+spec → +module_context → +feedback loop → +structured diagnose。
- **多模型对比**：SYSSPEC 对比 Gemini/DeepSeek/Qwen；我们对比 Kimi/Claude/GPT。

### 7.5 MoVES 的独特之处

- **Two-role separation + structured diagnose 的组合尚未被 prior work 系统评估**：MSG 有模块化 agents 但无 code generation；Clover 有 verifier-in-the-loop 但无 producer/diagnoser 分离；RePair 有过程反馈但无 domain-idiom 桥接。
- **False-verified 作为核心指标**：Prior work（MSG, Clover）报告 verifier 通过率，但未系统报告"verifier 通过但语义不完整"的比率。MoVES 将 false-verified rate 作为与 Pass@1 并列的一级指标。

---

## 8. 待决策问题（已解决）

| # | 问题 | 决策 | 原因 |
|---|------|------|------|
| 1 | Benchmark 数量：15 vs 25？ | **24 个**（L1:6 + L2:8 + L3:8 + L4:2） | 25 个原计划中 L4 只有 2 个可用，保持 24 个确保统计可靠性同时不虚构数据 |
| 2 | 消融实验范围 | **Single-role + Few-shot + CoT 都做**，每个抽样 5 函数 | 三个验证不同设计假设，均高优先级 |
| 3 | 跨模型对照范围 | **L4 全部 + L3 抽样 3 个** | L4 是模型能力差异最显著的区域；L3 抽样验证中等复杂度上的差异 |
| 4 | False-verified 检测方法 | **人工审计（5 项义务检查表）** | Clover 的对抗样本方法需要构造变体，对我们的场景不适用；人工审计更直接 |
| 5 | 重复次数 | **Kimi 主实验 3 次，消融/跨模型 1 次** | 平衡统计可靠性与 API 成本 |
