# LLM 修复试验记录（hello_prover 注入场景）

> **系统化基线**：Coding Agent / 多模型对照请使用 [baseline_tasks/](baseline_tasks/README.md)（T0/T1/T2、冻结 `fail.log`、`PROMPT.txt`、可选 [scripts/invoke_ofox_once.py](baseline_tasks/scripts/invoke_ofox_once.py)）。

## 1. 背景

- **包路径**：`E:\src\move-poc\hello_prover`（早期 PoC）；与 T0 等价的正式任务包为 `E:\src\move-poc\baseline\hello_prover_t0_plus1`
- **注入**：将 `plus1` 实现由 `x+1` 改为 `x+2`，`spec plus1` 仍为 `ensures result == x+1;`
- **Prover 输出摘要**：`post-condition does not hold`，指向 `ensures result == x+1;`（完整日志见 [poc_logs/hello_prover_injected_plus2_fail.txt](poc_logs/hello_prover_injected_plus2_fail.txt)）

## 2. 固定 Prompt 模板（可复制到 ChatGPT / Claude）

```
你是一名 Move 与 Move Prover 专家。下面是一段 Move 代码（模块 0x42::prove）以及 Move Prover 的报错。请：
1) 用一两句话说明失败原因；
2) 给出修正后的完整 `module 0x42::prove { ... }`（只改必要行，保留 spec）。

【代码】
<<<粘贴 sources/prove.move 注入后的全文>>>

【Prover 报错】
<<<粘贴 hello_prover_injected_plus2_fail.txt 中与 error/post-condition 相关的段落>>>
```

## 3. 试验记录（Cursor 助手代跑一轮，供报告引用）

| 项目 | 内容 |
|------|------|
| 模型角色 | 本对话中的编码助手（等价于一次「闭卷」修复尝试） |
| 是否一次改对 | **是**（将 `x+2` 恢复为 `x+1` 即可满足 `ensures result == x+1`） |
| 对日志敏感片段 | `post-condition does not hold` + 指向的 `ensures` 行号对定位最直接；Boogie/Z3 底层细节对本题几乎冗余 |
| 观察 | 简单算术与后置条件不一致时，**高层错误信息已足够**；若未来只有 Z3 反例而无行级映射，则更依赖 [计划.md](计划.md) 中的 **Error Translation** |

## 4. 与课题叙事的关系

- 本例支持：**规范、易读的 prover 摘要** 能降低 LLM 修复门槛。
- 仍需强调：更复杂模块（如长反例、不变式跨函数）可能出现「日志长、难对齐到代码」——与 CodeNet4Repair / Clover / SWE-agent 讨论一致，并为 **Translator + ACI** 留出研究空间。

## 5. 建议你在网页模型上补做的 1～2 轮

用第 2 节同一 Prompt 换 **GPT-4o / Claude** 各跑一次，在下方表格手写结果，用于开题材料「多模型对比」。

| 模型 | 一次改对？ | 备注 |
|------|------------|------|
| （待填） |  |  |
| （待填） |  |  |
