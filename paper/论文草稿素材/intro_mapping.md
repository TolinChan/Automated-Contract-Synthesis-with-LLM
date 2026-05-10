# Intro 中英段落对照映射

> 以 `introduction_zh_v2.md`（中文 v2）为目标结构，`intro.md` / `draft.md` 的英文旧版为素材库。
> 标注每段：【可复用】= 英文旧版有接近内容，改改就能用；【需重写】= 英文旧版没有，需要基于中文翻译。

---

## P1：从 SWE-bench 趋势到合约安全严重性

**中文 v2 内容**：
- SWE-bench 解决率 12% → 43%
- PatchDiff：29.6% 行为差异，7.8% 通过测试但行为不对
- 区块链场景后果更严重：DeFi $50B+，The DAO ($60M)、Poly Network ($611M)
- 现有防线：审计周期长、工具无法覆盖所有路径

**英文旧版对应**：
- **没有这段**。英文版直接从"Smart contracts manage high-value digital assets"开始，没有 SWE-bench 铺垫。

**操作建议**：【需重写】
- 中文 v2 的这段结构很好，建议保留。
- 英文素材：可以复用 `outline_expanded.md` Section 1 的 SWE-bench 数据和引用。
- 关键引用：
  - SWE-agent (NeurIPS 2024) → SWE-bench 提升
  - Wang et al., ICSE 2026 (PatchDiff) → 29.6% / 7.8%
  - The DAO、Poly Network → 历史损失

---

## P2：传统合成局限 → SmartSpec → Move 优势 → MSG 区分

**中文 v2 内容**：
- 语法引导合成（Synquid/Leon）不支持资源导向语言
- PBE 合成（Flash Fill）无形式化保证
- SmartSpec：85% match，但受限于 Solidity 子集，CEGIS 需人工反馈
- Move 优势：线性类型、静态派发、字节码验证
- MoveScan：37,302 合约，97,169 缺陷，Move Prover 只检出 6.02%
- **MSG 区分**：Code→Spec vs Spec→Code（关键新增）

**英文旧版对应**：
- 英文版 Para 2 有"traditional synthesizers face a fundamental tension..."
- 提到了 deductive synthesizers (e.g., [6, 29]) 和 inductive synthesizers (e.g., [19, 27])
- 提到了 SmartSpec [X] 和三个局限（limited language coverage, heavy spec burden, brittle feedback loops）

**操作建议**：【部分复用 + 扩展】
- **可复用**：英文版 Para 2 的"三个局限"结构可以直接翻译为中文 v2 的框架。
- **需新增**：
  - Synquid [17] / Flash Fill [18] 的引用（中文 v2 新增，英文旧版没有）
  - MoveScan [14] 的统计数据（英文旧版 Background 里有，但 Intro 没有）
  - **MSG 区分**（最关键的新增）：Code→Spec vs Spec→Code 的明确对比
- **英文素材位置**：`draft.md` Section 2.1 和 Section 3 有 MoveScan 和 MSG 的英文描述，可以搬运到 Intro。

---

## P3：Move 验证友好性 → Thala 案例

**中文 v2 内容**：
- Bartoletti et al.：Move better suited for verification than Solidity
- Thala Labs 案例（2024.11，$25.5M，2 行补丁）
- 形式化验证本可阻止，但 spec→code 同样困难

**英文旧版对应**：
- **没有 Thala 案例**。英文版 motivating example 直接从 `update_performance_statistics` 开始。
- `draft.md` Section 1.1 有 Thala 的简短提及，但被压缩进了 motivating example 段落。

**操作建议**：【需重写】
- 中文 v2 把 Thala 案例从独立段落压缩进了 P3，作为"真实世界钩子"。
- 英文素材：
  - `outline_expanded.md` Section 5 有 Thala 案例的完整素材（段 1）
  - Bartoletti et al. 的对比表也在 `outline_expanded.md` Section 3
- **注意**：不要展开 Thala 太多，1-2 句话带过即可，重点要快速落到 spec→code 的困难。

---

## P4：Motivating Example（stake_update_perf）

**中文 v2 内容**：
- stake_update_perf 的 spec 简述
- 3 个 idioms：ghost var update、while-header invariant、overflow assume
- Generic feedback（B6）失败：2 轮后仍 timeout
- Manual diagnosis 成功：1 轮通过，76.95s
- Insight：codegen 能力够，瓶颈在 diagnosis

