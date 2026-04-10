# M1：nft-marketplace（move-by-examples）

- **Move 包**：`E:\src\move-poc\baseline\mbe_nft_marketplace`
- **注入**：`sources/marketplace.move` 中 `test_fixed_price` 将卖家余额期望从 **10500** 错写为 **10499**（售价 500，原余额 10000）。
- **金标准**：`aptos move test --package-dir <包路径>` 全部通过。
- **说明**：已删除与本地 `aptos-framework` 行为不一致的 `test_not_enough_coin_fixed_price`（避免基线误报）。

## 评估红线（禁止人工修补）

仅将 Agent **机械**输出的代码写入目标文件后判分；**不得**手改模型补丁再测。
