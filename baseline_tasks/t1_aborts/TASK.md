# T1：hello_prover — `abortsIf0` 与 `aborts_if` 不一致

- **Bug**：`x == 0` 分支内未调用 `abort(0)`，但 spec 要求 `aborts_if x == 0;`
- **金标准**：`E:\src\move-poc\baseline\hello_prover_t1_aborts` 下 `aptos move prove` → Success
- **禁止**（默认）：修改 `spec`；只改 `abortsIf0` 实现。
- **参考答案**：`golden/prove.move`（与 T0 同包布局）。
