"""Registry for agent_verify_loop: E-disk package, file to patch, prove vs test."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
BASELINE_TASKS = SCRIPTS_DIR.parent


@dataclass(frozen=True)
class LoopTask:
    task_id: str
    package_dir: Path
    relative_file: str
    verify: str  # "prove" | "test"

    def target_path(self) -> Path:
        return self.package_dir / self.relative_file

    def meta_dir(self) -> Path:
        return BASELINE_TASKS / self.task_id


LOOP_TASKS: dict[str, LoopTask] = {
    "t0_plus1": LoopTask(
        task_id="t0_plus1",
        package_dir=Path(r"E:\src\move-poc\baseline\hello_prover_t0_plus1"),
        relative_file="sources/prove.move",
        verify="prove",
    ),
    "t1_aborts": LoopTask(
        task_id="t1_aborts",
        package_dir=Path(r"E:\src\move-poc\baseline\hello_prover_t1_aborts"),
        relative_file="sources/prove.move",
        verify="prove",
    ),
    "t2_hello_blockchain": LoopTask(
        task_id="t2_hello_blockchain",
        package_dir=Path(r"E:\src\move-poc\baseline\hello_blockchain_t2"),
        relative_file="sources/hello_blockchain_test.move",
        verify="test",
    ),
    "mbe_nft_marketplace": LoopTask(
        task_id="mbe_nft_marketplace",
        package_dir=Path(r"E:\src\move-poc\baseline\mbe_nft_marketplace"),
        relative_file="sources/marketplace.move",
        verify="test",
    ),
    "mbe_fa_vesting": LoopTask(
        task_id="mbe_fa_vesting",
        package_dir=Path(r"E:\src\move-poc\baseline\mbe_fa_vesting"),
        relative_file="tests/vesting_tests.move",
        verify="test",
    ),
    "mbe_advanced_todo": LoopTask(
        task_id="mbe_advanced_todo",
        package_dir=Path(r"E:\src\move-poc\baseline\mbe_advanced_todo"),
        relative_file="sources/advanced_todo_list.move",
        verify="test",
    ),
}


def get_loop_task(task_id: str) -> LoopTask:
    if task_id not in LOOP_TASKS:
        raise KeyError(task_id)
    return LOOP_TASKS[task_id]
