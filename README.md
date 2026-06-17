# MoVES: Move Verified Execution Synthesis

**Spec-driven smart-contract synthesis for Aptos Move with verifier-in-the-loop feedback.**

MoVES 是一个面向 Aptos Move 的自动化合成系统，核心任务是 **Spec→Code**：给定函数的 `requires` / `ensures` / `aborts_if` / `modifies` 形式化规约，让 LLM 自动生成通过 Move Prover 验证的函数体。

与现有工作（如 MSG 的 Code→Spec 方向）相反，MoVES  tackle 的是更困难的逆向问题，并通过**双角色架构**（独立的 Code Generation Role + Error Diagnosis Role）解决单模型在形式化验证反馈中的自我辩护偏差（self-justification bias）。

## 核心发现（Feasibility Test）

在 5 个 aptos-framework 函数上的可行性验证：

| Paper condition | 设置 | stake_update_perf 结果 | 整体通过率 |
|---|---|---|---|
| Zero-shot (`b1`) | 签名 + Spec | **FAIL** | 4/5 (80%) |
| +Ctx (`b3`) | 签名 + Spec + 模块上下文 | **FAIL** | 4/5 (80%) |
| +Diag-1 (`b6`) | 1 轮 generic feedback | **FAIL** | 4/5 |
| +Diag-3 (`b7`) | 3 轮 generic feedback | **FAIL** | 4/5 |
| Oracle-Diag | 手写结构化诊断 + 1 轮反馈 | **PASS (76.95 s)** | 5/5 |

关键结论：**codegen 能力足够，瓶颈在 diagnose**。零轮合成通过 80%，但失败的 `stake_update_perf`（含 ghost vars、while-loop invariants、overflow assumes 三个验证习语）无法被 generic feedback 修复；一旦提供手写结构化诊断，同一模型 1 轮即通过。

多模型对比（同一函数）：
- **Kimi**：zero-shot 及 generic feedback 均失败
- **Claude Opus 4.7**：在 MoVES 双角色框架下，1 轮结构化诊断通过（72.7 s）
- **GPT 5.5**：zero-shot 看似通过，但人工检查发现其**完全省略了 `failed_proposer_indices` 逻辑**，暴露 Pass@1 指标的系统性缺陷

## 仓库结构

> Current formal Phase 1 runs should use `experiments/phase1/`.
> `src/baseline_tasks/feasibility/` is kept as historical feasibility
> infrastructure and evidence, not as the main entry point for new runs.

```
.
├── paper/                          # ASE 格式论文（IEEEtran）
│   ├── overleaf/                   # LaTeX 源文件
│   │   ├── main.tex                # 主文件（引用 7 个章节）
│   │   ├── references.bib          # BibTeX 数据库
│   │   └── sections/               # 各章节 .tex 文件
│   └── 论文草稿素材/                # 旧草稿归档
│
├── src/baseline_tasks/
│   ├── feasibility/                # 可行性实验框架
│   │   ├── registry.json           # 5 个测试函数注册表
│   │   ├── scripts/                # 合成与验证脚本
│   │   │   ├── synth_loop.py       # 反馈循环主控
│   │   │   ├── diagnose.py         # 诊断角色 prompt
│   │   │   └── verify_synth.py     # 调用 aptos move prove
│   │   ├── results/                # 实验结果（按 run 编号）
│   │   │   ├── feas_run_02/        # Phase A/B 完整结果
│   │   │   └── model_cmp_20250508/ # 多模型对比（Claude/GPT）
│   │   └── AGENT_LOOP_DESIGN.md    # 双角色架构设计文档
│   │
│   └── scripts/                    # 通用判分脚本
│       ├── check_task.py           # T0–T2 验证
│       ├── apply_and_check_mbe.py  # M1–M3 测试
│       ├── agent_verify_loop.py    # 多轮 rounds_to_success
│       └── loop_tasks.py           # 任务注册表
│
├── doc/
│   ├── ENV_SETUP.md                # Move Prover 环境配置
│   ├── workflow.md                 # 文字版系统流程
│   └── 思维导图.png                 # 系统架构图
│
├── plans/                          # 项目规划与时间线
├── experiments/poc_logs/           # PoC 阶段日志
└── CLAUDE.md                       # 本项目给 Claude Code 的指令
```

## 环境配置

运行 Move Prover（T0/T1 及 feasibility test 必需）：

```powershell
$env:BOOGIE_EXE = "C:\Users\96247\.dotnet\tools\boogie.exe"
$env:Z3_EXE     = "E:\tools\z3_extract\z3-4.13.0-x64-win\bin\z3.exe"
```

版本锁：
- Aptos CLI **9.1.0**
- Boogie **3.5.1.x**（更高版本会被 Aptos CLI 拒绝）
- Z3 **4.13.0**
- .NET SDK **8.x**

完整环境说明见 [`doc/ENV_SETUP.md`](doc/ENV_SETUP.md)。

## 快速开始

### 跑单个可行性验证

```powershell
cd experiments\phase1\scripts
# Zero-shot (internal artifact tag: b1)
python synth_b1.py --provider deepseek --model deepseek-v4-pro --id stake_update_perf

# +Ctx (internal artifact tag: b3)
python synth_b3.py --provider deepseek --model deepseek-v4-pro --id stake_update_perf

# +Diag-1 (internal artifact tag: b6)
python synth_loop.py --provider deepseek --model deepseek-v4-pro --feedback-rounds 1 --id stake_update_perf

# 结果写入 results/<run_id>/<baseline>/<function>/
```

### 跑通用任务验证

```powershell
cd src\baseline_tasks\scripts
# T0/T1: Move Prover
python check_task.py --task-id t0_plus1

# T2: aptos move test
python check_task.py --task-id t2_hello_blockchain

# M1–M3: 提取模型输出并跑测试
python apply_and_check_mbe.py --task mbe_nft_marketplace
```

### 多轮反馈循环

```powershell
python agent_verify_loop.py --task t2_hello_blockchain --max-rounds 5
```

## 指标说明

| 指标 | 含义 | 脚本 |
|---|---|---|
| **Pass@1** | 模型仅一轮输出，脚本原样写入后一次验证即通过；不含人工修改或第二轮输出 | `invoke_ofox_once.py` + `apply_and_check_mbe.py` |
| **rounds_to_success** | 同一会话内多轮反馈修复，首次验证通过的轮次；耗尽 `max_rounds` 记失败 | `agent_verify_loop.py` |

**两者不可混用**。详见 `src/baseline_tasks/RESULTS_LOG.md`。

## 论文

当前 ASE 格式论文（IEEEtran，双盲审）位于 [`paper/overleaf/`](paper/overleaf/)，结构：

- Intro：已完成，含 Motivating Example 与多模型对比
- Background / Related Work / Design / Evaluation / Discussion / Conclusion：骨架已搭建，待填充

## 关联仓库

- 个人仓库（本仓库）：https://github.com/TolinChan/Automated-Contract-Synthesis-with-LLM
- Lab 仓库：https://github.com/declarative-systems-lab/smart-contracts-synthesis
