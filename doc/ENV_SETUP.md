# Move Prover 环境（Windows / E 盘侧布局）

本仓库 PoC 依赖 **Aptos CLI**、**Boogie 3.5.1**、**Z3** 与本地 **aptos-framework**（避免克隆整棵 aptos-core）。

## 1. 已验证版本

| 组件 | 说明 |
|------|------|
| Aptos CLI | `aptos 9.1.0`（winget 安装路径可在 `where aptos` 查看） |
| Boogie | **必须为 3.5.1.x**（`dotnet tool install --global boogie --version 3.5.1`）；过高版本会被 CLI 拒绝 |
| .NET SDK | 8.x（用于安装 Boogie） |
| Z3 | 例如 `E:\tools\z3_extract\z3-4.13.0-x64-win\bin\z3.exe` |

## 2. 环境变量（每次开新终端执行 prove 前建议设置）

```powershell
$env:BOOGIE_EXE = "C:\Users\96247\.dotnet\tools\boogie.exe"
$env:Z3_EXE     = "E:\tools\z3_extract\z3-4.13.0-x64-win\bin\z3.exe"
```

可将上述两行写入用户环境变量，避免每次手动设置。

## 3. 本地路径

| 路径 | 内容 |
|------|------|
| `E:\src\aptos-framework` | 浅克隆的 [aptos-framework](https://github.com/aptos-labs/aptos-framework)（与 hello_prover / defi 的 `Move.toml` 中 `local` 依赖一致） |
| `E:\src\move-poc\hello_prover` | 最小 prover 示例（来自 aptos-core move-examples） |
| `E:\src\move-poc\defi` | `locked_coins.move` 单文件包（Move.toml 中 `defi = "0xDEF1"`） |
| `E:\src\move-poc\baseline\hello_prover_t0_plus1` | 基线任务 T0（`plus1` 注入，`Move.toml` 依赖 `../../../aptos-framework/aptos-framework`） |
| `E:\src\move-poc\baseline\hello_prover_t1_aborts` | 基线任务 T1（`abortsIf0` 注入） |
| `E:\src\move-poc\baseline\hello_blockchain_t2` | 基线任务 T2（`hello_blockchain` 测试断言错误） |

课题仓库内元数据、冻结日志与 Prompt：[baseline_tasks/](baseline_tasks/README.md)。

## 4. 常用命令

```powershell
# hello_prover（在包目录下）
cd E:\src\move-poc\hello_prover
aptos move prove

# defi（任意目录）
aptos move prove --package-dir E:\src\move-poc\defi

# 基线任务判分（需先设置 BOOGIE_EXE / Z3_EXE，T2 仅需 PATH 中有 aptos）
cd "e:\Automated Contract Synthesis and Repair with Large Language Models\baseline_tasks\scripts"
python check_task.py --task-id t0_plus1
python check_task.py --task-id t1_aborts
python check_task.py --task-id t2_hello_blockchain
```

## 5. 克隆 aptos-core（可选）

网络稳定时可克隆完整仓库以使用官方 `move-examples` 路径；本机曾因大仓库拉取中断，故采用 **E:\src\move-poc** + 本地 framework 的折中方案。

## 6. 课题仓库中的日志

验证输出已保存到 [poc_logs/](poc_logs/)，便于写报告时引用。
