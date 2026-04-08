# M2：fungible-asset-vesting（move-by-examples）

- **Move 包**：`E:\src\move-poc\baseline\mbe_fa_vesting`
- **注入**：`tests/vesting_tests.move` 中 `test_create_vesting_success` 将 `vestings.length() == 1` 错写为 **`== 2`**。
- **金标准**：`aptos move test` 全部通过。

## 评估红线

机械应用 Agent 输出到 `tests/vesting_tests.move` 后判分；**禁止**人工改补丁再通过。
