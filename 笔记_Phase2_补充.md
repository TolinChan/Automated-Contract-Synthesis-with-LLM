# Phase 2 补充阅读短笔记：Reflexion、SWE-agent（与 AutoCoder 类工作）

> 目的：支撑「Agent + 工具/环境反馈」叙事，与课题中 **调用 `aptos move prove`、解析验证器日志、多轮修复** 对齐。依据公开论文与官方仓库说明整理，非全文精读笔记。

---

## 1. Reflexion（语言智能体的言语强化学习）

| 项目 | 内容 |
|------|------|
| **文献** | Shinn 等，*Reflexion: Language Agents with Verbal Reinforcement Learning*，NeurIPS 2023；arXiv: [2303.11366](https://arxiv.org/abs/2303.11366) |
| **核心** | 不更新模型权重，而用**自然语言形式的反思（reflection）**把环境反馈转成可复用的**情节记忆**；下一轮决策前可读入这些反思，相当于**语义上的梯度信号**。 |
| **反馈形态** | 可接标量/二元成功失败，也可接自由文本；来源可以是外部环境或内部模拟。 |
| **与课题的关系** | Move Prover 失败后，除原始日志外，可显式生成「**本轮失败原因摘要 + 下轮应避免/应尝试**」的反思文本，与 CodeNet4Repair 的**过程反馈**、Clover 的**验证器反馈**形成互补：**Reflexion 强调「把反馈写成可累积的语言记忆」**，便于多轮 `prove → 修复 → prove`。 |
| **可写进报告的句** | 「闭环修复不仅依赖单次报错，还可借鉴 Reflexion 将验证失败**言语化**并写入记忆，降低重复犯错的概率。」 |

---

## 2. SWE-agent（面向软件工程的 Agent–计算机接口）

| 项目 | 内容 |
|------|------|
| **文献** | Yang 等，*SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering*，NeurIPS 2024；arXiv: [2405.15793](https://arxiv.org/abs/2405.15793)；代码：[princeton-nlp/SWE-agent](https://github.com/princeton-nlp/SWE-agent) |
| **核心** | 提出 **Agent-Computer Interface (ACI)**：在「裸 Shell」与 LM 之间加一层**面向软件工程的原语**（浏览文件、搜索仓库、带护栏的编辑等），并把命令执行结果以**简洁、可消费**的形式回传给模型。 |
| **与课题的关系** | 你们的 Agent 需要稳定调用 **`aptos move prove`** 并处理长日志，可直接类比 ACI 思想：**把 prove 封装成单一工具调用**、对 stdout/stderr **截断/结构化/高亮关键反例**，减少模型被噪声淹没——这与 [计划.md](计划.md) 中的 **Error Translation / 日志清洗** 同向。 |
| **可写进报告的句** | 「SWE-agent 表明 LM 更需要**专门设计的计算机接口**而非原始终端流；Move Prover 输出同样需要 **Translator 层** 才能稳定驱动多轮修复。」 |

---

## 3. AutoCoder 类工作（简述）

| 项目 | 内容 |
|------|------|
| **定位** | 业界有多条「LLM + 自动写代码 + 运行/测试」管线（名称常含 AutoCoder、code agent 等），共同点是大模型**生成补丁 → 执行编译或测试 → 将结果再喂回模型**。 |
| **与课题的关系** | 与 SWE-agent 类似，强调**工具闭环**；差异是你们的安全关键路径是 **定理证明器/ SMT 反例** 而非仅单元测试通过，**反馈更难读**，故「翻译层」权重更高。 |
| **使用建议** | 报告「相关工作」中可与 SWE-agent 合并一句带过，避免堆砌产品名；若需正式引用，优先选**有 arXiv/顶会论文**的一条并单独精读摘要。 |

---

## 4. 三篇合并对照表（便于 PPT）

| 工作 | 反馈从哪来 | 给模型的形式 | 对 Move 闭环的启发 |
|------|------------|--------------|-------------------|
| Reflexion | 环境/任务结果 | **自然语言反思 + 记忆** | prover 失败后生成结构化反思，减少重复错误 |
| SWE-agent | 命令与工具 | **ACI 包装后的短反馈** | 封装 `prove`、压缩/解析日志 |
| 本课题 | Move Prover / Z3 | （目标）**Spec + 清洗后的反例说明** | 绝对真值 + 需翻译的冗长日志 |

---

*文档版本：与《课题完整执行计划》A2 节一致；复杂图表与公式以原论文为准。*
