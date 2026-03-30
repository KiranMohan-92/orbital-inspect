"""
Track Gemini API token usage and estimated costs per analysis.

Pricing estimates (Gemini Flash):
  - Input: $0.075 per 1M tokens
  - Output: $0.30 per 1M tokens
  - Image: $0.0025 per image
"""

import logging
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

# Approximate pricing for gemini-2.0-flash (per 1M tokens)
PRICING = {
    "gemini-2.0-flash": {"input": 0.075, "output": 0.30, "image": 0.0025},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30, "image": 0.0025},
    "gemini-1.5-pro": {"input": 3.50, "output": 10.50, "image": 0.00265},
}


@dataclass
class AnalysisCost:
    """Accumulated cost for a single analysis run."""
    analysis_id: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    image_count: int = 0
    model: str = "gemini-2.0-flash"
    agent_costs: dict = field(default_factory=dict)

    @property
    def estimated_cost_usd(self) -> float:
        pricing = PRICING.get(self.model, PRICING["gemini-2.0-flash"])
        input_cost = (self.prompt_tokens / 1_000_000) * pricing["input"]
        output_cost = (self.completion_tokens / 1_000_000) * pricing["output"]
        image_cost = self.image_count * pricing["image"]
        return round(input_cost + output_cost + image_cost, 6)

    def add_agent_usage(
        self,
        agent_name: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        images: int = 0,
    ):
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens
        self.image_count += images
        self.agent_costs[agent_name] = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "images": images,
        }
        log.info(
            "[CostTracker] %s: +%d input, +%d output tokens",
            agent_name, prompt_tokens, completion_tokens,
        )

    def summary(self) -> dict:
        return {
            "analysis_id": self.analysis_id,
            "total_prompt_tokens": self.prompt_tokens,
            "total_completion_tokens": self.completion_tokens,
            "total_images": self.image_count,
            "estimated_cost_usd": self.estimated_cost_usd,
            "model": self.model,
            "per_agent": self.agent_costs,
        }
