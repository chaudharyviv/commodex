"""
COMMODEX — LLM Client Abstraction
Supports OpenAI (demo mode) and Anthropic Claude (paper/production).
Switched via config.TRADING_MODE — zero code changes needed.

Features:
- Single interface for both providers
- JSON response parsing with retry-and-repair
- Pydantic validation of all agent outputs
- Prompt version tracking
"""

import os
import json
import logging
import re
from typing import Optional, Type
from pydantic import BaseModel, ValidationError
from openai import OpenAI
from anthropic import Anthropic
from config import TRADING_MODE, ACTIVE_LLM, PROMPTS_DIR

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────
# PYDANTIC OUTPUT MODELS
# One model per agent — strict validation of LLM output
# ─────────────────────────────────────────────────────────────────

class MarketAnalysis(BaseModel):
    """Agent 1 output — Market Analyst."""
    market_regime:              str       # trending_up | trending_down | ranging | volatile
    trend_strength:             str       # strong | moderate | weak
    key_support_levels:         list[float]
    key_resistance_levels:      list[float]
    technical_summary:          str
    india_specific_factors:     str
    global_risk_factors:        str
    high_impact_events_next_24h: Optional[str] = None
    overall_sentiment:          str       # bullish | bearish | neutral | mixed
    sentiment_confidence:       int       # 0-100
    analyst_notes:              str


class SignalDecision(BaseModel):
    """Agent 2 output — Signal Generator."""
    action:                     str       # BUY | SELL | HOLD
    confidence:                 int       # 0-100
    primary_reason:             str
    supporting_factors:         list[str]
    contradicting_factors:      list[str]
    invalidation_condition:     str
    recommended_timeframe:      str       # intraday | positional_2d | positional_5d | swing
    signal_quality:             str       # A | B | C
    hold_reasoning:             Optional[str] = None


class RiskParameters(BaseModel):
    """Agent 3 output — Risk Assessor."""
    entry_price:                float
    entry_type:                 str       # market | limit
    stop_loss:                  float
    stop_loss_basis:            str       # ATR | support_level | percentage
    target_1:                   float
    target_2:                   float
    risk_reward_ratio:          float
    max_hold_duration:          str
    exit_conditions:            list[str]
    margin_required_approx:     float
    execution_notes:            str
    risk_approved:              bool
    risk_block_reason:          Optional[str] = None


# ─────────────────────────────────────────────────────────────────
# PROMPT LOADER
# ─────────────────────────────────────────────────────────────────

def load_prompt(agent_name: str, version: str = "1.0") -> str:
    """
    Load a versioned prompt from the prompts/ directory.
    Falls back to a minimal default if file not found.
    """
    prompt_file = PROMPTS_DIR / f"{agent_name}_v{version}.txt"
    try:
        return prompt_file.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        logger.warning(f"Prompt file not found: {prompt_file}")
        return f"You are a {agent_name} for MCX commodity trading. Respond only in JSON."


# ─────────────────────────────────────────────────────────────────
# LLM CLIENT
# ─────────────────────────────────────────────────────────────────

class LLMClient:
    """
    Unified LLM interface for OpenAI and Anthropic.
    Mode is set via config.TRADING_MODE — no code changes needed.

    Usage:
        client = LLMClient()
        result = client.call(
            system_prompt="...",
            user_prompt="...",
            output_model=MarketAnalysis,
        )
    """

    def __init__(self):
        self.provider = ACTIVE_LLM["provider"]
        self.model    = ACTIVE_LLM["model"]
        self.api_key  = ACTIVE_LLM["api_key"]

        if self.provider == "openai":
            self._client = OpenAI(api_key=self.api_key)
        elif self.provider == "anthropic":
            self._client = Anthropic(api_key=self.api_key)
        else:
            raise ValueError(f"Unknown LLM provider: {self.provider}")

        logger.info(
            f"LLMClient ready — provider={self.provider} "
            f"model={self.model} mode={TRADING_MODE}"
        )

    def call(
        self,
        system_prompt: str,
        user_prompt:   str,
        output_model:  Type[BaseModel],
        max_tokens:    int = 1500,
        temperature:   float = 0.2,
    ) -> BaseModel:
        """
        Call LLM and return validated Pydantic model.

        Retry-with-repair pattern:
        1. Call LLM → parse JSON → validate with Pydantic
        2. If parse/validation fails → send back to LLM to fix
        3. If second attempt fails → raise with clear error

        temperature=0.2 for consistent, deterministic outputs.
        """
        raw_response = self._call_llm(
            system_prompt, user_prompt, max_tokens, temperature
        )

        # First parse attempt
        try:
            return self._parse_and_validate(raw_response, output_model)
        except (json.JSONDecodeError, ValidationError) as e:
            logger.warning(
                f"First parse failed ({type(e).__name__}): {e}\n"
                f"Attempting repair..."
            )

        # Repair attempt — send malformed output back to LLM
        repair_prompt = f"""The following JSON is malformed or missing required fields.
Fix it to exactly match this Pydantic schema:

{output_model.model_json_schema()}

Malformed JSON:
{raw_response}

Return ONLY the corrected JSON. No explanation, no markdown."""

        repaired = self._call_llm(
            "You are a JSON repair assistant. Fix JSON to match the given schema exactly.",
            repair_prompt,
            max_tokens,
            0.0,   # zero temperature for repair
        )

        try:
            return self._parse_and_validate(repaired, output_model)
        except (json.JSONDecodeError, ValidationError) as e:
            logger.error(f"Repair attempt also failed: {e}")
            raise ValueError(
                f"LLM output could not be parsed after repair attempt.\n"
                f"Provider: {self.provider}\n"
                f"Error: {e}\n"
                f"Raw: {repaired[:500]}"
            )

    def _call_llm(
        self,
        system_prompt: str,
        user_prompt:   str,
        max_tokens:    int,
        temperature:   float,
    ) -> str:
        """Raw LLM call — returns string response."""
        try:
            if self.provider == "openai":
                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system",  "content": system_prompt},
                        {"role": "user",    "content": user_prompt},
                    ],
                    max_tokens=max_tokens,
                    temperature=temperature,
                    response_format={"type": "json_object"},
                )
                return response.choices[0].message.content

            elif self.provider == "anthropic":
                response = self._client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system_prompt,
                    messages=[
                        {"role": "user", "content": user_prompt}
                    ],
                )
                return response.content[0].text

        except Exception as e:
            logger.error(f"LLM call failed ({self.provider}): {e}")
            raise

    def _parse_and_validate(
        self,
        raw: str,
        output_model: Type[BaseModel],
    ) -> BaseModel:
        """
        Extract JSON from response and validate against Pydantic model.
        Handles common LLM formatting issues.
        """
        # Strip markdown fences if present
        clean = re.sub(r"```(?:json)?", "", raw).strip()
        clean = clean.strip("`").strip()

        # Find JSON object boundaries
        start = clean.find("{")
        end   = clean.rfind("}") + 1
        if start == -1 or end == 0:
            raise json.JSONDecodeError("No JSON object found", clean, 0)

        json_str = clean[start:end]
        data     = json.loads(json_str)
        return output_model.model_validate(data)