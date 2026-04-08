# 从 aptos-core `move-examples` 选型 + 基线实验操作规划

官方目录：[aptos-move/move-examples](https://github.com/aptos-labs/aptos-core/tree/main/aptos-move/move-examples)（需克隆 `aptos-core` 或按 [ENV_SETUP.md](ENV_SETUP.md) 用本地包 + `aptos-framework`）。

---

## 一、示例怎么选（按实验目的分层）

### 1. 优先用于 **Move Prover + LLM/Coding Agent 修复** 基线

| 包名 | 规模 | 说明 |
|------|------|------|
| **`hello_prover`** | 极小 | 含显式 `spec {}`（`plus1`、`abortsIf0`），`aptos move prove` 语义清晰，**最适合**做 Pass@1 / Pass@k、与「日志翻译」对照。 |
| **`vector_pushback`** | 极小 | 单文件、逻辑简单；**默认无 spec**，适合只做 `compile`/`test` 的 agent 基线，或**你方自行加少量 spec** 后再做 prove 实验。 |
| **`split_transfer`** | 小 | 为 **script** 形态，依赖框架 coin API；更适合跑通 CLI/编译，**Prover 需单独评估**（脚本与模块验证策略不同），建议优先级低于 `hello_prover`。 |

### 2. 用于 **业务叙事 / 规模压力**，Prover 需额外设计

| 包名 | 说明 |
|------|------|
| **`defi`**（`locked_coins`） | 与课题「合约 + 资产」贴合；官方文件体量大，**当前验证义务未必覆盖你关心的实现细节**（见 [poc_logs/defi_locked_coins_injection_note.txt](poc_logs/defi_locked_coins_injection_note.txt)）。适合作为 **「真实模块 + 工具链冒烟」**；若要做 **「注入必失败 → agent 修」**，需**自写/补充 spec** 指向关键不变式。 |

### 3. 适合 **通用 Coding Agent**（改代码、跑终端），但不以 Prover 为主

| 包名 | 说明 |
|------|------|
| **`hello_blockchain`** | 教程标配，`compile` / `move test` 文档多，适合测 agent **能否按文档跑通测试**（与「证明闭环」是不同维度）。 |
| **`moon_coin` / `message_board` / `tic-tac-toe`** | 中等复杂度，可测 **多文件导航、依赖理解**；选 1 个即可，避免任务集爆炸。 |

### 4. 基线阶段建议 **暂缓**

- **`drand`、`groth16_example`**：密码学重，调试成本高，易掩盖「验证反馈」问题。  
- **`cli-e2e-tests`、`large_packages`**：偏集成/体量，不适合作为第一篇基线论文式任务。  
- 更多新示例可关注官方维护的 **[move-by-examples](https://github.com/aptos-labs/move-by-examples)**（与 `move-examples` 互补）。

---

## 二、推荐的最小任务集（Coding Agent / Claude Code baseline）

在控制变量前提下，建议 **3 档难度、共 4 个任务点**（可删减）：

1. **T0**：`hello_prover` — 注入破坏 `plus1` 与 spec 一致性的实现，给 **完整 prover 日志**，量 **Pass@k** 与 **是否误改 spec**。  
2. **T1**：`hello_prover` — 第二处：`abortsIf0` 相关（改条件使 `aborts_if` 失败），观察 agent 对 **aborts** 类报错的理解。  
3. **T2**：`hello_blockchain` — 人为制造 **编译或单元测试失败**（非 prover），测 **SWE-agent 式**「跑测试—看报错—改代码」与 T0/T1 的对比。  
4. **T3（可选）**：`defi/locked_coins` — **仅当**你为关键函数补充 spec 后，再注入；否则只做「clone + prove 通过」的**工具链演示**，不计入修复率统计。

---

## 三、操作流程（可复现实验协议）

### 阶段 A：仓库与版本固定

1. 克隆 `aptos-core`（或沿用 [ENV_SETUP.md](ENV_SETUP.md) 的 `E:\src\aptos-framework` + 拷贝出的单包）。  
2. **记录**：`aptos --version`、Boogie/Z3 路径、`aptos-framework` 的 commit 或 `rev`。  
3. 每个任务在 **独立 git 分支** 或 **独立子目录副本**（如 `baseline_tasks/hello_prover_task1/`），避免 agent 改乱原树。

### 阶段 B：为每个任务准备「三件套」

1. **错误实现**（`buggy` 标签或分支）：仅改实现，**默认不改 spec**（除非实验「spec 修复」子问题）。  
2. **冻结的 prover 输出**（`fail.log`）：同一环境下生成一次，所有 baseline **共用同一份日志**，排除「日志随机性」。  
3. **评分脚本/检查单**：在该包目录执行 `aptos move prove`（及按需 `aptos move test`），**以退出码与 `Result: Success` 为金标准**。

### 阶段 C：对照 Baseline

| Baseline | 输入 | 操作约束 |
|----------|------|----------|
| **网页 LLM** | 代码 + `fail.log` + 固定 Prompt | 不允许执行终端；只看**单轮/少轮**文本补丁。 |
| **Claude Code / Cursor Agent** | 同上 + 打开任务子目录 | **允许**运行 `aptos move prove`，记录**轮数**与**是否自发调用 prove**。 |

记录字段建议：`模型/产品名`、`任务 ID`、`Pass@1`、`Pass@3`、`轮次`、`是否修改 spec`、`总 token（若可得）`。

### 阶段 D：写进开题/论文的表述

- **通用 Coding Agent** 在 **T0/T1（Prover 反馈）** 与 **T2（测试反馈）** 上的差距。  
- 若 **无翻译/无 ACI** 时 T0 明显更难，支撑导师建议的 **「参考 coding agent 做法 + 你们做 Translator/接口」** 路线。

---

## 四、与你当前仓库的衔接

- 已有：`hello_prover` 路径与日志雏形（见 [poc_logs/](poc_logs/)、[poc_llm_trial.md](poc_llm_trial.md)）。  
- 下一步：从 GitHub **同步官方 `hello_prover` 与 `hello_blockchain` 的完整包** 到 `E:\src\move-poc\` 或课题下的 `baseline_tasks/`，与 upstream **同 Move.toml 策略**（本地 `aptos-framework` 或 pin `rev`），再按上表批量生成 `fail.log`。

---

## 五、一键路径索引（GitHub）

- [hello_prover](https://github.com/aptos-labs/aptos-core/tree/main/aptos-move/move-examples/hello_prover)  
- [hello_blockchain](https://github.com/aptos-labs/aptos-core/tree/main/aptos-move/move-examples/hello_blockchain)  
- [defi](https://github.com/aptos-labs/aptos-core/tree/main/aptos-move/move-examples/defi)  
- [vector_pushback](https://github.com/aptos-labs/aptos-core/tree/main/aptos-move/move-examples/vector_pushback)  
- [move-examples 根 README](https://github.com/aptos-labs/aptos-core/blob/main/aptos-move/move-examples/README.md)

---

*本文档随实验迭代可增删任务行，不必改动 [计划.md](计划.md)。*
