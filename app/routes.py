import json
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import (
    FastAPI,
    Depends,
    HTTPException,
    Request,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (
    StreamingResponse,
    Response,
    RedirectResponse,
)
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from prometheus_client import (
    generate_latest,
    CONTENT_TYPE_LATEST,
)
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.database.db import (
    init_db,
    SessionLocal,
)
from app.database.seed import seed
from app.database.models import (
    Conversation,
    Approval,
)
from app.auth.security import (
    authenticate,
    create_token,
    current_user,
)
from app.security.validation import (
    validate_username,
    validate_message,
    sanitize_input,
)
from app.security.rate_limit import limiter
from app.agents.graph import run_agent
from app.mcp.client import call_tool_sync
from app.observability.logging import (
    configure_logging,
    logger,
)
from app.observability.audit import audit
from app.tools.tickets import (
    list_tickets,
    get_ticket,
    serialize,
)


# ---------------------------------------------------------
# Request models
# ---------------------------------------------------------

class ChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=1000,
    )

    # Conversation identifier.
    # The frontend can send this on subsequent messages.
    # If omitted, the backend creates a new conversation.
    thread_id: str | None = None


class ApprovalRequest(BaseModel):
    approve: bool


# ---------------------------------------------------------
# Application lifespan
# ---------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):

    configure_logging()

    init_db()

    seed()

    try:
        from app.rag.ingestion import ingest

        ingest()

    except Exception as e:
        logger.warning(
            "rag_ingestion_failed",
            error=str(e),
        )

    yield


# ---------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------
# Frontend
# ---------------------------------------------------------

FRONTEND_DIR = (
    Path(__file__).resolve().parent.parent
    / "frontend"
)

app.mount(
    "/ui",
    StaticFiles(
        directory=FRONTEND_DIR,
        html=True,
    ),
    name="frontend",
)


app.state.limiter = limiter


# ---------------------------------------------------------
# CORS
# ---------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        x.strip()
        for x in settings.cors_origins.split(",")
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# Root
# ---------------------------------------------------------

@app.get(
    "/",
    include_in_schema=False,
)
def root():
    return RedirectResponse("/ui/")


# ---------------------------------------------------------
# Rate limit handler
# ---------------------------------------------------------

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(
    request: Request,
    exc: RateLimitExceeded,
):
    return Response(
        "Rate limit exceeded",
        status_code=429,
    )


# ---------------------------------------------------------
# Request middleware
# ---------------------------------------------------------

@app.middleware("http")
async def request_middleware(
    request: Request,
    call_next,
):

    request_id = str(uuid.uuid4())

    try:

        response = await call_next(request)

        response.headers[
            "X-Request-ID"
        ] = request_id

        return response

    except Exception:

        logger.exception(
            "request_failed",
            request_id=request_id,
        )

        raise


# ---------------------------------------------------------
# Authentication
# ---------------------------------------------------------

@app.post("/auth/login")
def login(
    form: OAuth2PasswordRequestForm = Depends(),
):

    user = authenticate(
        form.username,
        form.password,
    )

    if not user:
        raise HTTPException(
            401,
            "Invalid credentials",
        )

    validate_username(user.username)

    return {
        "access_token": create_token(user),
        "token_type": "bearer",
        "role": user.role,
    }


# ---------------------------------------------------------
# Status
# ---------------------------------------------------------

@app.get("/status")
def status():

    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.environment,
        "llm_provider": settings.llm_provider,
    }


# ---------------------------------------------------------
# Health
# ---------------------------------------------------------

@app.get("/health")
def health():

    db = SessionLocal()

    try:

        from sqlalchemy import text

        db.execute(
            text("SELECT 1")
        )

        return {
            "status": "healthy",
            "database": "ok",
        }

    except Exception as exc:

        logger.error(
            "health_check_failed",
            error=str(exc),
        )

        raise HTTPException(
            status_code=503,
            detail="database unavailable",
        )

    finally:

        db.close()


# ---------------------------------------------------------
# Prometheus metrics
# ---------------------------------------------------------

