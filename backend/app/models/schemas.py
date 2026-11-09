from typing import Literal, Optional
from pydantic import BaseModel

DataKind = Literal["real", "imported", "mock", "pending"]

class ProjectCard(BaseModel):
    id: str
    name: str
    description: str
    stack: list[str]
    status: Literal["built", "pending", "demo"]
    data_kind: DataKind
    last_updated: Optional[str] = None
    thumbnail: Optional[str] = None
    preview_url: Optional[str] = None
    client: Optional[str] = None
    category: Optional[str] = None
    repo: Optional[str] = None
    build_status: Optional[str] = None
    test_status: Optional[str] = None
    synthetic: bool = False
    launch_label: Optional[str] = None
    import_note: Optional[str] = None

class FileNode(BaseModel):
    name: str
    path: str
    type: Literal["file", "dir"]
    category: Optional[str] = None
    change: Optional[Literal["added", "modified", "unchanged"]] = None
    children: list["FileNode"] = []

class FileContent(BaseModel):
    path: str
    language: str
    content: str
    original: Optional[str] = None
    binary: bool = False
    change: str

class DiffFile(BaseModel):
    path: str
    status: Literal["added", "modified", "deleted"]
    additions: int
    deletions: int
    diff: str
