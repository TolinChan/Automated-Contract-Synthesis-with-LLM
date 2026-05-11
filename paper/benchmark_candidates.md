# MoVES Benchmark 候选函数列表

> 生成时间：2026-05-11
> 来源：aptos-framework 源码扫描（`E:/src/move-poc/synth/framework_workspace/aptos-framework/sources/`）

---

## 重要发现

aptos-framework 中**大量函数标记了 `pragma verify = false;`**，不能直接用做 benchmark：

- **coin 模块**：`balance`, `deposit`, `transfer`, `withdraw`, `register`, `burn`, `burn_from` 等因 `fa_migration` 被禁用
- **stake 模块**：`withdraw`, `on_new_epoch`, `add_stake_with_cap`, `add_stake` 因 timeout/CI 失败被禁用
- **staking_contract 模块**：`unlock_rewards`, `unlock_stake` 因 timeout 被禁用
- **transaction_fee 模块**：`burn_fee`, `mint_and_refund` 因 `fa_migration` 被禁用
- **vesting 模块**：`distribute`, `distribute_many`, `terminate_vesting_contract` 因 timeout/依赖未验证被禁用

以下列表**仅包含当前可验证的函数**。

---

## L1 — Trivial（aborts_if false / 纯读取，spec <5 行）

| # | 函数 | 模块 | 特征 | 备注 |
|---|------|------|------|------|
| 1 | `get` | `chain_id` | `aborts_if false` | feas_run_02 已测试 |
| 2 | `create_id` | `guid` | `aborts_if false` | |
| 3 | `id` | `guid` | `aborts_if false` | |
| 4 | `creator_address` | `guid` | `aborts_if false` | |
| 5 | `creation_num` | `guid` | `aborts_if false` | |
| 6 | `id_creator_address` | `guid` | `aborts_if false` | |
| 7 | `id_creation_num` | `guid` | `aborts_if false` | |
| 8 | `eq_id` | `guid` | `aborts_if false` | |
| 9 | `is_coin_initialized` | `coin` | `aborts_if false` | |
| 10 | `is_account_registered` | `coin` | `aborts_if false` | |

> guid 模块的 7 个 getter 函数都是纯读取、不 abort，适合作为最简单的 baseline。

---

## L2 — Simple（有 aborts_if + ensures，无 loop/ghost，5-15 行 spec）

| # | 函数 | 模块 | 特征 | 备注 |
|---|------|------|------|------|
| 11 | `initialize` | `chain_id` | 多个 `aborts_if` + `ensures` | feas_run_02 已测试 |
| 12 | `create` | `guid` | `aborts_if` + `ensures` + `MAX_U64` overflow | MSG 论文中 AIO 失败案例 |
| 13 | `initialize` | `version` | 多个 `aborts_if` + `ensures` | |
| 14 | `get_sequence_number` | `account` | `aborts_if !exists<Account>` + `ensures` | |
| 15 | `get_guid_next_creation_num` | `account` | `aborts_if !exists<Account>` + `ensures` | |
| 16 | `create_account_if_does_not_exist` | `account` | `modifies` + `aborts_if`（多条件）+ `ensures` | |
| 17 | `create_account` | `account` | `include` schema + `aborts_if` | |
| 18 | `create_account_unchecked` | `account` | `include` schema + `ensures` | |
| 19 | `merge` | `coin` | `ensures` + `old()`（无 aborts_if，但涉及状态变化）| |
| 20 | `stake_pool_address` | `staking_contract` | `aborts_if` + `ensures` | |
| 21 | `commission_percentage` | `staking_contract` | `aborts_if` + `ensures` | |

---

## L3 — Medium（modifies / schema / 多条件 / 15-30 行 spec）

| # | 函数 | 模块 | 特征 | 备注 |
|---|------|------|------|------|
| 22 | `extract` | `coin` | `aborts_if` + `ensures` | feas_run_02 已测试 |
| 23 | `initialize` | `block` | 多个 `aborts_if` + `ensures` | feas_run_02 已测试 |
| 24 | `set_version` | `version` | `requires` + 多个 `aborts_if` + `ensures` + 引用外部 schema | |
| 25 | `increment_sequence_number` | `account` | `modifies` + `aborts_if` + `MAX_U64` + `ensures` | |
| 26 | `update_voter` | `staking_contract` | `include UpdateVoterSchema` + `ensures` | |
| 27 | `create_staking_contract` | `staking_contract` | `include` 多个 schema + `verify_duration_estimate = 120` | |
| 28 | `create_staking_contract_with_coins` | `staking_contract` | 同上 | |
| 29 | `request_commission` | `staking_contract` | `include` schema + `ensures` | |

---

## L4 — Complex（loop / invariant / ghost / >30 行 spec / 跨模块依赖）

| # | 函数 | 模块 | 特征 | 备注 |
|---|------|------|------|------|
| 30 | `update_performance_statistics` | `stake` | ghost var + while invariant + overflow assume | feas_run_02 已测试 |
| 31 | `add_stake` | `staking_contract` | `verify_duration_estimate = 600`，include 4+ schema，复杂 postcondition | |

---

## 被排除的函数（`pragma verify = false;`）

以下函数虽然有 spec，但当前被禁用验证，**不能**用作 benchmark：

| 模块 | 被排除函数 | 原因 |
|------|-----------|------|
| `coin` | `balance`, `deposit`, `transfer`, `withdraw`, `register`, `burn`, `burn_from` | fa_migration |
| `stake` | `withdraw`, `on_new_epoch`, `add_stake_with_cap`, `add_stake` | timeout/CI 失败 |
| `staking_contract` | `unlock_rewards`, `unlock_stake` | timeout |
| `transaction_fee` | `burn_fee`, `mint_and_refund` | fa_migration |
| `vesting` | `distribute`, `distribute_many`, `terminate_vesting_contract` | timeout/依赖未验证 |

---

## 建议的 Benchmark 组合

### 方案 A：保守扩展（共 15 个）

在已有 5 个基础上，新增 10 个：

| 级别 | 新增函数 | 目的 |
|------|---------|------|
| L1 | `guid::id`, `guid::creator_address`, `guid::eq_id`, `coin::is_coin_initialized` | 验证"简单函数是否都能过" |
| L2 | `guid::create`, `version::initialize`, `account::get_sequence_number`, `account::create_account_if_does_not_exist` | 测试基础 codegen + aborts_if |
| L3 | `version::set_version`, `account::increment_sequence_number`, `staking_contract::update_voter` | 测试 schema/modifies 理解 |

### 方案 B：完整覆盖（共 25 个）

扩展至 25 个，覆盖 L1-L4：

| 级别 | 数量 | 函数来源 |
|------|------|---------|
| L1 | 6 | chain_id, guid, coin |
| L2 | 8 | guid, version, account, coin, staking_contract |
| L3 | 8 | coin, block, version, account, staking_contract |
| L4 | 3 | stake, staking_contract |

---

## 待决策问题

1. **选哪个方案？** 15 个还是 25 个？
2. **L4 候选太少**：aptos-framework 中复杂函数大多被禁用。如果实验需要更多 L4/L5，可能需要：
   - 从 move-examples 中找（如 `hello_prover` 的复杂函数）
   - 或**手动构造**（把多个简单函数组合成一个需要 loop 的函数）
3. **是否需要自动化筛选脚本**：自动扫描所有 `.spec.move` 文件，过滤掉 `verify = false`，按 spec 行数/关键字自动分级。
