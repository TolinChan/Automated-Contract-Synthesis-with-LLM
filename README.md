# Automated Contract Synthesis and Repair with LLM

面向 **Aptos Move** 智能合约的自动化合成与修复研究：以 **Move Prover** 与 **`aptos move test`** 为金标准，构建可复现的 Coding Agent / LLM 基线任务集，并配套判分脚本、固定 Prompt、冻结验证器日志与可选 API 调用流程。

## 当前状态（截至仓库快照）

- **任务集**：已在元数据与脚本层面对齐 **T0–T2**（`hello_prover` 证明类 ×2 + `hello_blockchain` 测试类 ×1）以及 **M1–M3**（源自 [move-by-examples](https://github.com/aptos-labs/move-by-examples) 思路的较大体量包：NFT 市场、FA 归属、高级 Todo）。
- **可复现协议**：每个任务目录含 `TASK.md`、`PROMPT.txt`、冻结的 `fail.log`（及/或 `prove.move` 等参考物），便于固定输入、对照不同模型或 Agent。
- **自动化工具**（Python 3，主要使用标准库）：
  - `check_task.py`：对 T0/T1 执行 `aptos move prove`，对 T2 执行 `aptos move test`。
  - `apply_and_check_mbe.py`：对 M1–M3 机械合并模型输出的 Move 代码块后跑测试（**禁止人工改补丁**的 Pass@1 口径）。
  - `invoke_ofox_once.py`：可选，通过 OpenAI 兼容 API（如 OFOX）单轮拉取模型补丁。
  - `agent_verify_loop.py`：同一对话内多轮「写文件 → prove/test → 反馈」，记录 `rounds_to_success`（与 Pass@1 不同，见下）。
- **实验记录**：[`baseline_tasks/RESULTS_LOG.md`](baseline_tasks/RESULTS_LOG.md) 汇总 Pass@1 与多轮指标口径及已跑批次摘要；[`poc_llm_trial.md`](poc_llm_trial.md) 记录早期 hello_prover 注入 PoC。
- **环境说明**：[`ENV_SETUP.md`](ENV_SETUP.md) 记录已验证的 Aptos CLI、Boogie 3.5.1、Z3 与本地 `aptos-framework` 布局（Windows / 本机路径为示例）。

## 指标说明（避免混用）

| 指标 | 含义 |
|------|------|
| **Pass@1** | 模型**仅一轮**输出，经脚本**原样**写入后，**一次** `prove` / `test` 是否成功；不含人工改补丁或第二轮模型输出。 |
| **rounds_to_success** | `agent_verify_loop.py` 在同一会话内多轮修复，**首次**验证通过时的轮次；耗尽 `max_rounds` 则记失败（见各任务 `loop_runs/*/summary.json`）。 |

## 仓库结构（摘要）

| 路径 | 说明 |
|------|------|
| [`baseline_tasks/`](baseline_tasks/README.md) | 任务元数据、脚本、结果模板与部分 `loop_runs` 历史产物 |
| [`baseline_tasks/scripts/`](baseline_tasks/scripts/) | `check_task.py`、`apply_and_check_mbe.py`、`invoke_ofox_once.py`、`agent_verify_loop.py` 等 |
| [`ENV_SETUP.md`](ENV_SETUP.md) | Move Prover 与基线包路径说明 |
| [`move_examples_baseline_规划.md`](move_examples_baseline_规划.md) | 从官方 `move-examples` 选型的规划与实验流程 |
| [`poc_logs/`](poc_logs/) | PoC 阶段 prover 通过/失败日志摘录，供报告引用 |
| 根目录其他 `.md` | 开题/调研/笔记类草稿（随课题迭代） |

## 环境 prerequisites

1. **Aptos CLI**、**Boogie 3.5.1.x**、**Z3**、**.NET 8**（用于 Prover 链路）；T2 / M 系列以 `aptos move test` 为主时要求略低。
2. 本地 **`aptos-framework`**（或完整 `aptos-core`）与各 **Move 包** 需按你的机器布局放置；详细版本与命令见 [`ENV_SETUP.md`](ENV_SETUP.md)。

## 重要：Move 包路径

判分脚本内 **Move 包目录默认为本机 Windows 绝对路径**（例如 `E:\src\move-poc\baseline\...`）。在其他机器或 Linux 上复现时，请修改 [`baseline_tasks/scripts/check_task.py`](baseline_tasks/scripts/check_task.py)、[`apply_and_check_mbe.py`](baseline_tasks/scripts/apply_and_check_mbe.py)、[`loop_tasks.py`](baseline_tasks/scripts/loop_tasks.py) 等与 `PACKAGES` / 包根相关的常量，使其指向你本地的任务副本，并与各任务 `Move.toml` 中的 `aptos-framework` 依赖一致。

## 快速开始

```powershell
# 1. 按 ENV_SETUP.md 配置 BOOGIE_EXE、Z3_EXE（T0/T1 需要）
# 2. 在已放置 Move 包的前提下，于 scripts 目录判分示例：
cd baseline_tasks\scripts
python check_task.py --task-id t0_plus1

# M1–M3（需先准备 model_response.txt 或 API 输出）
python apply_and_check_mbe.py --task mbe_nft_marketplace
```

可选 API：在项目根目录创建 `.env` 并设置 `OFOX_API_KEY`（**勿提交密钥**；`.gitignore` 已忽略 `.env`）。详见 [`baseline_tasks/README.md`](baseline_tasks/README.md)。

## 公开仓库

远程地址：<https://github.com/TolinChan/Automated-Contract-Synthesis-with-LLM.git>

## License

未随仓库声明默认许可证；若公开分发，建议由作者补充 `LICENSE` 文件。
