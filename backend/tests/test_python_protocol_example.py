"""Structural typing with `Protocol` (modern Python §1; complements ABC-based `LLMClient`)."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class StatusPayload(Protocol):
    def as_health_dict(self) -> dict[str, str]: ...


class OkAdapter:
    def as_health_dict(self) -> dict[str, str]:
        return {"status": "ok"}


def test_protocol_accepts_structurally_compatible_impl():
    svc: StatusPayload = OkAdapter()
    assert svc.as_health_dict() == {"status": "ok"}
    assert isinstance(OkAdapter(), StatusPayload)
