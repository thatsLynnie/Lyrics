import json
import os
import unicodedata
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


SYSTEM_PROMPT = """Eres el asistente musical de Lyrics. Ayudas a personas que enseñan,
componen o aprenden música con teoría, análisis conceptual, planeación y borradores
editables de evaluaciones, ejercicios e ideas musicales. Responde en español, con
claridad y rigor, adapta la explicación al nivel y propósito indicados, y pregunta
solo por los datos imprescindibles.

La integración actual solo permite conversación de texto. No puedes recibir ni ver
archivos, analizar imágenes o PDF con OMR, escuchar audio, validar automáticamente una
partitura, renderizar notación musical, reproducir audio, exportar archivos ni guardar
recursos educativos. No afirmes que realizaste esas acciones. Si te las solicitan,
explica brevemente esta limitación y ofrece ayuda textual que sí puedas proporcionar.
Presenta los ejercicios, evaluaciones e ideas de composición como borradores que la
persona usuaria debe revisar; no presentes resultados musicales no verificados como
certezas."""


PROVIDERS = {
    "openai": {
        "name": "OpenAI",
        "key_env": "OPENAI_API_KEY",
        "model_env": "OPENAI_MODEL",
        "default_model": "gpt-4o-mini",
    },
    "gemini": {
        "name": "Gemini",
        "key_env": "GEMINI_API_KEY",
        "model_env": "GEMINI_MODEL",
        "default_model": "gemini-3.8-flash",
    },
}

LOCAL_PROVIDER = {
    "id": "local",
    "name": "Asistente local",
    "configured": True,
    "model": "respaldo musical",
}


class AssistantServiceError(Exception):
    def __init__(self, message, status_code=502):
        super().__init__(message)
        self.status_code = status_code


def assistant_name():
    return os.environ.get("LYRICS_AI_ASSISTANT_NAME", "Asistente musical").strip()[:60] or "Asistente musical"


def provider_settings(provider):
    if provider == "local":
        return LOCAL_PROVIDER.copy()
    settings = PROVIDERS.get(provider)
    if not settings:
        raise AssistantServiceError("El proveedor de IA seleccionado no es válido.", status_code=400)
    return {
        "id": provider,
        "name": settings["name"],
        "configured": bool(os.environ.get(settings["key_env"], "").strip()),
        "model": os.environ.get(settings["model_env"], settings["default_model"]).strip(),
    }


def available_providers():
    providers = []
    for provider in PROVIDERS:
        settings = provider_settings(provider)
        if settings["configured"]:
            providers.append(settings)
    providers.append(LOCAL_PROVIDER.copy())
    return providers


def is_configured(provider=None):
    if provider is not None:
        return provider_settings(provider)["configured"]
    return bool(available_providers())


def daily_limit():
    raw_limit = os.environ.get("LYRICS_AI_DAILY_LIMIT", "40").strip()
    try:
        limit = int(raw_limit)
    except ValueError as error:
        raise AssistantServiceError("LYRICS_AI_DAILY_LIMIT debe ser un número entero.", status_code=503) from error
    if not 1 <= limit <= 500:
        raise AssistantServiceError("LYRICS_AI_DAILY_LIMIT debe estar entre 1 y 500.", status_code=503)
    return limit


def generate_reply(history, provider="openai"):
    if provider == "local":
        return generate_local_reply(history)
    settings = provider_settings(provider)
    api_key = os.environ.get(PROVIDERS[provider]["key_env"], "").strip()
    if not api_key:
        raise AssistantServiceError(
            f"{settings['name']} no está configurado. Añade {PROVIDERS[provider]['key_env']} al archivo .env del servidor.",
            status_code=503,
        )

    model = settings["model"]
    if not model:
        raise AssistantServiceError(f"{PROVIDERS[provider]['model_env']} no puede estar vacío.", status_code=503)

    if provider == "openai":
        body = json.dumps({
            "model": model,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}, *history],
            "max_tokens": 1200,
            "temperature": 0.4,
        }).encode("utf-8")
        request = Request(
            "https://api.openai.com/v1/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
    else:
        contents = [
            {
                "role": "model" if message["role"] == "assistant" else "user",
                "parts": [{"text": message["content"]}],
            }
            for message in history
        ]
        body = json.dumps({
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": contents,
            "generationConfig": {"maxOutputTokens": 1200, "temperature": 0.4},
        }).encode("utf-8")
        request = Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/{quote(model, safe='')}:generateContent",
            data=body,
            headers={
                "x-goog-api-key": api_key,
                "Content-Type": "application/json",
            },
            method="POST",
        )

    try:
        with urlopen(request, timeout=35) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        try:
            error_data = json.loads(error.read().decode("utf-8")).get("error", {})
            detail = error_data.get("message", "")
            error_code = error_data.get("code", "")
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
            detail = ""
            error_code = ""
        finally:
            error.close()
        if error.code == 429:
            message = f"{settings['name']} alcanzó un límite de uso o cuota. Revisa el plan y los límites de tu cuenta, o cambia de proveedor."
            if provider == "openai" and error_code in {"insufficient_quota", "billing_hard_limit_reached"}:
                message = "La cuota o el saldo de la API de OpenAI se agotó. Revisa la facturación de OpenAI o cambia de proveedor."
            raise AssistantServiceError(message) from error
        message = f"{settings['name']} respondió con un error ({error.code})."
        if detail:
            message = f"{message} {detail[:300]}"
        raise AssistantServiceError(message) from error
    except (TimeoutError, URLError, HTTPException, OSError) as error:
        raise AssistantServiceError(f"No se pudo conectar con {settings['name']}. Comprueba la conexión e inténtalo de nuevo.") from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise AssistantServiceError(f"{settings['name']} devolvió una respuesta que no se pudo interpretar.") from error

    try:
        if provider == "openai":
            content = data["choices"][0]["message"]["content"]
        else:
            content = "".join(
                part.get("text", "")
                for part in data["candidates"][0]["content"]["parts"]
                if isinstance(part.get("text"), str)
            )
    except (KeyError, IndexError, TypeError) as error:
        raise AssistantServiceError(f"{settings['name']} no devolvió una respuesta utilizable.") from error
    if not isinstance(content, str) or not content.strip():
        raise AssistantServiceError(f"{settings['name']} devolvió una respuesta vacía.")
    return content.strip()


