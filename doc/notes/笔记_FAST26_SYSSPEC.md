# 文献笔记：FAST ’26 — Sharpen the Spec, Cut the Code（SYSSPEC / SPECFS）

## 元信息

- **标题**：*Sharpen the Spec, Cut the Code: A Case for Generative File System with SYSSPEC*
- **作者**：Qingyuan Liu 等，上海交通大学
- **会议**：USENIX FAST 2026
- **资源**：https://llmnativeos.github.io/specfs/；Artifact：https://github.com/LLMNativeOS/specfs-ae

## 一句话问题

如何用 LLM **生成并演化**完整文件系统，同时避免纯自然语言提示的歧义与不可靠性？

## 核心贡献

1. **生成式文件系统范式**：用「规约驱动 + LLM 工具链」替代在低层 C 代码上手工堆维护。
2. **SYSSPEC 多部件规约**：在**非完全形式化**前提下，借用形式化方法的结构（Hoare 式合同、Rely–Guarantee、显式并发规约），作为 LLM 的**无歧义蓝图**。
3. **DAG 结构 spec patch**：在规约层描述功能演进与依赖，工具链自叶向根再生成实现，避免手工改数千行 C。
4. **原型 SPECFS**：基于 AtomFS 设计、FUSE 用户态；xfstests 等验证；展示 10 个类 Ext4 特性通过 spec patch 集成；延迟分配等带来可测性能收益。

## 动机与背景数据

- **Ext4 纵向研究**（Linux 2.6.19–6.15，3157 commits）：约 **82.4%** 为 bug/maintenance；**5.1%** feature commit 却占约 **18.4%** LOC 变更；**fast commit** 案例：约 9 个 feature commit 对应后续约 80 个维护类 commit。
- **结论导向**：演化以小步、单文件修改为常态，适合自动化辅助，但前提是**意图表达足够精确**。

## SYSSPEC 规约结构（与 Move spec 的类比思路）

### 1. 功能规约（§4.1）

- **前置 / 后置条件**（Hoare 风格）、**不变式**、可选 **系统算法**（说明「怎么做」以防仅满足功能但性能极差，如冒泡 vs 快排）。
- **Intent**：自然语言高层意图，作为轻量算法提示，补合同所不能覆盖的工程/领域提示（如 bulk I/O）。
- **三级细节**：Level 1 多只需 pre/post + 不变式；Level 2 加 intent；Level 3 需显式算法（如 rename + 细粒度锁）。
- **与经典形式化的区别**：用**结构化自然语言 + 类型/数学化表述**写合同，由 **LLM 在生成时遵守**，而非定理证明器全程证明。

### 2. 模块化规约（§4.2）

- **上下文有界**：案例中单模块约 ≤500 LoC，推理约 ~30K tokens 量级（随模型能力可调）。
- **Rely / Guarantee**：模块对环境的假设与对外保证；依赖模块的 Guarantee 应能推出本模块的 Rely，以支持**分模块生成与组合**。

### 3. 并发规约（§4.3）

- **关键设计**：将锁协议等从功能规约中**拆出**为独立「并发规约」；工具链 **两阶段**：先验证**顺序**实现，再按并发规约**插桩**锁与并发行为，降低单 prompt 混合功能+锁时 LLM 失败率。

### 4. DAG spec patch（§4.4）

- **叶节点**：自包含、局部变更，可引入新结构供上层 rely。
- **中间节点**：基于子节点新 guarantee 叠更高层逻辑。
- **根节点**：对外语义与旧实现等价，作为原子「提交点」；可多根（DAG）。
- **共享结构变更**（如 inode）：依赖方模块需纳入 patch 并**再生**。

## 工具链三智能体（§4.5）

| 组件 | 职责 |
|------|------|
| **SpecCompiler** | 规约 → 可编译 C；**两阶段**（顺序 → 并发）；每阶段内 **retry-with-feedback**。 |
| **SpecEval**（内嵌于 Compiler 流程） | 与 CodeGen **分离**的审查角色：对照规约找错，产出**可执行反馈**（如某失败路径未处理），写回 prompt 再生成。 |
| **SpecValidator** | 整机 ImpFS：**复用 SpecEval 式审查** + **单元/回归测试**（类 CI）。 |
| **SpecAssistant** | 人给草稿规约 → 格式化；循环调用 SpecCompiler；失败则用 **SpecFine** 据反馈打磨规约再试；成功交付规约+实现，失败返回带诊断的规约。 |

**论文论点**：「验证比生成容易」+ 两模型**互补共错**概率低——但本质上 **SpecEval 仍是 LLM**，不是机器证明。

## 实验要点（§6，摘要）

- **准确率**：SPECFS 相对 Normal / Oracle few-shot，在 Gemini-2.5-Pro、DeepSeek-V3.1 等上生成 AtomFS 模块准确率显著更高（强模型上可达 100% 模块覆盖等，见图 11）。
- **消融（表 3）**：仅功能规约不足以处理接口不匹配；+模块化后并发无关模块可达标；**线程安全模块**需 **+并发规约 + SpecValidator**。
- **生产力（表 4）**：Extent / Rename 两类 patch，规约驱动相对人工报告约 **3.0× / 5.4×**。
- **性能（§6.5）**：Inline data、预分配、extent、delayed allocation 等有微基准与业务场景（如 xv6 编译）上的 metadata/data I/O 比例变化；delayed allocation 场景数据写可极大下降（文中有 99.9% 量级案例）。
- **局限（§6.6）**：当前 SPECFS 为 FUSE 用户态，无完整内核栈与 **crash consistency** 评估；未来谈工业 FS、SpecAssistant 从文档/bootstrap 规约、以及与 **push-button verification** 结合。

## 与你课题（Move + Move Prover + Agent）的对接

- **可借鉴**：**规约 = Prompt 结构**（pre/post、不变式、模块化依赖、分阶段「先逻辑后资源/并发」）；**失败反馈闭环**（retry-with-feedback）。
- **可写进调研的批评点**：**SpecEval 是 LLM 审查**，存在幻觉与标准漂移；**Move Prover** 可作为「硬裁决」，与文中「未来接形式验证」的讨论（§6.6）一致。
- **相关工作表（Tab. 1）**：将 **Clover** 标为「精确但非模块化并发 FS」类 prior，便于你在综述里**定位 SYSSPEC 与 Clover 的差异**。

## 引用时可用的概括句

- SYSSPEC 将开发者负担从**写 C** 转为**写结构化规约**，用形式化方法的**纪律**而非全程**证明义务**来约束 LLM。
- **两阶段生成 + SpecEval 反馈**是其实现复杂 FS 并发正确的关键工程机制。

---

*笔记基于 PDF 文本抽取 `fast26-liu-qingyuan_extract.txt`，图表与公式以原文为准。*
