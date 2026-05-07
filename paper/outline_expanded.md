# MoVES 论文大纲扩充素材

> 根据 2026-05-07 思路整理，Claude 扩充的引用、事实和逻辑链。
> 导师要求：论文自己写，不要 AI 生成套话。本文件只提供素材，不生成论文段落。

---

## 1. Agent Coding 趋势与问题（Introduction P1）

### 趋势
- 2023-2025 年，LLM coding agent 从概念变为产品：GitHub Copilot (2021) → ChatGPT Code Interpreter (2023) → Devin (2024) → SWE-agent (NeurIPS 2024) → Claude Code / Cursor
- SWE-bench 成为事实标准：从 2023 年的 12% 解决率 (SWE-agent) 提升到 2024 年的 43% (OpenHands)，看似快速进步

### 问题（关键引用）
- **ICSE 2026** (Wang et al.): PatchDiff 技术分析发现 7.8% 的"已解决"问题通过了测试但行为与 ground truth 不同，29.6% 存在行为差异，整体 inflate 6.4 个百分点
- **Behavioral Drivers** (arXiv 2026): 分析 9,374 次 agent 运行，即使最好的 agent 在 >20% 的 SWE-bench Verified 任务上失败；55 个"永远解不出"的任务其实只需要简单 patch
- **SWE-Compass** (arXiv 2025): 提出 6 类 failure mode——需求误解 (RMI)、测试不足 (IAT)、方案不完整 (ISE)、技术知识缺口 (TKG)、工具调用错误 (TIE)、无限循环 (INF)
- **Shepherd** (OpenReview 2025): 18 个模型 3,908 条轨迹的 3 类一致失败模式——回避环境（不测试代码）、行为失序（先编辑后理解）、过早终止

### 核心论点
Agent coding 在通用软件工程上已有不错表现，但**涉及形式化验证的代码生成**是一个不同的挑战——因为 verifier 的反馈是机器级别的（SMT timeout、VC failure、counterexample trace），不像单元测试那样"通过/不通过"二元明确。

---

## 2. 区块链合约安全（Introduction P2）

### 趋势
- DeFi 锁仓价值峰值超 $100B（2021），即使 2025 年也有 $50B+，合约漏洞直接等于资金损失
- Solidity 生态的惨痛教训：The DAO ($60M, 2016)、Poly Network ($611M, 2021)、Nomad ($190M, 2022)
- 传统防御：人工审计 + 自动化工具（Slither、Mythril、Certora），但审计周期长（2-4 周）、成本高（$50K-$200K）、无法覆盖所有路径

### Move 生态的现实
- **MoveScan (ISSTA 2024)**：Song et al. 分析 Aptos + Sui 共 37,302 个合约，发现 97,169 个缺陷，精度 98.85%。**关键发现**：算术溢出占 61.3%；跨模块状态污染在生产环境中（18.5%）远高于开源代码（8.0%），说明部署前审查不足
- **MoveScanner (arXiv 2025)**：Luo et al. 基于控制流图和跨模块调用图分析，发现 12 种新的 Move 特定安全风险类型
- **Move Prover 的现实局限**：MoveScan 显示 Move Prover 只检出了 **6.02%** 的真实缺陷——不是工具不强，而是**需要人工写 spec**，而写 spec 比写代码更难

### 核心论点
即使有 Move Prover 这样的形式化验证工具，实际合约中仍有大量漏洞。核心瓶颈不是验证技术本身，而是**把开发者的意图转化为可被验证器理解的规范**这一过程。

---

## 3. MOVE 语言的形式化验证优势（Background 2.1）

### Move vs Solidity 安全设计（引用 FMBC 2025）

| 特性 | Move | Solidity |
|------|------|----------|
| 资源保留 | 天然（线性类型） | 几乎不可表达 |
| 所有权追踪 | 内置 | 需手动实现 |
| 重入攻击 | 架构层面防止 | 依赖模式，仍可利用 |
| 静态派发 | 编译时验证 | 动态派发导致不可判定性 |
| 字节码验证 | 强制（发布前） | 无 |

**Bartoletti et al. (FMBC 2025)** 的实证结论："Move is better suited for verification than Solidity"——因为 Move 的资源导向设计使得"资源不丢失、所有权正确转移"这些属性在语言语义中天然成立，而 Solidity 中同样的属性"几乎不可验证，甚至不可表达"。

