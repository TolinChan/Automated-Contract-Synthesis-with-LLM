# Coding Agent 基线任务（T0–T2 + M1–M3）

与 [move_examples_baseline_规划.md](../../plans/move_examples_baseline_规划.md) 及实施计划一致：每个任务在 **E 盘**有独立 Move 包，本目录存放 **冻结 Prompt、失败日志副本、结果模板**。

## 路径

| 任务 ID | Move 包（判分在此执行） | 本目录元数据 |
|---------|-------------------------|--------------|
| **T0** | `E:\src\move-poc\baseline\hello_prover_t0_plus1` | [t0_plus1/](t0_plus1/) |
| **T1** | `E:\src\move-poc\baseline\hello_prover_t1_aborts` | [t1_aborts/](t1_aborts/) |
| **T2** | `E:\src\move-poc\baseline\hello_blockchain_t2` | [t2_hello_blockchain/](t2_hello_blockchain/) |
| **M1** | `E:\src\move-poc\baseline\mbe_nft_marketplace` | [mbe_nft_marketplace/](mbe_nft_marketplace/) |
| **M2** | `E:\src\move-poc\baseline\mbe_fa_vesting` | [mbe_fa_vesting/](mbe_fa_vesting/) |
| **M3** | `E:\src\move-poc\baseline\mbe_advanced_todo` | [mbe_advanced_todo/](mbe_advanced_todo/) |

## 环境

- 设置 `BOOGIE_EXE`、`Z3_EXE`（见 [ENV_SETUP.md](../../doc/ENV_SETUP.md)）。
- 判分（Python 3，仅标准库）：`python scripts/check_task.py --task-id t0_plus1`（或 `t1_aborts` / `t2_hello_blockchain`）。
- **M1–M3（move-by-examples 副本）**：机械应用 + `aptos move test`，**不做**语法自动纠错：  
  `python scripts/apply_and_check_mbe.py --task mbe_nft_marketplace`（或 `mbe_fa_vesting` / `mbe_advanced_todo`；可选 `--response path\to\model_response.txt`）。默认读取对应 `baseline_tasks/<task>/model_response.txt`。

## Baseline 类型

- **Baseline A**：网页 / API 模型，仅根据 `PROMPT.txt` + 代码 + `fail.log` 输出补丁；不执行本机命令。
- **Baseline B**：Claude Code / Cursor Agent，在对应 `E:\...\baseline\...` 目录内可运行 `aptos move prove` 或 `aptos move test`。

## 记录结果

- **已跑批次汇总**：[RESULTS_LOG.md](RESULTS_LOG.md)（含 T0–T2 与 **M1–M3 / 禁止人工修补** 协议说明）。
- 各任务空白模板：T0 [RESULTS_TEMPLATE.md](t0_plus1/RESULTS_TEMPLATE.md)；M1–M3 见各 [mbe_*/RESULTS_TEMPLATE.md](mbe_nft_marketplace/RESULTS_TEMPLATE.md)。也可另建 CSV。

## OFOX API（可选）

脚本 [scripts/invoke_ofox_once.py](scripts/invoke_ofox_once.py)（**勿提交密钥**）：

1. **密钥**：在项目根目录 `.env` 中写一行 `OFOX_API_KEY=你的密钥`（已在 `.gitignore`）；或先在终端 ` $env:OFOX_API_KEY = '...' `（环境变量优先于 `.env`）。
2. **模型**：在脚本顶部改常量 `DEFAULT_MODEL`，或运行时指定 `--model`；**不会**从 `.env` 读模型名。

```powershell
python baseline_tasks\scripts\invoke_ofox_once.py --task-id t0_plus1
python baseline_tasks\scripts\invoke_ofox_once.py --task-id t0_plus1 --model openai/gpt-4o
python baseline_tasks\scripts\invoke_ofox_once.py --mbe-task mbe_nft_marketplace
```

**M1–M3**：`--mbe-task` 从 `baseline_tasks/mbe_*/` 读 `PROMPT.txt`、`fail.log`，从 `E:\src\move-poc\baseline\...` 读**当前（注入后）**目标 `.move` 全文拼入用户消息；超时 300s（体量大）。输出仍写入 `baseline_tasks/mbe_*/model_response.txt`。

批跑建议：`invoke_ofox_once.py --mbe-task <id>` → `apply_and_check_mbe.py --task <id>` → 在 [RESULTS_LOG.md](RESULTS_LOG.md) 登记；**中间不得手改**模型输出。

## 多轮 Spec–Agent–Verifier 闭环（API）

脚本 [scripts/agent_verify_loop.py](scripts/agent_verify_loop.py) 在同一 Chat Completions 会话中多轮调用模型：每轮提取第一个 ` ```move ` 块，**原样**写入 E 盘配置中的目标文件，再运行 **`aptos move prove`**（T0/T1）或 **`aptos move test`**（T2、M1–M3）；失败则将验证器输出（可截断）作为下一条 user 消息，直到通过或达到 `--max-rounds`。

- **任务 ID**：与 `check_task.py` / `apply_and_check_mbe.py` 一致，见 [scripts/loop_tasks.py](scripts/loop_tasks.py)。
- **首轮上下文**：与 `invoke_ofox_once.py` 相同（`PROMPT.txt` + `fail.log` + **E 盘当前**目标源文件全文）。
- **产物**：`baseline_tasks/<task>/loop_runs/<UTC时间戳>/`，含各轮 `round_NN_assistant.txt`、`round_NN_verifier.log`、`messages.jsonl`、`summary.json`（含 `rounds_to_success` 或失败原因）。
- **可选备份**：首次运行前若不存在，会将目标文件复制为同目录 `*.buggy_before_loop.bak`，便于手动恢复注入态。

```powershell
Set-Location baseline_tasks\scripts
python agent_verify_loop.py --task t2_hello_blockchain --max-rounds 5
python agent_verify_loop.py --task mbe_nft_marketplace --max-rounds 8 --timeout-sec 400
```

与 **单轮** `invoke_ofox_once.py` + 机械 `apply_and_check_mbe.py` 的区别：闭环记录的是 **`rounds_to_success`**（或多轮仍失败），**不是**论文中的 **Pass@1**；二者定义见 [RESULTS_LOG.md](RESULTS_LOG.md)。