**英文旧版对应**：
- 英文版 Para 4（Section 1.1 Motivating Example）和这段**几乎完全一致**。
- 同样有 3 idioms、generic feedback 失败、manual diagnosis 成功、insight。

**操作建议**：【高度可复用】
- 英文旧版的 Motivating Example 写得很好，可以直接用。
- **唯一需要新增**：中文 v2 提到了"2 轮后仍 timeout"，英文旧版说"After a second round the result is still a failure"——一致，无需修改。

---

## P5：核心论点（Thesis Statement）+ 多模型对比

**中文 v2 内容**：
- 重新审视 LLM + 形式化验证架构的必要性
- 单次生成不可靠（Behavioral Drivers：>20% 任务持续失败）
- 自我辩护偏差
- **多模型对比**（关键新增）：
  - Kimi：zero-shot + generic feedback 均失败
  - Claude Opus 4.7：1 轮结构化诊断通过（72.7s）
  - GPT 5.5：zero-shot "通过"但遗漏逻辑，Pass@1 有缺陷
- **Thesis Statement**（粗体）：双角色架构比单模型直接生成更能有效提升验证通过率

**英文旧版对应**：
- **完全没有这段**。英文旧版在 motivating example 之后直接进入 contributions，没有论点展开和多模型对比。
- `outline_expanded.md` Section 6 有"多模型对比实验"的完整素材。

**操作建议**：【需重写 — 这是整篇 intro 最重要的新增段落】
- 英文旧版缺失 thesis statement 和多模型对比，这是 v2 最大的改进。
- 英文素材来源：
  - `outline_expanded.md` Section 6 "多模型对比实验"表格和结论
  - `draft.md` Section 5.5 的 Claude/GPT/Kimi 结果（你 5/8 跑的实验）
- **必须包含的元素**：
  1. Thesis statement（一句话概括核心论点）
  2. 多模型对比表格或叙述
  3. Pass@1 缺陷的指出（GPT 5.5 遗漏 failed_proposer_indices）

---

## P6：Contributions（4 条）

**中文 v2 内容**：
1. 诊断分类学与双角色架构
2. Verifier-in-the-Loop 合成机制
3. 结构化诊断反馈协议
4. 实现与跨模型评估

**英文旧版对应**：
- 英文版有 3 条贡献：
  1. Two-role architecture
  2. Domain-specific diagnosis taxonomy
  3. Empirical separation of concerns
- **没有第 4 条"跨模型评估"**。

**操作建议**：【扩展第 4 条】
- 英文旧版的前 3 条可以保留，措辞微调即可。
- **新增第 4 条**：基于 `outline_expanded.md` Section 6 的多模型对比，写"Cross-model evaluation revealing the systematic deficiency of Pass@1 in verification settings"。
- 参考中文 v2 的表述："在 Aptos 标准库和真实世界合约上实现 MoVES 原型系统，通过对比 Kimi、Claude 和 GPT..."

---

## 引用编号统一提醒

两个版本的引用编号**不兼容**，不能混用：

| 编号 | 英文旧版 (draft.md) | 中文 v2 |
|------|---------------------|---------|
| [5] | Move Prover (Angelis/CPAL — 错误) | PatchDiff (Wang, ICSE 2026) |
| [12] | — | SmartSpec |
| [13] | — | Bartoletti (FMBC 2025) |
| [14] | — | MoveScan (ISSTA 2024) |
| [19] | — | MSG (ASE 2025) |

**建议**：以中文 v2 的编号体系为准（因为它更完整），但需要查 BibTeX 确认每个引用的正确信息。

---

## 快速操作清单

1. **直接搬运**：P4 Motivating Example（英文旧版写得很好，几乎不用改）
2. **小幅修改**：P2 传统合成局限（复用英文旧版 Para 2 框架，加 Synquid/Flash Fill/MSG 区分）
3. **新增撰写**：P1 SWE-bench 开头、P3 Thala 案例、P5 Thesis Statement + 多模型对比
4. **扩展**：P6 增加第 4 条贡献

按这个映射，应该能在 1-2 小时内拼出一版完整的英文 intro。