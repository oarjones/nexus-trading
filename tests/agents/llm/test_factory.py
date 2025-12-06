"""Tests para LLMAgentFactory."""

import pytest
import os
from unittest.mock import patch, MagicMock

from src.agents.llm.factory import LLMAgentFactory
from src.agents.llm.config import LLMAgentConfig
from src.agents.llm.agents.claude_agent import ClaudeAgent
from src.agents.llm.interfaces import AutonomyLevel


@pytest.fixture
def mock_env_key():
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test_key"}):
        yield


def test_create_claude_agent(mock_env_key):
    agent = LLMAgentFactory.create(
        provider="claude",
        model="claude-test",
        autonomy=AutonomyLevel.MODERATE
    )
    
    assert isinstance(agent, ClaudeAgent)
    assert agent._model == "claude-test"
    assert agent._default_autonomy == AutonomyLevel.MODERATE


def test_create_from_config_object(mock_env_key):
    config = LLMAgentConfig(
        active_provider="claude",
        autonomy_level="experimental",
        providers={
            "claude": {
                "model": "claude-config-test",
                "max_tokens": 1000
            }
        }
    )
    
    agent = LLMAgentFactory.create_from_config_object(config)
    
    assert isinstance(agent, ClaudeAgent)
    assert agent._model == "claude-config-test"
    assert agent._default_autonomy == AutonomyLevel.EXPERIMENTAL
    assert agent._max_tokens == 1000


def test_missing_api_key():
    # Asegurar que no hay key en env
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="No API key found"):
            LLMAgentFactory.create(provider="claude")


def test_unknown_provider():
    with pytest.raises(ValueError, match="Unknown provider"):
        LLMAgentFactory.create(provider="unknown")
