import json
import os
from functools import cache

import google.auth
from google.cloud import secretmanager

CLAUDE_KEY_SECRET_ID = "CLAUDE_KEY"
CLAUDE_KEY_ENV = "CLAUDE_KEY"


class SecretError(RuntimeError):
    """El secreto no se pudo leer o no tiene el formato esperado."""


def _project_id() -> str:
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    if project_id:
        return project_id

    _, project_id = google.auth.default()
    if not project_id:
        raise SecretError("No se pudo determinar el proyecto de GCP")
    return project_id


def _access_secret(secret_id: str, version: str) -> bytes:
    name = f"projects/{_project_id()}/secrets/{secret_id}/versions/{version}"
    client = secretmanager.SecretManagerServiceClient()
    return client.access_secret_version(request={"name": name}).payload.data


@cache
def get_secret_json(secret_id: str, version: str = "latest") -> dict[str, object]:
    """Lee un secreto de Secret Manager cuyo contenido es un objeto JSON.

    El resultado se cachea por instancia: Secret Manager solo se consulta en la
    primera petición. Si la lectura falla no se cachea y se reintenta en la
    siguiente. Los mensajes de error nunca incluyen el contenido del secreto.
    """
    try:
        data = json.loads(_access_secret(secret_id, version).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise SecretError(f"El secreto {secret_id} no es un JSON valido") from None

    if not isinstance(data, dict):
        raise SecretError(f"El secreto {secret_id} debe ser un objeto JSON")
    return data


@cache
def get_secret_text(secret_id: str, version: str = "latest") -> str:
    """Lee un secreto de Secret Manager cuyo contenido es texto plano (p. ej. un PEM).

    Mismo cacheo que get_secret_json. Un secreto vacio es un error de configuracion.
    """
    try:
        value = _access_secret(secret_id, version).decode("utf-8")
    except UnicodeDecodeError:
        raise SecretError(f"El secreto {secret_id} no es texto UTF-8") from None
    if not value.strip():
        raise SecretError(f"El secreto {secret_id} esta vacio")
    return value


def get_claude_api_key() -> str:
    """API key de Anthropic para los agentes que usan el SDK de Claude directamente.

    En produccion se lee del secreto de texto plano `CLAUDE_KEY` de Secret Manager
    (la cuenta de servicio de Cloud Run necesita `roles/secretmanager.secretAccessor`
    sobre el). En local se puede inyectar con la variable de entorno CLAUDE_KEY para
    no depender de Secret Manager.
    """
    value = os.getenv(CLAUDE_KEY_ENV, "").strip()
    if value:
        return value
    return get_secret_text(CLAUDE_KEY_SECRET_ID).strip()
