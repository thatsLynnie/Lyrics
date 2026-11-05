import io
import json
import os
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from ai_service import (
    AssistantServiceError,
    available_providers,
    generate_reply,
    generate_reply_with_fallback,
    is_configured,
)


class OpenAIServiceTests(unittest.TestCase):
    def test_sends_conversation_to_server_side_chat_completions(self):
        response_body = json.dumps({
            "choices": [{"message": {"content": "Respuesta pedagógica."}}],
        }).encode("utf-8")
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key", "OPENAI_MODEL": "test-model"}):
            with patch("ai_service.urlopen", return_value=io.BytesIO(response_body)) as open_url:
                reply = generate_reply([{"role": "user", "content": "Explícame el compás."}])

        self.assertEqual(reply, "Respuesta pedagógica.")
        request = open_url.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.openai.com/v1/chat/completions")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-key")
        payload = json.loads(request.data)
        self.assertEqual(payload["model"], "test-model")
        self.assertEqual(payload["messages"][-1]["content"], "Explícame el compás.")

    def test_missing_api_key_is_reported_without_requesting_openai(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            with patch("ai_service.urlopen") as open_url:
                with self.assertRaises(AssistantServiceError) as raised:
                    generate_reply([])

        self.assertEqual(raised.exception.status_code, 503)
        open_url.assert_not_called()

    def test_rate_limit_is_reported_clearly(self):
        body = b'{"error":{"message":"Rate limit reached."}}'
        error = HTTPError(
            "https://api.openai.com/v1/chat/completions",
            429,
            "Too Many Requests",
            {},
            io.BytesIO(body),
        )
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            with patch("ai_service.urlopen", side_effect=error):
                with self.assertRaises(AssistantServiceError) as raised:
                    generate_reply([])

        self.assertEqual(raised.exception.status_code, 502)
        self.assertIn("límite", str(raised.exception))

    def test_lists_only_configured_providers(self):
        with patch.dict(os.environ, {
            "OPENAI_API_KEY": "",
            "GEMINI_API_KEY": "gemini-test-key",
            "GEMINI_MODEL": "gemini-test-model",
        }):
            providers = available_providers()
            self.assertFalse(is_configured("openai"))
            self.assertTrue(is_configured("gemini"))

        self.assertEqual(providers, [{
            "id": "gemini",
            "name": "Gemini",
            "configured": True,
            "model": "gemini-test-model",
        }, {
            "id": "local",
            "name": "Asistente local",
            "configured": True,
            "model": "respaldo musical",
        }])

    def test_sends_conversation_to_gemini_generate_content(self):
        response_body = json.dumps({
            "candidates": [{
                "content": {"parts": [{"text": "Respuesta "}, {"text": "musical."}]},
            }],
        }).encode("utf-8")
        history = [
            {"role": "user", "content": "Explícame el compás."},
            {"role": "assistant", "content": "Es la organización rítmica."},
            {"role": "user", "content": "Dame un ejemplo."},
        ]
        with patch.dict(os.environ, {
            "GEMINI_API_KEY": "gemini-test-key",
            "GEMINI_MODEL": "gemini-test-model",
        }):
            with patch("ai_service.urlopen", return_value=io.BytesIO(response_body)) as open_url:
                reply = generate_reply(history, provider="gemini")

        self.assertEqual(reply, "Respuesta musical.")
        request = open_url.call_args.args[0]
        self.assertEqual(
            request.full_url,
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-test-model:generateContent",
        )
        self.assertEqual(request.get_header("X-goog-api-key"), "gemini-test-key")
        payload = json.loads(request.data)
        self.assertIn("systemInstruction", payload)
        self.assertEqual(
            [message["role"] for message in payload["contents"]],
            ["user", "model", "user"],
        )
        self.assertEqual(payload["contents"][-1]["parts"][0]["text"], "Dame un ejemplo.")

    def test_missing_gemini_api_key_is_reported_without_requesting_gemini(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            with patch("ai_service.urlopen") as open_url:
                with self.assertRaises(AssistantServiceError) as raised:
                    generate_reply([], provider="gemini")

        self.assertEqual(raised.exception.status_code, 503)
        self.assertIn("GEMINI_API_KEY", str(raised.exception))
        open_url.assert_not_called()

    def test_rejects_unknown_provider(self):
        with patch("ai_service.urlopen") as open_url:
            with self.assertRaises(AssistantServiceError) as raised:
                generate_reply([], provider="unknown")

        self.assertEqual(raised.exception.status_code, 400)
        open_url.assert_not_called()

    def test_local_assistant_answers_music_questions_without_api_keys(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "", "GEMINI_API_KEY": ""}):
            providers = available_providers()
            reply = generate_reply(
                [{"role": "user", "content": "Explícame una escala mayor."}],
                provider="local",
            )

        self.assertEqual([provider["id"] for provider in providers], ["local"])
        self.assertIn("Do, Re, Mi, Fa, Sol, La, Si", reply)
        self.assertIn("sin IA generativa", reply)

    def test_falls_back_to_other_configured_provider(self):
        with patch.dict(os.environ, {
            "OPENAI_API_KEY": "openai-test-key",
            "GEMINI_API_KEY": "gemini-test-key",
        }), patch(
            "ai_service.generate_reply",
            side_effect=[
                AssistantServiceError("OpenAI alcanzó su cuota."),
                "Respuesta de Gemini.",
            ],
        ) as generate:
            answer, provider, notice = generate_reply_with_fallback(
                [{"role": "user", "content": "Explica una escala."}],
                provider="openai",
            )

        self.assertEqual(answer, "Respuesta de Gemini.")
        self.assertEqual(provider, "gemini")
        self.assertIn("respondió como respaldo", notice)
        self.assertEqual(generate.call_count, 2)

    def test_uses_local_music_help_when_all_online_providers_fail(self):
        with patch.dict(os.environ, {
            "OPENAI_API_KEY": "openai-test-key",
            "GEMINI_API_KEY": "gemini-test-key",
        }), patch(
            "ai_service.generate_reply",
            side_effect=[
                AssistantServiceError("OpenAI alcanzó su cuota."),
                AssistantServiceError("Gemini está temporalmente ocupado."),
            ],
        ), patch(
            "ai_service.generate_local_reply",
            return_value="Respuesta local de ritmo (sin IA generativa).",
        ):
            answer, provider, notice = generate_reply_with_fallback(
                [{"role": "user", "content": "Dame un ejercicio de ritmo."}],
                provider="openai",
            )

        self.assertEqual(provider, "local")
        self.assertIn("Respuesta local de ritmo", answer)
        self.assertIn("sin IA generativa", answer)
        self.assertIn("OpenAI alcanzó su cuota", notice)
        self.assertIn("Gemini está temporalmente ocupado", notice)


if __name__ == "__main__":
    unittest.main()
