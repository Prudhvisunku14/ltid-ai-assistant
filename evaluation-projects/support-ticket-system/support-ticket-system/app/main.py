"""FastAPI application: REST API + static dashboard."""
import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .classifier import Classifier, RuleBasedClassifier, build_classifier
from .config import Settings
from .db import TicketRepository
from .models import Category, Priority, Status, TicketCreate, TicketOut, TicketUpdate

log = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).parent / "static"


def create_app(settings: Optional[Settings] = None, classifier: Optional[Classifier] = None) -> FastAPI:
    settings = settings or Settings.from_env()
    repo = TicketRepository(settings.database_path)
    classifier = classifier or build_classifier(settings)

    app = FastAPI(title="AI Support Ticket System", version="1.0.0")
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/config")
    def get_config():
        return {"auto_classify_enabled": settings.auto_classify_enabled, "classifier": classifier.name}

    @app.post("/api/tickets", response_model=TicketOut, status_code=201)
    def create_ticket(payload: TicketCreate):
        auto = payload.auto_classify and settings.auto_classify_enabled
        if not auto and payload.category is None:
            raise HTTPException(422, "Automatic classification is disabled; please choose a category.")

        record = {
            "title": payload.title,
            "description": payload.description,
            "category": payload.category.value if payload.category else None,
            "priority": payload.priority.value if payload.priority else None,
            "category_source": "manual",
            "priority_source": "manual",
            "priority_reasoning": "Priority entered manually." if payload.priority else "",
        }

        # Ask the LLM only for what the user did not provide themselves.
        if auto and (payload.category is None or payload.priority is None):
            try:
                result = classifier.classify(payload.title, payload.description)
            except Exception:  # a classifier must never block ticket submission
                log.exception("classifier raised; using rule-based fallback")
                result = RuleBasedClassifier().classify(payload.title, payload.description)
            record["ai_category"] = result.category.value
            record["ai_priority"] = result.priority.value
            if payload.category is None:
                record["category"] = result.category.value
                record["category_source"] = result.source
            if payload.priority is None:
                record["priority"] = result.priority.value
                record["priority_source"] = result.source
                record["priority_reasoning"] = result.reasoning

        if record["priority"] is None:  # classification off and no priority given
            record["priority"] = Priority.medium.value
            record["priority_source"] = "default"
            record["priority_reasoning"] = "No automatic priority; defaulted to medium. Adjust if needed."

        return repo.create(record)

    @app.get("/api/tickets", response_model=list[TicketOut])
    def list_tickets(status: Optional[Status] = None, category: Optional[Category] = None,
                     priority: Optional[Priority] = None):
        return repo.list(status, category, priority)

    @app.get("/api/tickets/{ticket_id}", response_model=TicketOut)
    def get_ticket(ticket_id: int):
        ticket = repo.get(ticket_id)
        if ticket is None:
            raise HTTPException(404, "Ticket not found")
        return ticket

    @app.patch("/api/tickets/{ticket_id}", response_model=TicketOut)
    def update_ticket(ticket_id: int, payload: TicketUpdate):
        changes = payload.model_dump(exclude_none=True, mode="json")
        if "category" in changes:
            changes["category_source"] = "manual"
        if "priority" in changes:
            changes["priority_source"] = "manual"
        ticket = repo.update(ticket_id, changes)
        if ticket is None:
            raise HTTPException(404, "Ticket not found")
        return ticket

    @app.get("/api/stats")
    def stats():
        return repo.stats()

    return app


app = create_app()