### Move Prover 的局限
- 无法跨交易推理（无全局/归纳不变式）
- 无法验证活性 (liveness)、流动性 (liquidity)
- 需要源码（不能验证已部署字节码）
- 写 spec 的人工成本高
- 可变引用语义不完全可规范

### 核心论点
Move 在语言设计上是"验证友好"的，但验证工具链的使用门槛很高。这正是程序合成可以发挥作用的地方：**如果开发者只需要写 spec，让机器自动生成满足 spec 的代码**，就能同时获得 Move 的安全保证和开发的便利性。

---

## 4. Related Work 定位

### 4.1 传统程序合成
- **SyGuS (Alur et al., FMCAD 2013)**: 语法引导合成，从逻辑规范 + 语法模板生成程序。局限：规范必须是 SMT-LIB 公式，模板需人工设计，不支持资源导向语言
- **Flash Fill (Gulwani, CACM 2012)**: 从输入-输出示例合成字符串处理程序。局限：仅适用于表格数据转换，无形式化保证
- **SmartSpec (我们的前期工作)**: 多模态规范（关系推理规则 + 时序逻辑）+ 演绎 sketch 生成 + CEGIS。在 27 个 Solidity 合约上达到 85% match。局限：(1) 仅支持 Solidity 受限子集；(2) 规范负担重（需写推理规则）；(3) CEGIS 反馈需人工解释

### 4.2 LLM 合约生成
- **MSG (Fu et al., ASE 2025)**: 多 Agent 分阶段生成 Move spec（Ensures → AbortsIf → Modifies → Ensemble）。AIO 模式 70.6%，Agent 模式 94.1%。但这是**反方向**的：给定代码生成 spec，我们做的是给定 spec 生成代码
- **Generating Move Smart Contracts based on Concepts (arXiv 2024)**: 从概念描述生成合约，无开源代码

### 4.3 LLM + 形式化验证
- **PropertyGPT (Liu et al., NDSS 2025)**: RAG 从审计报告生成验证属性，80% recall，发现 26/37 CVE。方向：从代码 + 历史漏洞生成验证属性
- **Clover (Sun et al., SAIV 2024)**: 闭环可验证代码生成，Dafny 语言，非 Move
- **RePair (Zhao et al., ACL 2024 Findings)**: 基于过程反馈的程序修复，通用语言
- **Laurel (arXiv 2024)**: LLM 证明合成，Dafny/F*/Rust，AutoVerus 多 Agent 系统在 150 个 Rust 函数合约上达 ~90%
- **SMARTIFY (arXiv 2025)**: 五 Agent 框架（Auditor/Architect/Generator/Refiner/Validator），支持 Solidity 和 Move，48.9% Pass@1

### 4.4 与 MoVES 的对比（定位表）

| 维度 | MSG | PropertyGPT | Clover | RePair | MoVES (ours) |
|------|-----|-------------|--------|--------|-------------|
| 方向 | Code→Spec | Code→Property | NL→Verified Code | Buggy→Fixed | Spec→Verified Code |
| 目标语言 | Move | Solidity | Dafny | General | Move |
| Verifier 反馈 | ✓ (Prover) | ✗ | ✓ (Dafny) | ✗ (tests) | ✓ (Move Prover) |
| 角色分离 | Multi-agent | Single | Single | Single | Two-role |
| 诊断结构化 | Phase-based | RAG | Error→fix | Process feedback | Taxonomy-based |

---

## 5. Motivating Example 设计

### 段 1 — 真实世界钩子（Thala Labs）

> 2024 年 11 月，Aptos 生态 DeFi 协议 Thala Labs 的 farming contract 遭受攻击，损失 $25.5M。漏洞根源是两天前发布的一个 2 行补丁：开发者认为改动"足够简单"，绕过了常规安全审查。补丁缺少一个关键的状态检查，允许攻击者提取超出其质押额度的代币。虽然资金在 6 小时内被追回（得益于 Move 的内置资产冻结能力），但事件暴露了一个核心问题：**即使是有经验的开发者，在看似简单的代码修改中也会引入关键漏洞**。

**事实来源**：
- Thala 官方 post-mortem (2024-11-15)
- The Block 报道：$25.5M，100% 追回，$300K bounty
- 攻击时间线：11/1 发布补丁 → 11/15 被攻击 → 6 小时内追回

