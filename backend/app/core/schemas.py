from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    user_id: str | None = None
    message: str = Field(min_length=1, max_length=4000)
    session_id: str | None = None
    task_type: str = "chat"
    user_constraints: dict = Field(default_factory=dict)
    priority: str = "normal"
    deadline: str | None = None
    attachments: list = Field(default_factory=list)

    def to_internal_request(self) -> "InternalRequest":
        return InternalRequest(
            request_id=str(uuid4()),
            session_id=self.session_id or str(uuid4()),
            trace_id=uuid4().hex,
            task_type=self.task_type,
            input_payload={"message": self.message, "user_id": self.user_id},
            user_constraints=self.user_constraints,
            priority=self.priority,
            deadline=self.deadline,
            attachments=self.attachments,
        )


class InternalRequest(BaseModel):
    request_id: str
    session_id: str
    trace_id: str
    task_type: str
    input_payload: dict
    user_constraints: dict
    priority: str
    deadline: str | None = None
    attachments: list = Field(default_factory=list)


class ToolCallRead(BaseModel):
    id: str
    tool_name: str
    tool_input: dict
    tool_output: dict
    created_at: datetime


class MessageRead(BaseModel):
    id: str
    role: str
    content: str
    created_at: datetime


class TranscriptEventRead(BaseModel):
    id: str
    seq: int
    kind: str
    payload: dict
    created_at: datetime


class RunRead(BaseModel):
    id: str
    request_id: str
    session_id: str
    trace_id: str
    task_type: str
    status: str
    created_at: datetime
    finished_at: datetime | None
    messages: list[MessageRead]
    tool_calls: list[ToolCallRead]
    transcript_events: list[TranscriptEventRead]


class HumanReviewItemRead(BaseModel):
    id: str
    run_id: str
    trigger_class: str
    status: str
    case_summary: str
    uncertainty: str | None
    attempted_actions: list
    resolved_at: datetime | None
    resolution: str | None
    resolver: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ReviewResolveRequest(BaseModel):
    status: str = "resolved"
    resolution: str
    resolver: str | None = None

