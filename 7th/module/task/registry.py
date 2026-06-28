"""Small task registry used by the scheduler runtime.

The registry keeps scheduler command names stable while allowing task
implementations to live outside ``E7AutoScript`` methods.
"""

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional


@dataclass(frozen=True)
class TaskSpec:
    command: str
    method: str
    factory: Callable
    description: str = ""
    enabled_by_default: bool = False


_TASKS_BY_COMMAND: Dict[str, TaskSpec] = {}
_TASKS_BY_METHOD: Dict[str, TaskSpec] = {}


def _normalize_command(command: str) -> str:
    return str(command or "").strip().lower()


def _normalize_method(method: str) -> str:
    return str(method or "").strip().lower()


def register_task(spec: TaskSpec) -> TaskSpec:
    """Register a task spec under scheduler command and runtime method."""
    if not spec.command or not spec.method:
        raise ValueError("TaskSpec requires command and method")
    _TASKS_BY_COMMAND[_normalize_command(spec.command)] = spec
    _TASKS_BY_METHOD[_normalize_method(spec.method)] = spec
    return spec


def get_task(name: str) -> Optional[TaskSpec]:
    """Resolve a task by Scheduler.Command or snake_case method name."""
    return _TASKS_BY_COMMAND.get(_normalize_command(name)) or _TASKS_BY_METHOD.get(_normalize_method(name))


def list_tasks() -> List[TaskSpec]:
    """Return registered tasks in command-name order."""
    return sorted(_TASKS_BY_COMMAND.values(), key=lambda spec: spec.command.lower())


def create_task(name: str, **kwargs):
    """Create a registered task instance."""
    spec = get_task(name)
    if spec is None:
        raise KeyError(name)
    return spec.factory(**kwargs)


def _create_secret_shop_task(**kwargs):
    from tasks.secret_shop import SecretShopTask

    return SecretShopTask(**kwargs)


register_task(
    TaskSpec(
        command="SecretShop",
        method="secret_shop",
        factory=_create_secret_shop_task,
        description="Secret shop refresh and purchase automation",
        enabled_by_default=True,
    )
)
