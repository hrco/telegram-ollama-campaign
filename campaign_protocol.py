"""
Campaign Protocol v2.0

A structured, repeatable system for running high-quality content campaigns
using a local Ollama model.
"""

from typing import Literal
from pydantic import BaseModel

class CampaignPhase(BaseModel):
    name: str
    objective: str
    prompt_template: str

CAMPAIGN_PROTOCOL = {
    "research": CampaignPhase(
        name="Research & Positioning",
        objective="Understand audience, tone, and key messages",
        prompt_template="""You are a world-class campaign strategist.
Research the topic deeply. Define:
- Core message
- Target audience
- Tone of voice
- 3-5 key angles

Topic: {topic}
Platform: {platform}
"""
    ),
    "content": CampaignPhase(
        name="Content Architecture",
        objective="Create high-signal content pieces",
        prompt_template="""Write 3-5 pieces of content following the positioning.
Make them sharp, original, and platform-native.

Topic: {topic}
Tone: {tone}
Length: {length}
"""
    ),
    "schedule": CampaignPhase(
        name="Distribution Schedule",
        objective="Plan optimal posting times and sequence",
        prompt_template="""Create a 7-14 day content calendar.
Include posting times, format, and hook for each post.

Topic: {topic}
Frequency: {frequency}
"""
    ),
    "social_copy": CampaignPhase(
        name="Social Copy Pack",
        objective="Generate ready-to-post Telegram message variants",
        prompt_template="""Based on campaign research and content, create 5 ready-to-post Telegram messages.

Each message must have:
- A sharp hook (first line, max 10 words)
- Body (2-4 lines, plain language, no corporate speak)
- Clear call to action (last line)

Vary the angle for each. Keep each under 280 words. Format with --- between messages.

**Important rules:**
- Do NOT invent statistics, user counts, testimonials, or social proof.
- Only use facts that are verifiably true about the product.
- If you don't have real data, don't mention numbers or "thousands of users".

Topic: {topic}
Tone: {tone}
""",
    ),
}

def get_phase_prompt(phase: str, **kwargs) -> str:
    if phase not in CAMPAIGN_PROTOCOL:
        raise ValueError(f"Unknown phase: {phase}")
    import re
    template = CAMPAIGN_PROTOCOL[phase].prompt_template
    keys = re.findall(r'\{(\w+)\}', template)
    filled = {k: kwargs.get(k, f"[{k}]") for k in keys}
    return template.format(**filled)