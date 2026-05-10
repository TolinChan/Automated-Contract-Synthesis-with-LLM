```
┌─────────────────────────────────────────────────────────────┐
│  冻结输入（Frozen Inputs）                                    │
│    • function signature                                     │
│    • formal spec block（只读、LLM不能修改）                    │
│    • module context（函数相关内容上下文）                       │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
                ┌─────────────────┐      body_0
                │   Codegen LLM   │ ─────────────────┐
                │  （生成函数体）   │                  │
                └─────────────────┘                  ▼
                      ▲                    ┌─────────────────────┐
                      │                    │  Splice + Verifier  │
                feedback prompt             │                    │
                      │                     └─────────────────────┘
                      │                              │
                      │                   pass / fail+stderr+stdout
                      │                              │
                      │                     ┌────────┴─────────┐
                      │                     │                  │
                      │                  halt              ┌──────────┐
                      │               (success)            │ Diagnose │
                      │                                    │   LLM    │
                      │                                    │          │
                      │                                    └──────────┘
                      │                                       │
                      └───────────────────────────────────────┘
                                     diagnosis_k
```

**输入**：一个 Move 函数的签名（signature）、固定的形式化规范（`spec fun` 块），以及可选的模块上下文（imports、structs、常量、兄弟函数签名、模块级 ghost 变量声明）。

**输出**：一个函数体（body），使得将其拼接到签名中后，`aptos move prove` 能够成功通过验证。

**约束**：spec 块在整个流程中只读不可改，唯一可编辑的表面是函数体。

### Step 1: 输入准备（Input Preparation）

**做什么**：从 `aptos-framework` 源码中提取并固定每个测试函数的输入素材。

**输入**：

| 字段             | 来源                   | 说明                                                         |
| ---------------- | ---------------------- | ------------------------------------------------------------ |
| `signature`      | 源码 `.move` 文件      | 函数的完整签名，含可见性、泛型参数、参数列表、返回值         |
| `spec_block`     | 源码 `.spec.move` 文件 | `spec fun` 块，含 `requires`/`ensures`/`aborts_if`/`modifies`/`invariant` |
| `module_context` | 同模块源码             | imports、structs、常量、兄弟函数签名、模块级 ghost 变量声明  |
| `reference_body` | 源码 `.move` 文件      | 参考实现（仅用于 sanity check 和对比）                       |

**输出**：每个函数一个目录，内含 `signature.txt`、`spec.txt`、`module_context.txt`、`reference_body.txt`。

**设计动机**：

- **为什么冻结 spec？** 如果允许 LLM 修改 spec 来"配合"代码，验证通过将失去意义。spec 是开发者意图的精确表达，必须作为不可变约束。
- **为什么提取 module_context？** 函数体通常依赖同模块的 struct 定义、常量、辅助函数签名。（目前feasibility test的context很长，后续的实验可以尝试压缩）

**openquestion**：

- 现在的feasibility test只针对单一函数进行测试，后续真实实验需要调整到：给 LLM 整个模块的骨架（多个函数的 signature + spec），让它一次性填充所有 body

### Step 2: 代码生成 — Round 0（Codegen）

**做什么**：向 Codegen LLM 发送 prompt，要求它生成满足 spec 的函数体。

**输入**：

| 字段           | Round 0 |
| -------------- | ------- |
| signature      | ✓       |
| spec_block     | ✓       |
| module_context | ✓       |
| previous_body  | ✗       |
| diagnosis      | ✗       |

**Prompt 模板（目前测试用的）**：

```
Task: Write the body of a Move function so that it satisfies the formal specification.

Constraints:
- Move (Aptos dialect) source code only
- Use only standard built-ins and items in the same module
- Do NOT modify the spec block

=== Function Signature ===
{signature}

=== Formal Specification ===
{spec_block}

=== Module Context ===
{module_context}

=== Output format ===
Return ONLY the function body wrapped in:
<<<BODY
... your Move code here ...
BODY>>>
```

