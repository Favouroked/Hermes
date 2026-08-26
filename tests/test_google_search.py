import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.models.api import GoogleSearchRequest
from src.web import api


class SessionContext:
    def __init__(self, session):
        self.session = session

    def __enter__(self):
        return self.session

    def __exit__(self, *args):
        return False


class GoogleSearchTests(unittest.TestCase):
    def test_settings_returns_resume_and_preferences(self):
        installation = SimpleNamespace(
            installation_id="hermes-1", llm_provider="ollama", openai_key=None,
            auto_fill=False, resume="stored resume", preferences="stored preferences",
        )
        session = MagicMock()
        session.query.return_value.filter_by.return_value.one_or_none.return_value = installation
        with patch.object(api, "SessionLocal", return_value=SessionContext(session)):
            response = api.app.test_client().get("/api/settings?installation_id=hermes-1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["resume"], "stored resume")
        self.assertEqual(response.json["preferences"], "stored preferences")
        self.assertIsNone(response.json["llm_model"])

    def test_settings_updates_resume_and_preferences(self):
        installation = SimpleNamespace(
            installation_id="hermes-1", llm_provider="ollama", openai_key=None,
            auto_fill=False, resume="old resume", preferences="old preferences",
        )
        session = MagicMock()
        session.query.return_value.filter_by.return_value.one_or_none.return_value = installation
        with patch.object(api, "SessionLocal", return_value=SessionContext(session)):
            response = api.app.test_client().patch(
                "/api/settings",
                json={
                    "installation_id": "hermes-1",
                    "llm_provider": "openai",
                    "llm_model": "preferred-model",
                    "openai_key": "test-key",
                    "auto_fill": True,
                    "resume": "new resume",
                    "preferences": "new preferences",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(installation.resume, "new resume")
        self.assertEqual(installation.preferences, "new preferences")
        self.assertEqual(installation.llm_model, "preferred-model")
        self.assertTrue(installation.auto_fill)
        session.commit.assert_called_once()

    def test_request_defaults_to_reusing_searches(self):
        request = GoogleSearchRequest(installation_id="hermes-1", cutoff_date="2026-08-01")
        self.assertFalse(request.force_generate)

    def test_cutoff_url_replaces_previous_cutoff(self):
        url = "https://www.google.com/search?q=python+jobs+after%3A2026-01-01"
        updated = api._cutoff_url(url, "2026-08-15")
        self.assertIn("after%3A2026-08-15", updated)
        self.assertNotIn("2026-01-01", updated)

    def test_existing_searches_are_reused_newest_first(self):
        installation = SimpleNamespace(
            installation_id="hermes-1", resume="resume", preferences="preferences",
            llm_provider="ollama", openai_key=None,
        )
        newest = SimpleNamespace(
            google_search_url="https://www.google.com/search?q=newest",
            search_run_id="old", created_at=2,
        )
        oldest = SimpleNamespace(
            google_search_url="https://www.google.com/search?q=oldest+after%3A2026-01-01",
            search_run_id="old", created_at=1,
        )
        installation_session = MagicMock()
        installation_session.query.return_value.filter_by.return_value.one_or_none.return_value = installation
        query_session = MagicMock()
        query_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [newest, oldest]

        with patch.object(api, "SessionLocal", side_effect=[SessionContext(installation_session), SessionContext(query_session)]), \
             patch.object(api, "uuid4", return_value=SimpleNamespace(hex="run-1")) as uuid_mock, \
             patch.object(api, "Agent") as agent_mock:
            response = api.app.test_client().post(
                "/api/automaton/google-search",
                json={"installation_id": "hermes-1", "cutoff_date": "2026-08-15"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["search_run_id"], "run-1")
        self.assertEqual(response.json["urls"], [newest.google_search_url, oldest.google_search_url])
        self.assertIn("after%3A2026-08-15", oldest.google_search_url)
        self.assertNotIn("2026-01-01", oldest.google_search_url)
        uuid_mock.assert_called_once()
        agent_mock.assert_not_called()

    def test_force_generate_calls_agent_when_searches_exist(self):
        installation = SimpleNamespace(
            installation_id="hermes-1", resume="resume", preferences="preferences",
            llm_provider="ollama", openai_key=None,
        )
        generated = SimpleNamespace(
            site="lever", role_focus="Engineer", filters={}, query="engineer",
            google_search_url="https://www.google.com/search?q=engineer",
        )
        installation_session = MagicMock()
        installation_session.query.return_value.filter_by.return_value.one_or_none.return_value = installation
        query_session = MagicMock()
        query_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [SimpleNamespace()]
        insert_session = MagicMock()
        agent = MagicMock()
        agent.generate_google_searches.return_value = [generated]

        with patch.object(api, "SessionLocal", side_effect=[SessionContext(installation_session), SessionContext(query_session), SessionContext(insert_session)]), \
             patch.object(api, "uuid4", return_value=SimpleNamespace(hex="run-2")), \
             patch.object(api, "Agent", return_value=agent):
            response = api.app.test_client().post(
                "/api/automaton/google-search",
                json={"installation_id": "hermes-1", "cutoff_date": "2026-08-15", "force_generate": True},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json["urls"]), 1)
        agent.generate_google_searches.assert_called_once()
        insert_session.commit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
