# Baseline Tasks

本目录已迁移至以 `feasibility/` 为核心的实验框架。旧 T0–T2 / M1–M3 基线任务已归档清理。

## 当前结构

| 路径 | 说明 |
|------|------|
| [`feasibility/`](feasibility/) | **核心实验框架**。含合成循环脚本、诊断模块、验证流水线、以及 B1/B3/B6/B7/Manual-diag 实验结果 |
| [`scripts/`](scripts/) | 通用判分脚本（`check_task.py`、`agent_verify_loop.py` 等），仍被 feasibility 框架复用 |
| [`RESULTS_LOG.md`](RESULTS_LOG.md) | 历史实验记录（T0–T2 / M1–M3 旧批次） |

## 快速开始

详见项目根目录 [`README.md`](../../README.md) 与 [`feasibility/`](feasibility/) 子目录。
