from sqlalchemy import inspect

from app.database.session import engine
from app.neurocore.base import ModuleDescriptor, cap
from app.neurocore.registry import ModuleRegistry, interpret, registry

EXPECTED_TABLES = {
    "users", "roles", "user_sessions", "territories", "coordinates", "sources", "data_records", "sensors",
    "measurements", "events", "alerts", "alert_followups", "ai_models", "runs", "predictions", "documents",
    "reports", "conversations", "conversation_messages", "audit_logs", "alembic_version",
}


def test_migrations_create_all_tables():
    assert EXPECTED_TABLES <= set(inspect(engine).get_table_names())


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["database"] == "ok"
    assert r.headers["x-content-type-options"] == "nosniff"


def test_eight_specialized_modules_plus_core_systems(client):
    keys = {m["key"] for m in client.get("/api/neurocore/modules").json()}
    assert {"environmental", "mining", "biodiversity", "terrain", "disasters", "construction", "alerts",
            "neurovoice", "neurodata", "neurotraining"} == keys


def test_status_is_honest():
    """Un módulo sin capacidades implementadas nunca aparece como operativo."""
    assert registry.get("environmental").status == "parcial"  # Fase 2: NDVI y cambios
    assert registry.get("mining").status == "en_desarrollo"
    assert registry.get("neurodata").status == "operativo"
    assert registry.get("alerts").status == "parcial"
    for m in registry.all():
        if not any(c.implemented for c in m.capabilities):
            assert m.status == "en_desarrollo"


def test_registry_rejects_unknown_dependency_and_duplicates():
    reg = ModuleRegistry()
    a = ModuleDescriptor(key="a", name="A", version="1", description="", capabilities=[cap("x", "x")])
    b = ModuleDescriptor(key="b", name="B", version="1", description="", capabilities=[], dependencies=["c"])
    reg.register(a)
    try:
        reg.register(b)
        raise AssertionError("debía fallar")
    except ValueError:
        pass
    try:
        reg.register(a)
        raise AssertionError("debía fallar")
    except ValueError:
        pass


def test_interpreter_routes_spanish_with_accents():
    assert interpret("¿Cuántas alertas hay?").module_key == "alerts"
    assert interpret("¿Cuántas alertas hay?").intent == "consulta_conteo"
    assert interpret("riesgo de huaycos en la quebrada").module_key == "disasters"
    assert interpret("deforestación del bosque").module_key == "environmental"
    assert interpret("estado de los módulos").intent == "estado_modulos"
    assert interpret("xyz qwerty").intent == "desconocida"


def test_module_detail_404(client):
    assert client.get("/api/neurocore/modules/no-existe").status_code == 404
