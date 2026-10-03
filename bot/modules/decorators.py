from collections.abc import Callable
from typing import Any, TypeVar, cast

T = TypeVar("T")

def command_group(name: str) -> Callable[[T], T]:
    def decorator(cmd: T) -> T:
        # why does this feel like typescript
        cast("Any", cmd).command_group = name
        return cmd

    return decorator
