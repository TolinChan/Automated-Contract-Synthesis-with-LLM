# T2：hello_blockchain — 单元测试断言错误

- **Bug**：`hello_blockchain_test.move` 中期望字符串写为 `Hello Blockchain`（缺逗号），与真实消息 `Hello, Blockchain` 不一致，导致 `message_tests::sender_can_set_message` 失败。
- **金标准**：`E:\src\move-poc\baseline\hello_blockchain_t2` 下 `aptos move test` 全部通过。
- **禁止**（默认）：修改 `hello_blockchain.move` 业务逻辑；只修测试或按题目要求仅修一处断言。
- **参考答案**：`golden/hello_blockchain_test.move`（在 Move 包目录内）。
