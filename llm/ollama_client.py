import json
import logging
from urllib import error, request

try:
    import requests
except ImportError:
    requests = None


OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_TIMEOUT_SECONDS = 50


LOGGER = logging.getLogger(__name__)


def generate(prompt):

    payload = {
        "model": "phi3:mini",
        "prompt": prompt,
        "stream": False
    }

    if requests is not None:
        try:
            LOGGER.info("Sending prompt to Ollama at %s", OLLAMA_URL)
            response = requests.post(
                OLLAMA_URL,
                json=payload,
                timeout=OLLAMA_TIMEOUT_SECONDS
            )
            response.raise_for_status()
            return response.json()["response"]
        except requests.RequestException as exc:
            LOGGER.warning("Ollama request failed via requests: %s", exc)
            return '{"action":"unknown","resource":"","device":"local","parameters":{"message":"LLM unavailable."}}'

    try:
        LOGGER.info("Sending prompt to Ollama via urllib at %s", OLLAMA_URL)
        raw_request = request.Request(
            OLLAMA_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with request.urlopen(raw_request, timeout=OLLAMA_TIMEOUT_SECONDS) as response:
            body = json.loads(response.read().decode("utf-8"))
            return body["response"]
    except (error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as exc:
        LOGGER.warning("Ollama request failed via urllib: %s", exc)
        return '{"action":"unknown","resource":"","device":"local","parameters":{"message":"LLM unavailable."}}'
