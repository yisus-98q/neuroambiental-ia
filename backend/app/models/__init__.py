"""Importa todos los modelos para que Alembic y SQLAlchemy los registren."""
from app.models.data import DataRecord, Document, Measurement, Sensor
from app.models.identity import AuditLog, Role, User, UserSession
from app.models.operations import (
    AIModel,
    Alert,
    AlertFollowup,
    Conversation,
    ConversationMessage,
    Event,
    Prediction,
    Report,
    Run,
)
from app.models.territory import Coordinate, Source, Territory

__all__ = [
    "AIModel", "Alert", "AlertFollowup", "AuditLog", "Conversation", "ConversationMessage",
    "Coordinate", "DataRecord", "Document", "Event", "Measurement", "Prediction", "Report",
    "Role", "Run", "Sensor", "Source", "Territory", "User", "UserSession",
]
