"""Minimal click.testing stub for CLI tests."""

from __future__ import annotations

import inspect
import io
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, get_args, get_origin


@dataclass
class Result:
    """Simple result object matching click.testing.Result."""

    exit_code: int
    output: str
    exception: Exception | None = None


class CliRunner:
    """Minimal CLI runner for invoking command callables."""

    def invoke(
        self,
        command: Any,
        args: Iterable[str] | None = None,
        input: str | None = None,
    ) -> Result:
        arg_list = list(args or [])
        stdin = io.StringIO(input or "")
        stdout = io.StringIO()

        exit_code = 0
        exc: Exception | None = None

        try:
            kwargs, positionals = self._parse_args(command, arg_list)
            with _patched_stdio(stdin, stdout):
                command(*positionals, **kwargs)
        except SystemExit as system_exit:
            exit_code = system_exit.code if isinstance(system_exit.code, int) else 1
            exc = system_exit
        except Exception as error:  # pragma: no cover - mirrors click behavior  # NOSONAR
            exit_code = 1
            exc = error

        return Result(exit_code=exit_code, output=stdout.getvalue(), exception=exc)

    def _parse_args(self, command: Any, args: list[str]) -> tuple[dict[str, Any], list[Any]]:
        signature = inspect.signature(command)
        parameters = signature.parameters
        kwargs, positionals = self._split_args(parameters, args)
        bound_positionals = self._bind_positionals(parameters, positionals, kwargs)

        return kwargs, bound_positionals

    def _split_args(
        self, parameters: Mapping[str, inspect.Parameter], args: list[str]
    ) -> tuple[dict[str, Any], list[str]]:
        kwargs: dict[str, Any] = {}
        positionals: list[str] = []

        idx = 0
        while idx < len(args):
            token = args[idx]
            if token.startswith("--"):
                idx = self._handle_long_option(parameters, args, idx, kwargs)
            elif token.startswith("-") and len(token) > 1:
                self._handle_short_option(token, kwargs)
            else:
                positionals.append(token)
            idx += 1

        return kwargs, positionals

    def _handle_long_option(
        self,
        parameters: Mapping[str, inspect.Parameter],
        args: list[str],
        idx: int,
        kwargs: dict[str, Any],
    ) -> int:
        token = args[idx]
        name = token[2:].replace("-", "_")
        value: Any = True
        if idx + 1 < len(args) and not args[idx + 1].startswith("-"):
            value = args[idx + 1]
            idx += 1
        kwargs[name] = self._coerce_value(parameters.get(name), value)
        return idx

    def _handle_short_option(self, token: str, kwargs: dict[str, Any]) -> None:
        name = token[1:].replace("-", "_")
        kwargs[name] = True

    def _bind_positionals(
        self,
        parameters: Mapping[str, inspect.Parameter],
        positionals: list[str],
        kwargs: dict[str, Any],
    ) -> list[Any]:
        bound_positionals: list[Any] = []
        remaining_positionals = list(positionals)
        for param in parameters.values():
            if param.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD):
                if param.name in kwargs:
                    continue
                if remaining_positionals:
                    value = remaining_positionals.pop(0)
                    bound_positionals.append(self._coerce_value(param, value))

        return bound_positionals

    @staticmethod
    def _coerce_value(param: inspect.Parameter | None, value: Any) -> Any:
        if param is None or param.annotation is inspect._empty:
            return value
        annotation = param.annotation
        if get_origin(annotation) is not None:
            annotation_args = get_args(annotation)
        else:
            annotation_args = (annotation,)
        if int in annotation_args and isinstance(value, str):
            return int(value)
        if float in annotation_args and isinstance(value, str):
            return float(value)
        return value


class _patched_stdio:
    def __init__(self, stdin: io.StringIO, stdout: io.StringIO) -> None:
        self._stdin = stdin
        self._stdout = stdout
        self._old_stdin = None
        self._old_stdout = None

    def __enter__(self) -> None:
        import sys

        self._old_stdin = sys.stdin
        self._old_stdout = sys.stdout
        sys.stdin = self._stdin
        sys.stdout = self._stdout

    def __exit__(self, exc_type, exc, tb) -> None:
        import sys

        sys.stdin = self._old_stdin
        sys.stdout = self._old_stdout


__all__ = ["CliRunner", "Result"]
