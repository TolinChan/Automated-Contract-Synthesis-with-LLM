# Baseline Tasks

本目录保存早期 baseline 与 feasibility 阶段的历史材料。当前正式 Phase 1 实验入口在 `../../experiments/phase1/`；这里的脚本和结果仅作为历史证据或可复用基础设施保留。

## 当前结构

| 路径 | 说明 |
|------|------|
| [`feasibility/`](feasibility/) | 早期可行性实验框架。含合成循环脚本、诊断模块、验证流水线，以及对应 Zero-shot/+Ctx/+Diag/Oracle-Diag 的历史实验结果 |
| [`scripts/`](scripts/) | 通用判分脚本（`check_task.py`、`agent_verify_loop.py` 等），仍被 feasibility 框架复用 |
| [`RESULTS_LOG.md`](RESULTS_LOG.md) | 历史实验记录（T0–T2 / M1–M3 旧批次） |

## 快速开始

详见项目根目录 [`README.md`](../../README.md) 与 [`../../experiments/phase1/`](../../experiments/phase1/)。
