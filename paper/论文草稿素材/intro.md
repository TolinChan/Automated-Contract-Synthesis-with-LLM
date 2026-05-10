## 1. Introduction

Smart contracts manage high-value digital assets on blockchains. A single bug can lead to irreversible financial loss—attacks on smart contracts have caused billions of dollars in damages [12, 21]. Formal verification offers mathematical guarantees of correctness, but writing both the implementation and the formal specification is labour-intensive and requires deep expertise in verification tools. Program synthesis from formal specifications offers a compelling alternative: the developer writes a high-level specification, and a synthesizer automatically generates a provably correct implementation.

However, traditional synthesizers face a fundamental tension between precision and practicality. Deductive synthesizers (e.g., [6, 29]) generate correct-by-construction code from complete specifications, but the specification burden is heavy and the supported language fragments are limited. Inductive synthesizers (e.g., [19, 27]) learn from examples, but offer no formal guarantees. Recent hybrid approaches combine both paradigms: SmartSpec [X] uses a multi-modal specification (relational inference rules plus temporal logic) and combines deductive sketch generation with counterexample-guided inductive synthesis (CEGIS) to produce maximally permissive smart contracts. On 27 Solidity contracts, SmartSpec achieves 85% match with reference implementations without interactive refinement; the remaining cases require up to four rounds of manual feedback through extra examples.

Despite these advances, traditional synthesizers remain constrained in three ways:

1. **Limited language coverage.** SmartSpec supports only a restricted fragment of Solidity: deterministic guards, fixed side-effect-free UDFs, bounded loops, no external calls, and no recursion. Extending to other smart-contract languages—particularly those with rich verification infrastructure like Aptos Move—requires rebuilding the entire synthesis engine.
2. **Heavy specification burden.** The developer must write precise inference rules and temporal logic formulas. While these are more declarative than code, they still demand expertise in formal methods. For less experienced developers, writing correct specifications is as hard as writing correct code.
3. **Brittle feedback loops.** When synthesis fails, the CEGIS loop produces counterexamples that the developer must manually interpret and translate into specification refinements. Four rounds of manual feedback is acceptable for research evaluation, but impractical for production use.

Large language models (LLMs) offer a path around these limitations. LLMs can generate code from natural-language or formal specs [1, 2, 3, 4], and recent work has extended this to specification-driven generation [X]. Unlike traditional synthesizers, LLMs are not tied to a specific language fragment: they can generate any code expressible in their training data, including complex Move functions with ghost variables, loop invariants, and overflow assumptions. Moreover, LLMs can interpret feedback in natural language, potentially closing the feedback loop without manual intervention.

But LLM-based synthesis introduces its own challenges. When the target language includes a built-in formal verifier—as Aptos Move does with the Move Prover [5]—a generated body that "looks correct" may still fail verification because of subtle domain-specific requirements (e.g., ghost-variable bookkeeping, loop-invariant placement, arithmetic-overflow assumptions) that the LLM has not encountered in its training data. A natural response is to close the loop: run the verifier, feed its error output back to the LLM, and ask for a revised body. Prior work has explored this pattern in other domains [6, 7, 8], but two problems remain under-addressed:

1. **Raw verifier output is too low-level.** The Move Prover emits Boogie/Z3-level messages (verification-condition failures, SMT timeouts, counter-example traces). Feeding these directly into an LLM as "feedback" overwhelms the context window and does not surface the high-level code transformation required.
2. **Asking one LLM to both generate and self-critique conflates two distinct tasks.** A generator asked to repair its own output tends to make local, syntactic patches rather than recognise missing domain idioms; the failure mode and the fix are often orthogonal skills.

We address both problems with **two-role separation** and **structured domain-specific diagnosis**. MoVES splits the work between a *codegen* role (produce a body) and a *diagnoser* role (analyse verifier output and prescribe fixes in the vocabulary of Move-Prover idioms). The diagnoser's output is not raw prover stderr; it is a typed record `{CATEGORY, ROOT_CAUSE, FIX_INSTRUCTION}` phrased in domain terms the codegen role can act on.

### 1.1 Motivating Example

Consider `update_performance_statistics` from the Aptos `stake` module, a function that updates validator performance counters. Its specification (held fixed throughout our experiments) declares two module-level ghost variables, a while-loop over failed proposer indices, and post-conditions relating the updated state to the input snapshots.

When we ask an LLM (`kimi-for-coding`) to generate the function body from the signature and spec alone (zero-shot), it produces a body that compiles but fails verification with a timeout after 72 s. The generated body is missing three Move-Prover-specific idioms:

- **Idiom 1 — Ghost-variable update.** The spec references `global ghost_valid_perf` and `global ghost_proposer_idx`; the body must initialise them with `spec { update ghost_valid_perf = validator_perf; }` blocks, not regular `let` bindings.
- **Idiom 2 — While-header invariant placement.** Loop invariants must be placed inside the while-header expression (`while ({ spec { invariant ... }; cond })`), not in the loop body. The LLM places them in the body, triggering a compile-level prover error.
- **Idiom 3 — Overflow assume.** Every `u64 += 1` must be preceded by `spec { assume X + 1 <= MAX_U64; };`, otherwise the prover generates an unbounded overflow verification condition and times out.

We then run a generic feedback loop (B6): the prover error is fed back to the LLM with a prompt that asks it to diagnose and fix. After one feedback round the body changes, but two of the three idioms are still wrong; the error type shifts from timeout to "loop invariants must be declared at the beginning of the loop header." After a second round the result is still a failure. The loop is making *some* progress, but the generic diagnoser does not surface the idiom-level fixes because it has no Move-Prover checklist.

Finally, we hand-write a structured diagnosis that explicitly names all three idioms with code-level instructions, feed it through the *same* codegen prompt, and the resulting body passes verification in 76.95 s on the first attempt. The generated body matches the reference implementation almost line-for-line.

**Insight.** The LLM's *code-generation* capability is sufficient to produce a verifying body for this complex function. The bottleneck is the *diagnosis* step: without a domain-specific taxonomy that bridges raw prover output to actionable code transformations, the feedback loop cannot converge.

### 1.2 Contributions

We make the following contributions:

1. **A two-role architecture for verifier-in-the-loop synthesis.** We separate code generation from error diagnosis into distinct LLM roles with distinct contracts, preventing the generator from defending its own mistakes and making the bottleneck (diagnosis quality) independently measurable.
2. **A domain-specific diagnosis taxonomy for Move Prover.** We identify a finite set of failure modes and canonical fixes (ghost-variable update, while-header invariant placement, overflow assume) that bridge raw verifier output to actionable codegen instructions.
3. **An empirical separation of concerns.** A minimal feasibility test on five Aptos-framework functions shows that zero-shot codegen succeeds on 4/5; the one failure is repaired in one round by structured manual diagnosis but not by generic feedback. This demonstrates that codegen capability is not the limiting factor—diagnosis quality is.

### 1.3 Paper Organisation

Section 2 introduces Move, the Move Prover, and the spec-driven synthesis task. Section 3 surveys related work. Section 4 presents the MoVES design. Section 5 reports the minimal feasibility test. Section 6 discusses threats to validity and open questions. Section 7 concludes.
