"""Domain enums and API schemas (Pydantic)."""
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Category(str, Enum):
    technical_issue = "technical_issue"
    billing = "billing"
    general_inquiry = "general_inquiry"


class Priority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"


class Status(str, Enum):
    open = "open"
    in_progress = "in_progress"
    resolved = "resolved"


class TicketCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=5, max_length=5000)
    auto_classify: bool = True
    category: Optional[Category] = None
    priority: Optional[Priority] = None

    @model_validator(mode="after")
    def manual_mode_needs_category(self):
        if not self.auto_classify and self.category is None:
            raise ValueError("category is required when automatic classification is disabled")
        return self


class TicketUpdate(BaseModel):
    category: Optional[Category] = None
    priority: Optional[Priority] = None
    status: Optional[Status] = None

    @model_validator(mode="after")
    def at_least_one_field(self):
        if self.category is None and self.priority is None and self.status is None:
            raise ValueError("provide at least one of: category, priority, status")
        return self


class TicketOut(BaseModel):
    id: int
    title: str
    description: str
    category: Category
    priority: Priority
    priority_reasoning: str
    status: Status
    category_source: str  # ai | rules | manual
    priority_source: str  # ai | rules | manual | default
    ai_category: Optional[Category] = None  # what the classifier originally suggested
    ai_priority: Optional[Priority] = None
    created_at: str
    updated_at: str
