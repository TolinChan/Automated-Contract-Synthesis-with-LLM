# Experiment Status & Findings

> 记录当前实验阶段的已知结论、待填补缺口和下一步方向。非设计文档（见 AGENT_LOOP_DESIGN.md），也非结果日志（见 results/*/RESULTS.md）。
> Last updated: 2026-04-29

---

## 1. 已完成的实验

### feas_run_02（2026-04-25 交付给 Haoxian）

**目标**：最小可行性测试 —— 5 个 aptos-framework 函数，spec 固定，body 由 LLM 重新合成，Move Prover 验证。

| 方法 | 配置 | stake_update_perf 外 4 函数 | stake_update_perf（最难） |
|------|------|---------------------------|------------------------|
| B1 zero-shot | spec + signature | 4/4 PASS | FAIL |
| B3 zero-shot | spec + signature + module context | 4/4 PASS | FAIL |
| B6 auto-feedback (1 round) | generic diagnose | 4/4 PASS (大部分 round-0 即过) | FAIL |
| B7 auto-feedback (3 rounds) | generic diagnose | 4/4 PASS | 未跑 |
| **Manual diag** | **手写 structured diagnose（ naming 三个 idiom ）** | — | **PASS (76.95s)** |

**核心结论（已验证）**：
1. Zero-shot LLM 在简单/中等 spec 上表现很好（4/5）。
2. 复杂 spec（ghost var + while invariant + overflow assume）zero-shot 必然失败。
3. **Generic auto-diagnose 无法修复复杂函数** —— 它不懂 Move Prover 特定惯用法。
4. **手写 structured diagnose 可以一轮修复** —— 证明 codegen 能力是够的，瓶颈在 diagnose 质量。

---

## 2. 正在进行的实验（feas_run_03 系列）

**实际身份**：工程迭代 proposed method（structured diagnose with idiom checklist），**不是在补 baseline**。

证据：`scripts/diagnose.py` 已写入 Move-Prover Idiom Checklist（ghost var update、while-header invariant、overflow assume），并包含 `old(...)` 的 HARD CONSTRAINT。

### 各变体结果

| 变体 | 范围 | stake_update_perf 结果 | 关键问题 |
|------|------|----------------------|---------|
| v4 (B6) | 5 函数 | round 0: timeout → round 1: **invalid old(..)** | diagnose 或 codegen 仍引入 `old(...)` |
| v5 (B6) | 4 函数（不含 stake） | — | `chain_id_initialize` round-0 编译错、round-1 修复成功 |
| v5_stake (B6) | 仅 stake | round 0: mem invariant fail → round 1: compile error | 未收敛 |
| v5_stake_b7 (B7) | 仅 stake | round 0: compile error → rounds 1-3: **全部 timeout** | **越反馈越差** |

**关键发现**：
- Proposed method（idiom checklist diagnose）**尚未在 stake_update_perf 上成功**。
- B7（3 轮 feedback）结果比 B6 更差：从编译错误退化到连续 timeout，说明 feedback 不仅没有收敛，反而引入了更多问题。
- 对比 manual diag（一次性给出完整三个 idiom 指令）vs auto-diagnose（每轮只给当前错误的诊断），**auto-diagnose 可能信息不完整** —— 它只诊断当前看到的错误，不预判其他缺失的 idiom。

---

## 3. 缺口：Baseline Suite 不完整

Haoxian 原始要求："先构造 minimal feasibility test，**测出 baseline 方法的 limitation**，然后检验你的方法能不能生成。"

**我们实际做了什么**：
- ✅ 测了 zero-shot 的天花板（B1/B3）
- ✅ 测了 generic feedback 的天花板（B6/B7 with generic diagnose）
- ❌ **没有测 few-shot prompting**
- ❌ **没有测 Chain-of-Thought**
- ❌ **没有测 single-role feedback**（同一个 LLM 既生成又自纠，不分离 codegen/diagnose）
- ❌ 没有和 external related work 方法做对照

**为什么这是问题**：
1. 论文需要证明"formal verifier feedback 有必要"——需要和纯 prompting 方法（few-shot、CoT）做对比。
2. Design doc 的 P1（two-role separation）需要消融验证——需要 single-role baseline 来证明分离 diagnose 有价值。
3. 当前实验链是"zero-shot 失败 → naive feedback 也失败 → 手写 diagnose 能修复 → 自动化 diagnose 还在迭代"，缺少"自动化 diagnose vs naive feedback"的 head-to-head 对照。

---

## 4. 待填补的 Baseline（按优先级）

| Baseline | 描述 | 优先级 | 实现难度 | 验证什么 |
|----------|------|--------|----------|---------|
| **Single-role iterative repair** | 不分离 codegen/diagnose，同一个 LLM 看到 prover error 后直接重写 body | 🔴 最高 | 低（删掉 diagnose 步骤即可）| P1: two-role separation 是否有价值 |
| **Few-shot prompting** | Round-0 prompt 中加 1-2 个正确 spec→code 示例 | 🔴 高 | 低（准备 example pairs）| 示例是否能解决 idiom 缺失问题 |
| **Chain-of-Thought** | Round-0 让 LLM 先分析 spec 需求再写代码 | 🟡 中 | 低（改 prompt）| 推理步骤是否有帮助 |
| **Related work 复现** | FSM-SCG / SpecSyn / Scar 等方法适配到 Move | 🟢 低 | 高 | 外部 SOTA 对比（论文 related work 章节）|

**建议先做 single-role 和 few-shot**：这两个改动最小，但能直接回答"我们的架构设计是否有实证支撑"。

---

## 5. 待解决的问题

### R1: auto-diagnose 为何在 stake_update_perf 上持续失败？

已知 manual diag 能成功，说明信息本身是足够的。auto-diagnose 失败的可能原因：
- **信息不完整**：auto-diagnose 每轮只诊断当前错误，不像 manual diag 一次性列出所有三个 idiom。
- **prompt 过长**：idiom checklist 占用了大量 token，可能导致 diagnose 输出质量下降。
- **codegen 不听从指令**：即使 diagnose 正确，codegen 可能无法在一次重写中同时应用多个复杂惯用法。
- **反馈循环引入新错误**：B7 的结果表明每轮可能修复一个错误但引入另一个。

**验证方法**：对比 manual diag prompt 和 auto-diagnose prompt 的文本差异，检查 auto-diagnose 是否遗漏了关键信息。

### R2: 实验结构混乱

feas_run_03 有 8 个变体（smoke, smoke2, v2-v5, v5_stake, v5_stake_b7），但没有清晰的变量控制：
- 各版本之间 diagnose prompt 的差异是什么？
- 哪些改动有效、哪些无效？
- 没有在一个代码版本上同时跑 baseline 和 proposed method。

**建议**：冻结一个脚本版本，在同一版本上跑（B1 + B3 + B6 generic + B6 idiom + single-role + few-shot），产生可比较的结果。

### R3: 外部相关工作跟踪

近期可能出现撞车的论文：
- [A benchmark for vericoding](https://arxiv.org/html/2509.22908v1) ——  formally verified program synthesis，定位高度重叠。
- [Designing Predictable LLM-Verifier Systems](https://arxiv.org/html/2512.02080v2) —— LLM-verifier 交互可预测性，和 two-role 架构相关。

需要定期追踪，确保我们的 novelty 清晰。

---

## 6. 下一步行动（建议顺序）

1. **整理 feas_run_03 各变体的 diagnose prompt 差异**，明确哪些改动有效、哪些无效。
2. **实现 single-role feedback baseline**：在 `synth_loop.py` 中加一个模式，跳过 diagnose 步骤，直接把 prover error 扔回给同一个 LLM。
3. **实现 few-shot baseline**：准备 1-2 个正确的 spec→code 示例（可以用 coin_extract 和 block_initialize），加进 B3 prompt。
4. **跑一个干净的对比批次**：同一脚本版本、同一模型、同一函数集，同时出（B1 / B3 / single-role / B6 generic / B6 idiom / few-shot）的结果。
5. **分析 auto-diagnose vs manual diag 的 prompt 差异**，找出 auto-diagnose 缺失的关键信息。
