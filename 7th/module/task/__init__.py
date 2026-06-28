"""Task registry helpers for ALAS-style runtime dispatch."""

from module.task.registry import TaskSpec, create_task, get_task, list_tasks, register_task

__all__ = [
    "TaskSpec",
    "create_task",
    "get_task",
    "list_tasks",
    "register_task",
]
