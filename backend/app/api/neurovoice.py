from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.security import get_current_user
from app.database.session import get_db
from app.models import Conversation, ConversationMessage, User
from app.modules.neurovoice.contracts import available_providers
from app.modules.neurovoice.service import build_reply
from app.neurocore.registry import registry
from app.schemas import ChatIn, ChatOut

router = APIRouter(prefix="/api/neurovoice", tags=["NEUROVOICE IA"])


def _own(db: Session, conv_id: str, user: User) -> Conversation:
    conv = db.scalar(select(Conversation).options(selectinload(Conversation.messages))
                     .where(Conversation.id == conv_id))
    if conv is None or conv.user_id != user.id:
        raise HTTPException(404, "Conversación no encontrada.")
    return conv


@router.post("/chat", response_model=ChatOut)
def chat(body: ChatIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ChatOut:
    if body.conversation_id:
        conv = _own(db, body.conversation_id, user)
    else:
        conv = Conversation(user_id=user.id, title=body.message[:80])
        db.add(conv)
        db.flush()
    # Memoria de sesión: el módulo de la última respuesta permite preguntas de seguimiento («explícame más»).
    last = next((m.meta.get("module_key") for m in reversed(conv.messages or [])
                 if m.role == "asistente" and m.meta), None) if body.conversation_id else None
    if not last and body.context_module and registry.get(body.context_module):
        last = body.context_module   # contexto de la pantalla actual (p. ej. «explícame esto» en NEURODISASTER)
    reply, it = build_reply(db, body.message, registry, last_module=last)
    db.add(ConversationMessage(conversation_id=conv.id, role="usuario", content=body.message))
    db.add(ConversationMessage(conversation_id=conv.id, role="asistente", content=reply,
                               meta={"intent": it.intent, "module_key": it.module_key,
                                     "matched_keywords": it.matched_keywords, "method": it.method}))
    db.commit()
    return ChatOut(conversation_id=conv.id, reply=reply, intent=it.intent, module_key=it.module_key,
                   method=it.method)


@router.get("/capabilities")
def capabilities() -> dict:
    """Qué etapas de voz existen realmente (ASR, TTS, idiomas, herramientas)."""
    return available_providers()


@router.get("/conversations")
def conversations(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(Conversation).where(Conversation.user_id == user.id)
                      .order_by(Conversation.created_at.desc()).limit(50))
    return [{"id": c.id, "title": c.title, "created_at": c.created_at} for c in rows]


@router.get("/conversations/{conv_id}")
def conversation(conv_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    conv = _own(db, conv_id, user)
    return {"id": conv.id, "title": conv.title, "messages": [
        {"role": m.role, "content": m.content, "created_at": m.created_at, "meta": m.meta} for m in conv.messages]}