**输出**：LLM 的文本响应，从中提取 `<<<BODY ... BODY>>>` 或 ` ```move ` 块中的代码。

**设计动机**：

- **为什么用围栏标记（fence marker）？** LLM 喜欢在回答中添加解释性文字。强制使用 `<<<BODY ... BODY>>>` 标记使得提取可以自动化（`body_fence.py`），无需人工清理。
- **为什么 temperature=0.2？** 这是代码实现中的当前默认值，来自早期调试经验。尚未进行系统的 temperature 消融实验（如 temperature=0 与 temperature=0.5 的对比），因此无法断言 0.2 是最优值。
- **为什么要求"只返回 body"？** 减少 token 消耗，降低 LLM 在输出中重复 signature 或修改 spec 的概率。

### Step 3: 拼接与验证（Splice + Verify）

**做什么**：将生成的 body 拼接到 workspace 的 aptos-framework 源码中，运行 `aptos move prove`。（后续实验应该要修改，如果是针对一个完整的move代码，不能像现在测试这样拼进去）

**输入**：

| 字段               | 说明                                                         |
| ------------------ | ------------------------------------------------------------ |
| `function_id`      | 用于定位目标文件和函数名                                     |
| `body`             | Step 2 提取的代码字符串                                      |
| `canonical_source` | E:\\src\\move-poc\\synth\\framework_workspace 下的干净源码副本 |

**过程**：

1. **Workspace 重置**：将 workspace 下**所有** `.move` 文件从 canonical copy 恢复。原因：上一轮失败的 body 可能污染了其他模块，如果不全量恢复，下一轮验证会继承前一轮的错误。
2. **函数定位**：用正则匹配 `fun <name>(...)`，找到目标函数在文件中的位置。
3. **Body 替换**：用 brace-matching 找到函数体的 `{...}` 范围，将内部内容替换为生成的 body。
4. **运行验证器**：执行 `aptos move prove --filter <module>`，600s 超时。
5. **编译错误补救**：如果 `aptos move prove` 只输出 JSON summary（如 `{"Error":"Move Prover failed: exiting with N errors in compilation"}`），自动重跑 `aptos move compile` 捕获真实编译错误，附加到 stderr 中。

**输出**：`VerifyResult` 记录

| 字段                | 说明                                                         |
| ------------------- | ------------------------------------------------------------ |
| `passed`            | exit_code == 0                                               |
| `exit_code`         | 0（通过）、-1（拼接失败）、-2（超时）、-3（提取失败）、>0（验证/编译错误） |
| `stdout` / `stderr` | prover 完整输出                                              |
| `prove_time_sec`    | 墙钟时间                                                     |
| `error_summary`     | 从 stderr/stdout 提取的首个错误提示（300 字符截断）          |
| `splice_succeeded`  | body 是否成功拼接到源文件中                                  |

**设计动机**：

- **为什么全量重置 workspace 而不是只恢复目标文件？** 因为 aptos-framework 模块间存在依赖。如果上一轮在 module A 中留下了语法错误，下一轮验证 module B 时编译整个包会失败在 A 上，造成虚假失败。全量重置是"确定性沙盒"的最便宜实现。
- **为什么编译错误需要补救？** `aptos move prove` 在编译失败时吞掉具体错误信息，只返回一个 JSON summary。这对诊断 LLM 是致命的——它看不到 "expected `;`" 或 "unbound variable" 这样的具体信息，无法给出 actionable fix。
- **为什么 verifier 是唯一真值源？** 绝不让 LLM 判断"这段代码看起来对不对"。LLM 容易产生幻觉式成功（hallucinated success），而 verifier 的 exit code 是客观的。

### Step 4: 诊断（Diagnose）— 仅在验证失败时执行

**做什么**：将 prover 的失败输出交给 Diagnose LLM，让它分类失败原因并给出结构化修复指令。

**输入**：

| 字段                              | 来源                                                         |
| --------------------------------- | ------------------------------------------------------------ |
| `signature`                       | 冻结输入                                                     |
| `spec_block`                      | 冻结输入                                                     |
| `module_context`                  | 冻结输入                                                     |
| `failed_body`                     | Step 2/5 生成的失败 body                                     |
| `prover_stdout` / `prover_stderr` | Step 3 的 verifier 输出（截取尾部 4000 字符，这个有待商榷，可能会遗漏） |

**Prompt 核心结构**：

1. **Move-Prover Idiom Checklist**：内置三个 domain-specific idiom 的识别指南和修复模板：

   - Ghost-variable spec updates：`spec { update ghost_x = ...; };`
   - While-header invariant placement：`while ({ spec { invariant ... }; cond })`
   - Overflow assume：`spec { assume X + 1 <= MAX_U64; };`

2. **诊断输出格式要求**：

   ```
   CATEGORY: <compile_error | type_error | api_misuse | ghost_var_missing | 
              loop_invariant_placement | overflow_assume_missing | ...>
   ROOT_CAUSE: <一两句话定位根本原因>
   FIX_INSTRUCTION: <具体修复指令，引用 exact code snippet>
   ```

**输出**：结构化诊断文本（三个 labeled section）。

**设计动机**：

- **为什么分离 Codegen 和 Diagnose 两个角色？**
  1. **防止自我辩护**：同一个 LLM 在生成代码后又诊断自己的错误，倾向于用局部补丁掩盖问题，而不是承认缺失了某个 idiom。
  2. **瓶颈可独立测量**：如果手写 diagnosis 能让 codegen 一次通过，证明 codegen 能力足够，瓶颈在 diagnoser。这是 feas_run_02 的核心发现。
  3. **不同技能需求**：codegen 需要"写代码"的能力，diagnoser 需要"读错误输出 + 映射到领域知识"的能力，两者是不同的 prompt engineering 问题。

- **为什么诊断必须用 domain idioms 而不是 raw prover error？**（P4）
  Raw prover 输出是 Boogie/Z3 级别的（"VC failure at line 47"、"SMT timeout"、"counterexample: ..."），对 codegen LLM 来说过于底层。Codegen 需要的是"在 while 头部加 invariant"这样的 actionable instruction。Diagnoser 的角色就是**桥接**这两个抽象层级。

- **为什么 diagnose prompt 里硬编码 idiom checklist？**（这一点后续做实验应该要优化，可能会把diagnose 常见的问题打包成skill或者别的，需要去学习一下怎么微调llm）
  因为这些是 Move Prover 特有的写法，LLM 在训练数据中极少见到（Move Prover 用户群很小）。没有 checklist，diagnoser 会把 timeout 诊断为"需要减少循环迭代次数"，而不是"需要在 `+= 1` 前加 overflow assume"。

### Step 5: 反馈生成与再合成（Feedback → Codegen Round k）

**做什么**：将诊断结果、失败的 body、冻结输入组合成 feedback prompt，送回 Codegen LLM 生成修正后的 body。

**输入**：

| 字段             | 说明                                                         |
| ---------------- | ------------------------------------------------------------ |
| `signature`      | 冻结输入（始终不变）                                         |
| `spec_block`     | 冻结输入（始终不变）                                         |
| `module_context` | 冻结输入（始终不变）                                         |
| `previous_body`  | 上一轮生成的失败 body                                        |
| `diagnosis`      | Step 4 的结构化诊断（CATEGORY / ROOT_CAUSE / FIX_INSTRUCTION） |

**Prompt 模板**：

```
Your previous attempt at this Move function body failed `aptos move prove`.
Use the diagnosis to produce a corrected body. The spec block must NOT change;
only the body changes.

