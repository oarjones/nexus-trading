"""Tests para generación de prompts."""

import pytest
from src.agents.llm.interfaces import AutonomyLevel
from src.agents.llm.prompts import (
    get_system_prompt,
    get_prompt_token_estimate
)


def test_get_conservative_prompt():
    prompt = get_system_prompt(AutonomyLevel.CONSERVATIVE)
    assert "NIVEL DE AUTONOMÍA: CONSERVATIVE" in prompt
    assert "actions = [] siempre" in prompt
    assert "REGÍMENES DE MERCADO" in prompt  # Base prompt included


def test_get_moderate_prompt():
    prompt = get_system_prompt(AutonomyLevel.MODERATE)
    assert "NIVEL DE AUTONOMÍA: MODERATE" in prompt
    assert "size_suggestion" in prompt
    assert "REGÍMENES DE MERCADO" in prompt


def test_get_experimental_prompt():
    prompt = get_system_prompt(AutonomyLevel.EXPERIMENTAL)
    assert "NIVEL DE AUTONOMÍA: EXPERIMENTAL" in prompt
    assert "KILL SWITCH REMINDER" in prompt
    assert "REGÍMENES DE MERCADO" in prompt


def test_invalid_autonomy_level():
    with pytest.raises(ValueError):
        get_system_prompt("invalid_level")


def test_token_estimate():
    estimate = get_prompt_token_estimate(AutonomyLevel.MODERATE)
    assert estimate > 0
    assert isinstance(estimate, int)