@app.get("/metrics")
def metrics():

    return Response(
        generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


# ---------------------------------------------------------
# Build LangGraph thread ID
# ---------------------------------------------------------

def build_thread_id(
    username: str,
    requested_thread_id: str | None,
) -> tuple[str, str]:

    # If the frontend has not supplied a thread ID,
    # create a new conversation.
    public_thread_id = (
        requested_thread_id
        or str(uuid.uuid4())
    )

    # Bind the actual LangGraph checkpoint thread
    # to the authenticated user.
    #
    # Example:
    #
    # sandeep:abc-123
    #
    # This prevents two users from sharing the same
    # LangGraph checkpoint namespace.
    internal_thread_id = (
        f"{username}:{public_thread_id}"
    )

    return (
        public_thread_id,
        internal_thread_id,
    )


# ---------------------------------------------------------
# Chat
# ---------------------------------------------------------

@app.post("/chat")
@limiter.limit("10/minute")
async def chat(
    request: Request,
    chat_request: ChatRequest,
    user=Depends(current_user),
):

    validate_username(user.username)

    clean_message = sanitize_input(
        validate_message(
            chat_request.message,
            settings.max_message_length,
        )
    )

    # -----------------------------------------------------
    # Conversation / thread handling
    # -----------------------------------------------------

    public_thread_id, internal_thread_id = (
    build_thread_id(
        user.username,
        chat_request.thread_id,
    )
)

    logger.info(
    "THREAD_DEBUG",
    username=user.username,
    request_thread_id=chat_request.thread_id,
    public_thread_id=public_thread_id,
    internal_thread_id=internal_thread_id,
)

    # -----------------------------------------------------
    # Run LangGraph agent
    # -----------------------------------------------------

    result = run_agent(
        user.username,
        user.role,
        clean_message,
        internal_thread_id,
    )

    reply = result["response"]

    # -----------------------------------------------------
    # Persist application conversation history
    # -----------------------------------------------------

    db = SessionLocal()

    try:

        db.add(
            Conversation(
                username=user.username,
                role=user.role,
                message=clean_message,
                response=reply,
            )
        )

        db.commit()

    finally:

        db.close()

    # -----------------------------------------------------
    # Audit / logging
    # -----------------------------------------------------

    audit(
        user.id,
        "chat",
        "conversation",
        f"message_length={len(clean_message)}",
    )

    logger.info(
        "agent_response",
        username=user.username,
        thread_id=public_thread_id,
    )

    # -----------------------------------------------------
    # Response
    # -----------------------------------------------------

    return {
        "reply": reply,
        "thread_id": public_thread_id,
        "approval_id": result.get(
            "approval_id"
        ),
        "search_query": result.get(
            "search_query"
        ),
        "sources": [d.get("source", "") for d in result.get("documents", []) if d.get("source")],
        "agent": result.get("agent"),
        "handoff": result.get("handoff"),
    }


# ---------------------------------------------------------
# Chat streaming
# ---------------------------------------------------------

@app.post("/chat/stream")
@limiter.limit("10/minute")
async def chat_stream(
    request: Request,
    chat_request: ChatRequest,
    user=Depends(current_user),
):

    validate_username(user.username)

    clean_message = sanitize_input(
        validate_message(
            chat_request.message,
            settings.max_message_length,
        )
    )

    # -----------------------------------------------------
    # Conversation / thread handling
    # -----------------------------------------------------

    public_thread_id, internal_thread_id = (
        build_thread_id(
            user.username,
            chat_request.thread_id,
        )
    )

    # -----------------------------------------------------
    # Run agent
    # -----------------------------------------------------

    result = run_agent(
        user.username,
        user.role,
        clean_message,
        internal_thread_id,
    )

    reply = result["response"]

    # -----------------------------------------------------
    # Current implementation is simulated streaming.
    # -----------------------------------------------------

    def iterator():

        for word in reply.split():

            yield word + " "

    return StreamingResponse(
        iterator(),
        media_type="text/plain",
        headers={
            "X-Thread-ID": public_thread_id,
        },
    )


# ---------------------------------------------------------
# Tickets
# ---------------------------------------------------------

@app.get("/tickets")
def tickets(
    user=Depends(current_user),
):

    return [
        serialize(ticket)
        for ticket in list_tickets(
            user.username,
            user.role,
        )
    ]


@app.get("/tickets/{ticket_id}")
def ticket(
    ticket_id: int,
    user=Depends(current_user),
):

    ticket = get_ticket(
        ticket_id,
        user.username,
        user.role,
    )

    if ticket == "FORBIDDEN":

        raise HTTPException(
            403,
            "You are not allowed to access this ticket",
        )

    if not ticket:

        raise HTTPException(
            404,
            "Ticket not found",
        )

    return serialize(ticket)


# ---------------------------------------------------------
# Conversation history
# ---------------------------------------------------------

@app.get("/history")
def history(
    user=Depends(current_user),
):

    db = SessionLocal()

    try:

        rows = (
            db.query(Conversation)
            .filter_by(
                username=user.username
            )
            .order_by(
                Conversation.id.desc()
            )
            .limit(50)
            .all()
        )

        return [
            {
                "message": row.message,
                "response": row.response,
                "created_at": row.created_at,
            }
            for row in rows
        ]

    finally:

        db.close()


@app.delete("/history")
def clear_history(
    user=Depends(current_user),
):

    db = SessionLocal()

    try:

        db.query(Conversation).filter(
            Conversation.username
            == user.username
        ).delete()

        db.commit()

        audit(
            user.id,
            "delete_history",
            user.username,
        )

        return {
            "message": "Your history was cleared"
        }

    finally:

        db.close()


# ---------------------------------------------------------
# Approvals
# ---------------------------------------------------------

@app.get("/approvals")
def approvals(
    user=Depends(current_user),
):

    db = SessionLocal()

    try:

        query = (
            db.query(Approval)
            .filter(
                Approval.status == "pending"
            )
        )

        if user.role not in (
            "helpdesk",
            "admin",
        ):

            query = query.filter(
                Approval.username
                == user.username
            )

        return [
            {
                "id": approval.id,
                "username": approval.username,
                "action": approval.action,
                "payload": approval.payload,
                "status": approval.status,
            }
            for approval in query.order_by(
                Approval.id.desc()
            ).all()
        ]

    finally:

        db.close()


# ---------------------------------------------------------
# Resolve approval
# ---------------------------------------------------------

@app.post(
    "/approvals/{approval_id}"
)
def resolve_approval(
    approval_id: int,
    req: ApprovalRequest,
    user=Depends(current_user),
):

    db = SessionLocal()

    try:

        approval = db.get(
            Approval,
            approval_id,
        )

        if not approval:

            raise HTTPException(
                404,
                "Approval not found",
            )

        if (
            approval.username != user.username
            and user.role not in (
                "helpdesk",
                "admin",
            )
        ):

            raise HTTPException(
                403,
                "Not allowed",
            )

        if approval.status != "pending":

            return {
                "status": approval.status
            }

        # -------------------------------------------------
        # Reject
        # -------------------------------------------------

        if not req.approve:

            approval.status = "rejected"

            db.commit()

            audit(
                user.id,
                "approval_rejected",
                str(approval.id),
            )

            return {
                "status": "rejected"
            }

        # -------------------------------------------------
        # Approve
        # -------------------------------------------------

        payload = json.loads(
            approval.payload
        )

        title = "AI-created IT ticket"

        description = payload["message"]

        ticket = call_tool_sync(
            "create_ticket_for_user",
            {
                "username": approval.username,
                "role": user.role,
                "title": title,
                "description": description,
                "priority": "high",
                "idempotency_key": f"approval-{approval.id}",
            },
        )

        if not isinstance(ticket, dict) or ticket.get("error"):
            raise HTTPException(
                status_code=502,
                detail=f"MCP ticket creation failed: {ticket.get('error', 'invalid MCP response') if isinstance(ticket, dict) else 'invalid MCP response'}",
            )

        approval.status = "approved"

        db.commit()

        audit(
            user.id,
            "approval_approved",
            str(approval.id),
        )

        return {
            "status": "approved",
            "ticket": ticket,
        }

    finally:

        db.close()