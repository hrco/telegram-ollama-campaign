"""
Campaign Protocol v1.0

A structured, repeatable system for running high-quality content campaigns
using a local Ollama model.

Phases:
1. Research & Positioning
2. Content Architecture
3. Asset Generation
4. Distribution Schedule
5. Performance Review
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
}

def get_phase_prompt(phase: str, **kwargs) -> str:
    if phase not in CAMPAIGN_PROTOCOL:
        raise ValueError(f"Unknown phase: {phase}")
    template = CAMPAIGN_PROTOCOL[phase].prompt_template
    return template.format(**kwargs)