"""Pydantic v2: discriminated unions, model validators (requirement §15)."""

from typing import Annotated, Literal, Union

import pytest
from pydantic import BaseModel, Field, ValidationError, model_validator


class OptionA(BaseModel):
    kind: Literal["a"] = "a"
    count: int


class OptionB(BaseModel):
    kind: Literal["b"] = "b"
    label: str


class Payload(BaseModel):
    item: Annotated[Union[OptionA, OptionB], Field(discriminator="kind")]


def test_discriminated_union_parses_variants():
    p = Payload.model_validate({"item": {"kind": "a", "count": 3}})
    assert isinstance(p.item, OptionA)
    assert p.item.count == 3

    q = Payload.model_validate({"item": {"kind": "b", "label": "x"}})
    assert isinstance(q.item, OptionB)
    assert q.item.label == "x"


def test_discriminated_union_rejects_unknown_kind():
    with pytest.raises(ValidationError):
        Payload.model_validate({"item": {"kind": "unknown"}})


class BoundedRetryConfig(BaseModel):
    """Cross-field rule: retries must not exceed a ceiling (validator pattern)."""

    max_attempts: int = Field(ge=1, le=10)
    ceiling: int = Field(ge=1)

    @model_validator(mode="after")
    def attempts_lte_ceiling(self) -> "BoundedRetryConfig":
        if self.max_attempts > self.ceiling:
            raise ValueError("max_attempts cannot exceed ceiling")
        return self


def test_model_validator_cross_field_rule():
    m = BoundedRetryConfig(max_attempts=3, ceiling=5)
    assert m.max_attempts == 3

    with pytest.raises(ValidationError):
        BoundedRetryConfig(max_attempts=9, ceiling=5)
