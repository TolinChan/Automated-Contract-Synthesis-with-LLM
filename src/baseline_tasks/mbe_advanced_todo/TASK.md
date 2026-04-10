# M3：advanced-todo-list（move-by-examples）

- **Move 包**：`E:\src\move-poc\baseline\mbe_advanced_todo`
- **注入**：`sources/advanced_todo_list.move` 中 `test_end_to_end` 将 `todo_list_length == 1` 错写为 **`== 2`**。
- **金标准**：`aptos move test` 全部通过。

## 评估红线

机械应用 Agent 输出到 `sources/advanced_todo_list.move` 后判分；**禁止**人工改补丁再通过。