def generate_local_reply(history):
    prompt = next(
        (message.get("content", "") for message in reversed(history) if message.get("role") == "user"),
        "",
    )
    normalized = unicodedata.normalize("NFD", prompt)
    normalized = "".join(char for char in normalized if unicodedata.category(char) != "Mn").lower()

    if any(word in normalized for word in ("escala", "tonalidad", "tono y semitono")):
        answer = (
            "La escala mayor sigue este patrón de intervalos: tono, tono, semitono, tono, tono, tono, "
            "semitono. En Do mayor las notas son Do, Re, Mi, Fa, Sol, La, Si y Do. "
            "Prueba cantarla despacio y escucha cómo el semitono entre Mi-Fa y Si-Do crea sensación de llegada."
        )
    elif any(word in normalized for word in ("acorde", "triada", "armonia", "armonía")):
        answer = (
            "Una tríada se forma apilando la primera, tercera y quinta nota de una escala. "
            "En Do mayor, Do-Mi-Sol forma Do mayor; Do-Mi bemol-Sol forma Do menor. "
            "Para practicar, toca cada nota por separado y luego las tres juntas."
        )
    elif any(word in normalized for word in ("compas", "ritmo", "pulso", "dictado")):
        answer = (
            "Prueba este ejercicio en 4/4 a un pulso cómodo: cuenta «1, 2, 3, 4», da una palmada "
            "en cada número y acentúa suavemente el 1 y el 3. Después mantén las palmadas en 1, 2, 3, 4 "
            "y di «ta-ta-ti-ti» en los pulsos 3 y 4. Repite sin acelerar."
        )
    elif any(word in normalized for word in ("compos", "cancion", "melodia", "progresion")):
        answer = (
            "Idea de composición para explorar en Do mayor: usa la progresión "
            "| Do | La menor | Fa | Sol |, un compás por acorde en 4/4. "
            "Crea un motivo corto de tres o cuatro notas, repítelo y cambia solo su nota final "
            "sobre el último acorde. Puedes probar un tempo lento y revisarlo a tu gusto."
        )
    else:
        answer = (
            "Puedo ofrecer ayuda musical básica sin conexión: explica una escala, un acorde o un ritmo, "
            "o propone un ejercicio y una idea de composición. Para obtener una respuesta más amplia, "
            "prueba de nuevo cuando OpenAI o Gemini estén disponibles."
        )

    return f"Respuesta del asistente local (sin IA generativa):\n\n{answer}"


def generate_reply_with_fallback(history, provider="openai"):
    provider_settings(provider)
    if provider == "local":
        return generate_local_reply(history), "local", (
            "Modo local: respuesta musical guiada, sin IA generativa."
        )

    errors = []
    candidates = [provider]
    candidates.extend(
        candidate for candidate in PROVIDERS
        if candidate not in candidates and provider_settings(candidate)["configured"]
    )
    for candidate in candidates:
        try:
            answer = generate_reply(history, provider=candidate)
            if candidate == provider:
                return answer, candidate, ""
            return answer, candidate, (
                f"{PROVIDERS[candidate]['name']} respondió como respaldo de "
                f"{PROVIDERS[provider]['name']}."
            )
        except AssistantServiceError as error:
            errors.append(f"{provider_settings(candidate)['name']}: {error}")

    answer = generate_local_reply(history)
    detail = " / ".join(errors)
    notice = "Los servicios de IA generativa no respondieron. Se usó el asistente local."
    if detail:
        notice = f"{notice} {detail}"
    return answer, "local", notice
