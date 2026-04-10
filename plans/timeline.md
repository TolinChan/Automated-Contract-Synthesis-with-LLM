# 项目时间线

**课题**: Automated Contract Synthesis and Repair with Large Language Models
**开始**: 2026-04-09  
**目标**: 完成可投稿论文（系统论文 / 实证研究）

---

## 已完成（截至 2026-04-10）

| 里程碑 | 完成时间 | 产物 |
|--------|----------|------|
| 8 篇核心文献调研 | 2026-04-09 | `paper/related_work/survey.md` + 各篇笔记 |
| PoC 可行性验证（T0/T1/T2） | 2026-04-09 | `experiments/poc_logs/` |
| T0–T2 + M1–M3 基线任务集 | 2026-04-09 | `src/baseline_tasks/` + E 盘 Move 包 |
| H1 Pass@1 基线（GPT-4o，T0–T2） | 2026-04-09 | `src/baseline_tasks/RESULTS_LOG.md` |

---

## Phase 1 — 完成相关工作调研（2026-04-10 ~ 2026-04-24）

**目标**: 形成可写入论文 Related Work 节的完整文献综述。

### 任务

| # | 任务 | 产物 |
|---|------|------|
| 1.1 | 补充 2–3 篇遗漏方向（Move/Rust 形式化验证、LLM code repair 近期工作） | `paper/related_work/` 新增笔记 |
| 1.2 | 在 `paper/related_work/survey.md` 中整理分类表（方法 × 语言 × 验证器） | 更新 survey.md |
| 1.3 | 明确本工作与 PropertyGPT / Clover / DafnyBench 的核心差异点 | `doc/findings.md` 补充 gap analysis |
| 1.4 | 起草 Related Work 节草稿（~600 字） | `paper/related_work.md`（新建） |

**交付物**: 可引用文献 ≥ 12 篇；Related Work 初稿。

---

## Phase 2 — Spec 驱动输入层重设计 + 可行性测试（2026-04-25 ~ 2026-05-09）

**目标**: 修复当前 error-driven 输入问题（见 `doc/research-state.yaml` key_design_decision_needed），完成全量基线跑通。

### 任务

| # | 任务 | 产物 |
|---|------|------|
| 2.1 | 重写 T0/T1 PROMPT.txt：前置 spec {} 语义解释，而非直接贴 fail.log | `src/baseline_tasks/t0_*/PROMPT.txt` |
| 2.2 | 重写 T2/M1–M3 PROMPT.txt：以 assert!/test oracle 为核心 | `src/baseline_tasks/t2_*/PROMPT.txt` 等 |
| 2.3 | 清理 fail.log 噪声（NativeCommandError 头、乱码路径）预处理脚本 | `src/utils/clean_fail_log.py` |
| 2.4 | 运行 Baseline A（API 单轮）全量 6 个任务，记录 Pass@1 | `experiments/H1_pass1_vs_loop/` |
| 2.5 | 运行 Baseline B（agent_verify_loop）全量 6 个任务，记录 rounds_to_success | 同上 |

**交付物**: T0–T2 + M1–M3 各任务的 Pass@1 与 rounds_to_success 数据表。

---

## Phase 3 — 多模型对比 Benchmark（2026-05-10 ~ 2026-05-24）

**目标**: 测试 H3（模型能力对复杂任务的影响），为改进方案提供数据基础。

### 任务

| # | 任务 | 模型 |
|---|------|------|
| 3.1 | 在全量 6 任务上跑 Pass@1 | GPT-4o、Claude 3.5 Sonnet、GPT-4o-mini |
| 3.2 | 在 M1–M3 上跑 rounds_to_success | 同上 |
| 3.3 | 分析失败模式：语法错误 vs 语义错误 vs 规约误解 | `doc/findings.md` |
| 3.4 | 确认改进空间：哪类错误是系统性可修复的 | `plans/improvement_opportunities.md` |

**交付物**: 3×6 对比表；失败模式分类；improvement opportunity 说明文档。

---

## Phase 4 — 改进方案原型（2026-05-25 ~ 2026-06-20）

**目标**: 实现并评估 ≥1 个改进基线的系统（H4 Reflexion-style reflection；或其他 Phase 3 发现的机会）。

### 任务

| # | 任务 | 说明 |
|---|------|------|
| 4.1 | 选定改进方向（Reflexion 反思步 / 错误分类器 / 分层输入） | 基于 Phase 3 分析 |
| 4.2 | 实现原型 | `src/improved/` |
| 4.3 | 在全量任务上与 Baseline A/B 对比 | `experiments/improved_vs_baseline/` |
| 4.4 | 统计显著性检验（若样本量允许） | |

**交付物**: 改进方案代码 + 实验结果；对比表。

---

## Phase 5 — 论文写作（2026-06-21 ~ 2026-07-20）

| # | 任务 | 说明 |
|---|------|------|
| 5.1 | Introduction + Motivation | 以 PoC 和 DafnyBench 数字为钩 |
| 5.2 | System Design 节 | 两层架构图、输入格式设计 |
| 5.3 | Experiment 节 | 填入 Phase 2–4 数据 |
| 5.4 | Related Work 节 | 基于 Phase 1 草稿 |
| 5.5 | Abstract + Conclusion | 最后写 |
| 5.6 | 导师 review → 修改 | |

**目标投稿**: TBD（与导师确认目标会议/期刊）

---

## 关键风险

| 风险 | 应对 |
|------|------|
| Move Prover 在新机器/CI 环境不稳定 | 固定 Boogie 3.5.1，脚本内置默认路径 |
| LLM API 费用超预算 | 先用 GPT-4o-mini 探索，再选 GPT-4o 跑最终结果 |
| M1–M3 任务体量过大导致改行失败 | 拆分子任务；允许 pass rate 低但要有分析 |
| 改进方案无显著提升 | Null result 也是贡献；换分析角度（失败模式分类） |

---

## 下一步（立即行动）

1. **Phase 1.1**: 搜索 2025 年关于 Move/Aptos formal verification 的最新工作（关键词: `Move language LLM`, `Aptos smart contract verification`, `formal specification repair`）
2. **Phase 2.1**: 用 `brainstorming-research-ideas` skill 设计 spec-driven prompt 格式
3. 将 `doc/research-state.yaml` 中 `current_direction` 更新为 `PHASE1_RELATED_WORK`
