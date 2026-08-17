import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from src.agents.lever import LeverAgent
from src.llm.providers import OpenAIProvider
from src.models.agents import JobDetails


class LLMTests(unittest.TestCase):
    def test_openai_provider_sends_structured_schema_without_logging_key(self):
        completion = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"title":"Engineer"}'))]
        )
        client = Mock()
        client.chat.completions.create.return_value = completion

        with patch("src.llm.providers.OpenAI", return_value=client) as openai:
            provider = OpenAIProvider(api_key="secret-key", model="test-model")
            result = provider.generate(
                system_prompt="system",
                user_prompt="user",
                schema=JobDetails.model_json_schema(),
                schema_name="jobdetails",
            )

        self.assertEqual(json.loads(result)["title"], "Engineer")
        openai.assert_called_once_with(api_key="secret-key")
        request = client.chat.completions.create.call_args.kwargs
        self.assertEqual(request["model"], "test-model")
        self.assertEqual(request["response_format"]["type"], "json_schema")
        self.assertEqual(request["response_format"]["json_schema"]["schema"], JobDetails.model_json_schema())


    def test_lever_agent_openai_wraps_search_array(self):
        search = {
            "site": "lever",
            "role_focus": "Backend Engineer",
            "filters": {},
            "query": "site:jobs.lever.co Backend Engineer",
            "google_search_url": "https://www.google.com/search?q=backend",
        }
        provider = Mock()
        provider.generate.return_value = json.dumps({"items": [search]})
        agent = LeverAgent.__new__(LeverAgent)
        agent._provider = provider
        agent._provider_name = "openai"

        result = agent.generate_google_searches(
            SimpleNamespace(resume="resume", preferences="preferences")
        )

        self.assertEqual(result[0].query, search["query"])
        self.assertEqual(provider.generate.call_args.kwargs["schema_name"], "searchqueries")


    def test_ollama_search_keeps_array_response_shape(self):
        search = {
            "site": "lever",
            "role_focus": "Backend Engineer",
            "filters": {},
            "query": "site:jobs.lever.co Backend Engineer",
            "google_search_url": "https://www.google.com/search?q=backend",
        }
        provider = Mock()
        provider.generate.return_value = json.dumps([search])
        agent = LeverAgent.__new__(LeverAgent)
        agent._provider = provider
        agent._provider_name = "ollama"

        result = agent.generate_google_searches(
            SimpleNamespace(resume="resume", preferences="preferences")
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(provider.generate.call_args.kwargs["schema_name"], "jobgooglesearchquery")
