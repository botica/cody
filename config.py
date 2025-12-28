import os
from dataclasses import dataclass, field

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

MODEL = "minimax/minimax-m2.1"
# MODEL = "deepseek/deepseek-r1"

# Pricing per million tokens (input, output)
MODEL_PRICING = {
    "minimax/minimax-m2.1": (0.30, 1.20),
}

SYSTEM_PROMPT = """
You are an AI agent named Cody. You assist the user with general tasks, coding tasks, and have tools available for usage.
Use your tools efficiently to complete the task.
""".strip()


@dataclass
class Session:
    """Holds all mutable state for a conversation session."""
    cwd: str = field(default_factory=os.getcwd)
    token_usage: dict = field(default_factory=lambda: {"input": 0, "output": 0, "cost": 0.0})
    auto_confirm_turn: bool = False
    conversation: list = field(default_factory=list)

    def __post_init__(self):
        if not self.conversation:
            self.conversation = [{"role": "system", "content": SYSTEM_PROMPT}]

    def reset_turn(self):
        """Reset per-turn state."""
        self.auto_confirm_turn = False
