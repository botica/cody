"""Configuration loader for Cody."""

import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

DEFAULTS = {
    "api_key": "",
    "model": "google/gemini-3-pro-preview",
    "model_pricing": {
        "google/gemini-3-flash-preview": (0.50, 3.00),
        "minimax/minimax-m2.1": (0.30, 1.20),
        "x-ai/grok-code-fast-1": (0.20, 1.50),
        "z-ai/glm-4.7": (0.40, 1.50),
        "deepseek/deepseek-r1": (0.70, 2.40),
        "openai/gpt-5.2": (1.75, 14.00),
        "google/gemini-3-pro-preview": (2.00, 12.00),
    },
    "max_turn_cost": 0.50,
    "show_reasoning": True,
    "confirm_tools": {"write_file", "edit_file", "delete_file", "fetch_webpage", "web_search", "run_bash"},
    "file_size_limit": 10_000_000,
    "system_prompt": """You are an AI agent named Cody. You assist the user with general tasks, coding tasks, and have tools available for usage.

Use your knowledge for basic facts. Only search for current events, real-time data, or things you don't know. When you DO use web_search, it only returns titles and snippets - you MUST fetch_webpage on at least one result to get actual content.

Environment:
- Working directory: {cwd}
- Platform: {platform}
- Date: {date}""",
}

_config = None


def _load_config():
    """Load config, merging file settings over defaults."""
    global _config
    if _config is not None:
        return _config

    # Start with defaults
    _config = {k: v for k, v in DEFAULTS.items()}

    # Override with config.json if it exists
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            file_config = json.load(f)

        for key, value in file_config.items():
            if key == "model_pricing":
                _config[key] = {k: tuple(v) for k, v in value.items()}
            elif key == "confirm_tools":
                _config[key] = set(value)
            else:
                _config[key] = value

    return _config


def _save_config(config):
    """Save config to config.json."""
    # Convert sets/tuples for JSON serialization
    save_config = {}
    for key, value in config.items():
        if key == "model_pricing":
            save_config[key] = {k: list(v) for k, v in value.items()}
        elif key == "confirm_tools":
            save_config[key] = list(value)
        else:
            save_config[key] = value

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(save_config, f, indent=2)


def prompt_api_key():
    """Prompt user for API key and save config."""
    global _config
    print("No API key found.")
    print("Get one at: https://openrouter.ai/keys\n")

    api_key = input("Enter your OpenRouter API key: ").strip()
    if not api_key:
        return False

    _config = _load_config()
    _config["api_key"] = api_key
    _save_config(_config)
    print(f"Saved to {CONFIG_PATH}\n")
    return True


def _init():
    """Initialize config."""
    config = _load_config()
    return config


_cfg = _init()

API_KEY = _cfg["api_key"]
MODEL = _cfg["model"]
MODEL_PRICING = _cfg["model_pricing"]
MAX_TURN_COST = _cfg["max_turn_cost"]
SHOW_REASONING = _cfg["show_reasoning"]
CONFIRM_TOOLS = _cfg["confirm_tools"]
FILE_SIZE_LIMIT = _cfg["file_size_limit"]
SYSTEM_PROMPT_TEMPLATE = _cfg["system_prompt"]
