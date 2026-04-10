# 开题汇报 PPT 大纲（与计划.md 第五节对齐）

> 每节建议 1–2 页；技术路径与 PoC 可配图。

---

## 第 1 部分：背景与动机（1–2 页）

- 智能合约：效率 vs 可证明正确性
- LLM 写代码的普及与**安全缺口**
- FAST ’26：**规约驱动生成**可行，但 **LLM-as-verifier 不可靠** → 需要 **Move Prover** 类真值后端
- 一句话问题：**能否让 LLM 在「证明器在环」下可靠地合成/修复 Move 合约？**

## 第 2 部分：Verifier-in-the-Loop Agent（2–3 页）

- 架构图：Spec → 生成/编辑 → `aptos move prove` → 反馈解析 →（Translator）→ LLM → 循环
- 与 Clover（Dafny）、SWE-agent（ACI）、Reflexion（言语记忆）的**类比与差异**
- 核心难点：**Prover/Z3 日志 → LLM 可消费信号**（Error Translation）

## 第 3 部分：文献综述要点（2–3 页）

- **SYSSPEC**：规约结构、Intent + Hoare 风格 → 对我们 Prompt/规约模板的启发
- **CodeNet4Repair**：过程反馈；简单报错不够 → 对我们日志处理的动机
- **Clover**：闭环验证；Dafny 反馈 vs **Move Prover** 反馈形态对比
- **Reflexion / SWE-agent**：多轮反思、专用计算机接口 → Agent 设计启发
- 小结：**Move + 资产安全**作为应用场景的**差异化**

## 第 4 部分：初步 PoC（2–3 页）

- **环境**：Aptos CLI + Boogie + Z3（见 `ENV_SETUP.md` 一页截图或表格）
- **hello_prover**：基线 Success + 注入 `plus1` 后 **post-condition 失败**（贴终端或日志片段）
- **defi / locked_coins**：基线 Success；说明**无 spec 则部分逻辑错误不被当前验证覆盖**（工程教训）
- **LLM 试验**：展示 [poc_llm_trial.md](poc_llm_trial.md) 中 Prompt + 结论（简单错误可一次修对）

## 第 5 部分：下一步计划与时间表（1–2 页）

- 构建 **Move Spec–Code** 小数据集
- **LangChain/AutoGen** 集成 prove 子进程
- **Translator +（可选）反思记忆** 实验与评测指标（修复率、轮次、Token）

## 备用问答

- 为何选 Move 而非 Solidity？（资源模型、内置 Prover 生态）
- 与仅单测的区别？（证明覆盖语义而非样例）
- 最大风险？（日志噪声、规约编写成本、框架版本与 Boogie 版本耦合）

---

*可直接将各节标题复制到 PowerPoint / Keynote 作为目录页。*
