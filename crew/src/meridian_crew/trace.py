"""An event-bus tap that records which tools actually ran.

Asking the model to report the tools it used would be a self-report. Reading the
event bus is the objective version, which is what makes a test of "did the agent
really call goal_solver" worth anything.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

from crewai.events.event_bus import crewai_event_bus
from crewai.events.types.tool_usage_events import (
    ToolUsageErrorEvent,
    ToolUsageFinishedEvent,
    ToolUsageStartedEvent,
)

MAX_ECHO_CHARS = 700

# A tool call's `ref` ties its result back to the call that produced it, which is
# what lets a consumer render one row that fills in rather than two unrelated
# lines. CrewAI events do not carry such an id, so the trace assigns one.
Sink = Any  # Callable[[dict[str, Any]], None]


@dataclass
class ToolCall:
    name: str
    args: dict[str, Any] | str | None = None
    output: str | None = None
    error: str | None = None
    from_cache: bool = False
    ref: str = ""

    @property
    def ok(self) -> bool:
        return self.error is None


@dataclass
class ToolTrace:
    calls: list[ToolCall] = field(default_factory=list)

    @property
    def names(self) -> list[str]:
        return [call.name for call in self.calls]

    def called(self, name: str) -> bool:
        return name in self.names

    @property
    def errors(self) -> list[ToolCall]:
        return [call for call in self.calls if not call.ok]


def _shorten(value: Any) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    text = " ".join(text.split())
    if len(text) <= MAX_ECHO_CHARS:
        return text
    return f"{text[:MAX_ECHO_CHARS]}... [{len(text)} chars]"


@contextmanager
def tool_trace(echo: bool = False, sink: Sink = None) -> Iterator[ToolTrace]:
    """Collect tool calls for the duration of the block.

    `echo` prints each call as it happens, which is the difference between
    watching an agent work and staring at a blank terminal for 40 seconds.
    `sink` receives the same calls as plain dicts, for a consumer that wants to
    forward them somewhere -- the Express console, for instance.
    """
    trace = ToolTrace()
    counter = {"n": 0}

    def _pending(name: str, field: str) -> ToolCall | None:
        for call in reversed(trace.calls):
            if call.name == name and getattr(call, field) is None:
                return call
        return None

    def _emit(event: dict[str, Any]) -> None:
        if sink is not None:
            sink(event)

    with crewai_event_bus.scoped_handlers():

        @crewai_event_bus.on(ToolUsageStartedEvent)
        def _started(source: Any, event: ToolUsageStartedEvent) -> None:
            counter["n"] += 1
            ref = f"tool-{counter['n']}"
            trace.calls.append(
                ToolCall(name=event.tool_name, args=event.tool_args, ref=ref)
            )
            if echo:
                print(f"\n  -> {event.tool_name}({_shorten(event.tool_args)})", flush=True)
            _emit(
                {
                    "type": "tool_call",
                    "ref": ref,
                    "name": event.tool_name,
                    "args": _shorten(event.tool_args),
                }
            )

        @crewai_event_bus.on(ToolUsageFinishedEvent)
        def _finished(source: Any, event: ToolUsageFinishedEvent) -> None:
            call = _pending(event.tool_name, "output")
            summary = _shorten(event.output)
            if call is not None:
                call.output = summary
                call.from_cache = bool(event.from_cache)
            if echo:
                print(f"  <- {summary}", flush=True)
            _emit(
                {
                    "type": "tool_result",
                    "ref": call.ref if call else "",
                    "status": "ok",
                    "summary": summary,
                }
            )

        @crewai_event_bus.on(ToolUsageErrorEvent)
        def _errored(source: Any, event: ToolUsageErrorEvent) -> None:
            message = str(getattr(event, "error", "unknown error"))
            call = _pending(event.tool_name, "error")
            if call is not None:
                call.error = message
            else:
                counter["n"] += 1
                call = ToolCall(
                    name=event.tool_name, error=message, ref=f"tool-{counter['n']}"
                )
                trace.calls.append(call)
            if echo:
                print(f"  !! {event.tool_name} failed: {_shorten(message)}", flush=True)
            _emit(
                {
                    "type": "tool_result",
                    "ref": call.ref,
                    "status": "error",
                    "summary": _shorten(message),
                }
            )

        yield trace
