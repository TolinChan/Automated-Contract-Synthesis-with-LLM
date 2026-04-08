# T0：hello_prover — `plus1` 与后置条件不一致

- **Bug**：`plus1` 实现为 `x+2`，spec 仍为 `ensures result == x+1;`
- **金标准**：在 `E:\src\move-poc\baseline\hello_prover_t0_plus1` 执行 `aptos move prove` → `Result: Success`
- **禁止**（默认）：修改 `spec` 块；只改实现使证明通过。
- **参考答案**：见 Move 包内 `golden/prove.move`。