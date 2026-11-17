"""
AI Task Builder Assistant.
~~~~~~~~~~~~~~~~~~~~~~~~~~
Optionally uses an external model to refine generated trade scenarios and questions.
Uses built-in templates when no API key is configured.
"""

from __future__ import annotations

import logging
from typing import Optional
import httpx

from config import BotConfig
from task_builder import BaseTask, TradeDecisionTaskBuilder, Web3CustomTaskBuilder

logger = logging.getLogger("AIBuilder")


class AITaskSynthesizer:
    """Orchestrates task synthesis combining deterministic templates with AI refinement."""

    def __init__(self, config: BotConfig) -> None:
        self.config = config
        self.trade_builder = TradeDecisionTaskBuilder()
        self.web3_builder = Web3CustomTaskBuilder()

    def build_task(self, category: str = "trade", seed: Optional[str] = None) -> BaseTask:
        """Generate a task, optionally refined with the AI builder model."""
        # 1. Generate base template task
        if category == "web3":
            base_task = self.web3_builder.generate_task(seed=seed)
        else:
            base_task = self.trade_builder.generate_task(seed=seed)

        # 2. If AI Builder is disabled or has no key, return the combinatorial task immediately
        if not self.config.ai_builder_enabled or not self.config.ai_builder_api_key:
            return base_task

        # 3. Enhance with AI builder model
        try:
            enhanced_prompt = self._refine_with_ai(base_task.user_prompt)
            if enhanced_prompt and len(enhanced_prompt.strip()) > 50:
                base_task.user_prompt = enhanced_prompt.strip()
                logger.info("Task %s refined with %s (%s)", base_task.task_id, self.config.ai_builder_provider, self.config.ai_builder_model)
        except Exception as exc:
            logger.debug("AI builder refinement failed (%s); using base template task", exc)

        return base_task

    def _refine_with_ai(self, initial_prompt: str) -> Optional[str]:
        """Call AI provider to enhance the scenario narrative."""
        headers = {
            "Authorization": f"Bearer {self.config.ai_builder_api_key}",
            "Content-Type": "application/json",
        }
        system_instruction = (
            "You are a quantitative finance scenario architect. "
            "Review the provided trading scenario and questions. "
            "Refine the technical narrative with realistic order book dynamics while preserving "
            "the exact required JSON output schema."
        )
        payload = {
            "model": self.config.ai_builder_model,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": f"Refine this evaluation setup:\n\n{initial_prompt}"},
            ],
            "max_tokens": 400,
            "temperature": 0.7,
        }

        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                f"{self.config.ai_builder_endpoint}/chat/completions",
                json=payload,
                headers=headers,
            )
            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices", [])
                if choices and "message" in choices[0]:
                    return choices[0]["message"].get("content")
        return None