### 段 2 — 技术挑战（stake_update_perf）

> 形式化验证本可以阻止这类错误——如果合约附有完整规范，验证器可以在部署前发现状态不变式被破坏。但问题的另一面是：给定一个完整规范，自动合成满足它的代码同样困难。以 Aptos `stake` 模块的 `update_performance_statistics` 为例，其规范要求更新模块级 ghost 变量、维护 while 循环不变式、并处理 u64 溢出。即使向 LLM 提供完整的签名和规范（zero-shot），生成的代码仍因三个 Move-Prover 特有 idiom 而验证失败：
> - **Idiom 1 — Ghost-variable update.** 规范引用 `global ghost_valid_perf` 和 `global ghost_proposer_idx`；函数体必须用 `spec { update ghost_valid_perf = validator_perf; }` 块初始化，不能用普通 `let` 绑定。
> - **Idiom 2 — While-header invariant placement.** 循环不变式必须放在 while 头部表达式内（`while ({ spec { invariant ... }; cond })`），不能放在循环体中。LLM 放在体中，触发编译级 prover 错误。
> - **Idiom 3 — Overflow assume.** 每个 `u64 += 1` 之前必须有 `spec { assume X + 1 <= MAX_U64; };`，否则 prover 生成无界溢出验证条件并超时。

### 段 3 — 对比实验结果

> 我们测试了三种修复策略：generic feedback（失败，2 轮后仍 timeout）、structured manual diagnosis（1 轮通过，76.95s）、auto-diagnose with idiom checklist（仍失败）。结果说明：codegen 能力足够，瓶颈在 diagnose。

---

## 6. 设计动机（Discussion / Design 部分）

### 为什么 Spec + 代码描述？
- SmartSpec 的教训：从自然语言/示例合成 requirement 是瓶颈（85% match 后还需 4 轮人工反馈）
- 缩小问题范围：假设 spec 已完整给出，只解决 **spec → code** 这一步。这让问题更可解、结果更可验证

### 为什么 Feedback 循环？
- ICSE 2026 证明单次生成不可靠（29.6% 行为差异）
- Verifier 作为真值源可以捕捉语义违规（代码满足 spec 吗？），而非仅语法正确性

### 为什么 Two-Role 分离？
- Single agent 同时生成和诊断会"为自己的错误辩护"
- feas_run_03 证明：即使加入 idiom checklist，auto-diagnose 仍失败，因为 per-round diagnosis 缺乏全局上下文
- Manual diagnosis（一次性列出所有 3 个 idiom）1 轮就过

### 换更好的模型会不会改善？（明天验证一下最好，ai说的不一定对）
- **不会。** 这不是生成能力问题（manual diag 产生 reference-quality 代码）。这是**信息路由问题**：diagnoser 必须知道哪些 Move-Prover idiom 需要 prescription。
- 更好的模型（GPT-5、Claude 4 等）可能在通用代码上更强，但 Move-Prover 的 ghost var、while-header invariant、overflow assume 是**训练数据中极少出现**的 idiom，属于 domain knowledge 缺口

### 代码和 spec 冲突——最有价值的 failure mode
- 模型可能生成语法正确但语义不满足 spec 的代码（如遗漏 aborts_if 条件）
- 这种错误肉眼难以发现，但 verifier 可以捕捉
- 说明 verifier-in-the-loop 不是"锦上添花"，而是**必要组件**

---

## 7. 待补充引用（BibTeX 待查）

| 引用 | 来源 | 用途 |
|------|------|------|
| Alur et al. 2013 | SyGuS, FMCAD 2013 | 传统合成器 |
| Gulwani 2011 | Flash Fill, CACM 2012 | PBE 合成 |
| SmartSpec | 我们的前期工作 | 定位 |
| SWE-Compass | arXiv 2025 | Agent failure modes |
| Wang et al. ICSE 2026 | PatchDiff | SWE-bench inflate |
| Behavioral Drivers | arXiv 2026 | Agent 失败率 |
| Bartoletti et al. | FMBC 2025 | Move vs Solidity |
| Song et al. | ISSTA 2024 | MoveScan |
| Thala post-mortem | Medium 2024 | 真实案例 |
| Cetus analysis | Dedaub/BlockSec 2025 | 备选案例 |
