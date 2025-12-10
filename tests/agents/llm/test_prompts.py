"""Tests para generación de prompts."""

import pytest
from src.agents.llm.interfaces import AutonomyLevel
from src.agents.llm.prompts import (
    CONSERVATIVE_PROMPT,
    MODERATE_PROMPT
)


def test_conservative_prompt_content():
    """Verify conservative prompt content."""
    prompt = CONSERVATIVE_PROMPT
    assert "NIVEL DE AUTONOMÍA: CONSERVATIVE" in prompt
    assert "ANALISTA DE RIESGOS" in prompt
    
    # Check for keywords instead of exact phrases that might change
    assert "CONSERVATIVE" in prompt


def test_moderate_prompt_content():
    """Verify moderate prompt content."""
    prompt = MODERATE_PROMPT
    assert "NIVEL DE AUTONOMÍA: MODERATE" in prompt
    
    # Check for keywords
    assert "MODERATE" in prompt