=== Function Signature ===
{signature}

=== Formal Specification ===
{spec_block}

=== Module Context ===
{module_context}

=== Previous Body (failed) ===
{previous_body}

=== Diagnosis ===
{diagnosis}

=== Output format ===
Return ONLY the corrected function body wrapped in:
<<<BODY
... your corrected Move code here ...
BODY>>>
```

**输出**：新的 body（同样用 fence marker 包裹）。

**设计动机**：

- **为什么 feedback prompt 不包含 raw prover output？** 设计文档 3.5 明确要求"feedback prompt 是结构化组合，不是叙事"。Raw prover output 已被 diagnoser 处理过，如果再把原始输出塞给 codegen，会造成：① 上下文膨胀；② 信息冗余（diagnosis 已经总结了关键信息）；③ 可能让 codegen 被底层错误信息干扰，偏离高层修复方向。
- **为什么保留 previous_body 而不是从头生成？** 实验发现，让 LLM 在 previous body 基础上修改比从零重新生成收敛更快。previous body 通常只差一两个 idiom，保留它可以避免 LLM 在完全正确的部分引入新错误。
- **为什么每次 feedback 都要重复冻结输入？** 因为 LLM 是无状态的（除少数支持多轮对话的 API 外），每一轮都是独立的 API call，必须携带完整上下文。

---

### Step 6: 循环控制与终止条件（Loop Control）

**做什么**：管理反馈轮次，决定何时停止。

**控制策略**：

| 条件                                      | 行为                                     |
| ----------------------------------------- | ---------------------------------------- |
| verifier exit code == 0                   | **成功停止**，记录 `rounds_to_success`   |
| 达到 `feedback_rounds` 上限（B6=1, B7=3） | **失败停止**，标记为未通过               |
| body 提取失败（无 fence marker）          | 计为一次失败轮次，继续下一轮（如有预算） |

**指标定义**：

| 指标                | 含义                                                      | 适用 baseline |
| ------------------- | --------------------------------------------------------- | ------------- |
| `Pass@1`            | Round 0 就通过（无任何 feedback）                         | B1, B3        |
| `rounds_to_success` | 第几次尝试通过（1=round 0, 2=第1轮 feedback 后通过，...） | B6, B7        |

**设计动机**：

- **为什么区分 Pass@1 和 rounds_to_success？** 两者衡量的是不同能力：Pass@1 衡量模型的"一次性生成能力"（类似编程竞赛中的第一次提交）；`rounds_to_success` 衡量"在结构化反馈下的收敛能力"。混用会误导读者——一个模型 Pass@1 高可能只是记住了训练数据，而 rounds_to_success 低才说明它能从反馈中真正学习。
- **为什么 B6 只给 1 轮 feedback？** 为了测试"最小 feedback 是否能修复"。如果 1 轮不够，说明 diagnose 质量不足或问题本身需要多轮迭代。
- **为什么 B7 给 3 轮？** 测试"增加 budget 是否能挽救失败 case"。实验发现 stake_update_perf 在 B7 下反而越反馈越差（从编译错误退化到连续 timeout），这本身就是一个重要发现：无质量的 feedback 增加轮次只会引入更多错误。