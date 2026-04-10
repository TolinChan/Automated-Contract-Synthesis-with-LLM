# M1（mbe_nft_marketplace）结果记录模板


| 日期  | Baseline（A 网页/API / B Agent） | 模型或产品名 | 机械应用后 Pass@1 | 失败阶段（解析/编译/测试） | 原始输出路径 |
| --- | ---------------------------- | ------ | ------------ | -------------- | ------ |
|     |                              |        |              |                |        |


**Pass@1**：将 `model_response.txt` 中**第一个** fenced 代码块（语言标记为 `move`，与 `apply_and_check_mbe.py` 一致）**原样**写入 `E:\src\move-poc\baseline\mbe_nft_marketplace\sources\marketplace.move` 后，一次 `aptos move test --package-dir` 是否全部通过。**禁止**为通过而手改模型输出或补丁内容。