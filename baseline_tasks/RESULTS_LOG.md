# 基线实验结果记录

> 自动化记录，便于开题/论文引用。后续每次跑批可在文末追加一节，保持**日期 + 模型 + 任务**可追溯。

## 指标口径：Pass@1 与多轮闭环

| 指标 | 含义 |
|------|------|
| **Pass@1** | 模型**仅一轮**输出，经 `apply_and_check_mbe.py` 或等价机械规则写入后，**一次** `aptos move test` / `check_task.py` 是否成功；**不**包含人工改补丁、也**不**包含第二轮模型输出。 |
| **rounds_to_success**（闭环） | 脚本 `agent_verify_loop.py` 在同一对话中反复「写文件 → prove/test → 反馈」，**首次**验证通过时的轮次；若耗尽 `max_rounds` 仍未通过，记失败并见该次 `loop_runs/.../summary.json`。 |

二者不可混用为同一列；论文表格需分列或脚注说明。

## 批次 2026-04-01（OFOX API + 脚本 `invoke_ofox_once.py`）

### 实验设置


| 项    | 内容                                                                                                                                             |
| ---- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| 提供方  | OfoxAI（OpenAI 兼容 `https://api.ofox.ai/v1/chat/completions`）                                                                                    |
| 模型   | `openai/gpt-4o-mini`（脚本内 `DEFAULT_MODEL`，未在 `.env` 写模型名）                                                                                       |
| 密钥   | 项目根目录 `.env` 中 `OFOX_API_KEY`（未写入本文件）                                                                                                          |
| 判分方式 | 将 `model_response.txt` 中代码**原样**合并到对应 `E:\src\move-poc\baseline\...\sources\` 后运行 `python baseline_tasks/scripts/check_task.py --task-id <id>` |


### 逐任务结果


| 任务 ID                   | 现象 / 模型输出要点                                      | 原样应用后 `check_task`                      | Pass@1 |
| ----------------------- | ------------------------------------------------ | --------------------------------------- | ------ |
| **t0_plus1**            | 将 `plus1` 从 `x+2` 改为 `x + 1`，spec 仅空格格式变化，语义不变   | `aptos move prove` → **Success**        | **是**  |
| **t1_aborts**           | 在 `x==0` 分支写 `abort;`（非合法 Move，应为 `abort(0)`）    | **编译失败**（`unexpected token` 于 `abort;`） | **否**  |
| **t2_hello_blockchain** | 将断言期望从 `Hello Blockchain` 改为 `Hello, Blockchain` | `aptos move test` → **2/2 通过**          | **是**  |


### 简要结论（本批次）

- **Prover 后置条件类错误（T0）与单测字符串断言（T2）**：当前模型可**一轮**给出可用补丁。
- `**aborts_if` / `abort` 语法（T1）**：模型给出**非法** `abort;`，原样应用无法进入 prove；需在 Prompt 中明确要求 `**abort(0)`** 等形式，或计为「需第二轮修复语法」。

### 原始模型输出位置

- `baseline_tasks/t0_plus1/model_response.txt`
- `baseline_tasks/t1_aborts/model_response.txt`
- `baseline_tasks/t2_hello_blockchain/model_response.txt`

### 备注

- 验证后已将 **T0 / T1 / T2** 的 Move 包恢复为**任务注入态**（buggy），以便重复实验。
- 若使用 Claude Code 等 **Baseline B**（可自跑 `prove`），请另开小节记录，避免与「仅 API 一轮输出」混淆。

---

## M1–M3（move-by-examples 基线 / 禁止人工修补协议）

与 T0–T2 区分：**拿到 Agent 或 API 输出后，不得在本地手改补丁内容**再通过编译或测试。论文/表格中的 **Pass@1** 仅指：按 `scripts/apply_and_check_mbe.py` 规则**机械写入**后，**一次** `aptos move test` 是否成功；无合法 fenced 块记 **解析失败**，编译/测试非零记对应阶段失败。

### 任务与判分命令

| 任务 | Move 包 | 机械应用目标文件 | 判分 |
|------|---------|------------------|------|
| **mbe_nft_marketplace**（M1） | `E:\src\move-poc\baseline\mbe_nft_marketplace` | `sources/marketplace.move` | `python baseline_tasks/scripts/apply_and_check_mbe.py --task mbe_nft_marketplace` |
| **mbe_fa_vesting**（M2） | `E:\src\move-poc\baseline\mbe_fa_vesting` | `tests/vesting_tests.move` | 同上，`--task mbe_fa_vesting` |
| **mbe_advanced_todo**（M3） | `E:\src\move-poc\baseline\mbe_advanced_todo` | `sources/advanced_todo_list.move` | 同上，`--task mbe_advanced_todo` |

可选：`--response path\to\model_response.txt`；默认使用 `baseline_tasks/<task>/model_response.txt`。

### OFOX 一轮调用（可选）

`python baseline_tasks/scripts/invoke_ofox_once.py --mbe-task mbe_nft_marketplace`（或 M2/M3 任务名）。将 `PROMPT.txt`、`fail.log` 与 E 盘**当前 buggy 源文件**全文发给模型；结果写入对应 `model_response.txt`。随后**不经人工编辑**运行 `apply_and_check_mbe.py`。

### 结果表（跑批后追加行）

| 任务 | Agent/API | 机械应用后 Pass@1 | 失败阶段（解析/编译/测试） | 原始输出路径 |
|------|-----------|-------------------|-----------------------------|--------------|
| mbe_nft_marketplace | OFOX `openai/gpt-4o-mini`（`invoke_ofox_once.py --mbe-task`） | **否** | **编译**（`purchase` 内写成 `coins + 1`，`Coin` 不能与 `integer` 运算） | `baseline_tasks/mbe_nft_marketplace/model_response.txt` |
| mbe_fa_vesting | | | | |
| mbe_advanced_todo | | | | |

#### 批次备注（M1，2026-04-01 后补记）

- 模型未只改断言：在 `deposit_coins` 处错误增加 `coins + 1`，**未到达测试阶段**即失败；符合「机械应用、不手改模型输出」的判分。
- 判分后已将 E 盘 `mbe_nft_marketplace/sources/marketplace.move` **恢复为任务注入态**（`test_fixed_price` 仍为 `10499`，`purchase` 为正确 `deposit_coins(seller, coins)`），便于重复实验。

