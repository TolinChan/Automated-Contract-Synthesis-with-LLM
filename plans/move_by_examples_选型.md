# move-by-examples 本地克隆与选型备忘

- **仓库路径**：`E:\src\move-by-examples`（`git clone --depth 1 https://github.com/aptos-labs/move-by-examples.git`）
- **官方说明**：根目录 [README.md](file:///E:/src/move-by-examples/README.md) 概述了单合约、事件、FT/NFT、跨合约调用、单测、脚本等主题。

## 含 Move 包的主要示例（按体量大致排序）

| 示例目录 | Move 包路径（`aptos move compile/test` 常用 `--package-dir` 指这里） | 约 `.move` 文件数* | 适用性简述 |
|----------|----------------------------------------------------------------------|-------------------|------------|
| **billboard** | `billboard/move` | 1 | 极简，适合「比 hello 稍大」的冒烟或自定义注入。 |
| **dutch-auction** | `dutch-auction/move` | 1 | 单文件拍卖逻辑，适合 **test/编译** 基线。 |
| **nft-launchpad** | `nft-launchpad/move` | 1 | 单文件 NFT 发布，叙事贴近链上资产。 |
| **fungible-asset-launchpad** | `fungible-asset-launchpad/aptos/move` | 1 | FA 发布入门，依赖官方 framework（git）。 |
| **simple-todo-list** | `simple-todo-list/aptos/move` | 3 | 与 **advanced-todo-list** 可组成「简单 vs 进阶」对照。 |
| **advanced-todo-list** | `advanced-todo-list/aptos/move` | 3 | 比 simple 功能多，适合 **多入口、多结构** 的 Agent 导航实验。 |
| **friend-tech** | `friend-tech/aptos/move` | 3 | 社交/份额类业务，适合 **业务叙事 + test**。 |
| **nft-marketplace** | `nft-marketplace/move` | 2 | 市场 + TokenObjects，**中等复杂度**，依赖 `aptos-token-objects`（git）。 |
| **fungible-asset-voting** | `fungible-asset-voting/move` | 2 | 投票 + FA，适合治理类故事。 |
| **fungible-asset-with-permission** | `fungible-asset-with-permission/move` | 2 | 权限与 FA，适合「策略/权限」相关错误注入。 |
| **fungible-asset-vesting** | `fungible-asset-vesting`（包在根下） | 2 | 锁仓释放，**时间/金额** 组合，适合较难单测场景。 |
| **fungible-asset-with-buy-sell-tax** | `fungible-asset-with-buy-sell-tax/move/FungibleAssetWithBuySellTax` 等 | 多包 | **最复杂之一**：多子包 + DEX 接口；适合高阶 baseline，需耐心解决依赖。 |
| **multidex-router** | `multidex-router/move` | 8（含本包 sources） | **体量最大**：依赖 Liquidswap（git）、本地 `third_party_dependencies/PancakeSwap`；仓库内可见少量 `spec`（多为未完整验证）。适合 **压力测试**，不适合作为第一个复杂例。 |

\*文件数为该包路径下递归 `*.move` 数量，含测试；`multidex-router` 未计入全部 third_party 体积。

**脚注（M1 基线副本）**：课题侧落地副本 `E:\src\move-poc\baseline\mbe_nft_marketplace` 中已移除上游自带的 `test_not_enough_coin_fixed_price`（原 `#[expected_failure]` 与本地 `AptosFramework` 下实际 abort 模块不一致，会导致注入前也无法全绿）。其余用例与单点注入任务见 `baseline_tasks/mbe_nft_marketplace/`。

## 与课题目标的匹配建议

1. **先做「复杂一点、但仍好编译」**（推荐优先级）  
   - **`nft-marketplace/move`** 或 **`fungible-asset-vesting`**：业务感强、文件数少，便于 **人为制造单点 test/编译失败** 做 Coding Agent baseline。  
   - **`advanced-todo-list/aptos/move`**：与已有 **simple-todo** 形成梯度。

2. **Move Prover 为主**  
   - 本仓库 **几乎无** 像 `hello_prover` 那样成体系的 `spec`；仅 **`multidex-router`** 的第三方目录里可见个别 `spec` 片段。  
   - 若以 Prover 为核心，更现实做法是：**在上述某一包内自行为关键函数加少量 spec**，再注入实现错误（与你们 `defi` 笔记结论一致）。

3. **暂缓**  
   - **`multidex-router`**、**`fungible-asset-with-buy-sell-tax`**：依赖多、拉取慢，适合环境稳定后再开。

## 下一步可操作项（如需可再执行）

- 对选定包运行：`aptos move compile --package-dir <路径>` / `aptos move test --package-dir <路径>`，记录是否需代理或 git 依赖失败。  
- 将选中包 **复制或软链** 到 `E:\src\move-poc\baseline\` 并改写 `Move.toml` 为 **本地 `aptos-framework`**（与现有 [ENV_SETUP.md](ENV_SETUP.md) 一致），便于离线/稳定复现。

---

*生成日期：2026-04-01；克隆源：`aptos-labs/move-by-examples` main。*
