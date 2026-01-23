"""Configuration loader for Cody."""

import tomllib
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.toml")

DEFAULTS = {
    "model": "llama3.1:8b",
    "available_models": [
        "llama3.1:8b",
        "qwen2.5-coder:3b",
        "qwen2.5-coder:7b",
        "deepseek-r1:8b",
        "mistral:7b",
    ],
    "show_reasoning": True,
    "confirm_tools": {"write_file", "edit_file", "delete_file", "fetch_webpage", "web_search", "run_bash"},
    "file_size_limit": 10_000_000,
    "system_prompt": """You are an AI agent named Cody. You assist the user with general tasks, coding tasks, and have tools available for usage.

Use your knowledge for basic facts. Only search for current events, real-time data, or things you don't know. When you use web_search, it only returns titles and snippets - ALWAYS fetch_webpage immediately after searching. Do not run multiple searches in a row without fetching. If a fetch fails or returns under 200 chars, try another URL until you get useful content.

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

    # Override with config.toml if it exists
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "rb") as f:
            file_config = tomllib.load(f)

        for key, value in file_config.items():
            if key == "confirm_tools":
                _config[key] = set(value)
            else:
                _config[key] = value

    return _config


def _save_config(config):
    """Save config to config.toml with comments."""
    # Build confirm_tools array
    tools_list = ", ".join(f'"{t}"' for t in sorted(config["confirm_tools"]))

    # Build available_models array
    models_list = ", ".join(f'"{m}"' for m in config["available_models"])

    # Escape the system prompt for TOML multiline string
    system_prompt = config["system_prompt"]

    toml_content = f'''# Cody Configuration (Ollama)
# Edit this file to customize your setup. Changes take effect on restart.

# Model to use (must be pulled in Ollama: ollama pull <model>)
model = "{config["model"]}"

# Available models for switching (add any models you have pulled)
available_models = [{models_list}]

# Show model reasoning/thinking output (for models that support it)
show_reasoning = {str(config["show_reasoning"]).lower()}

# Maximum file size in bytes that can be read (default: 10MB)
file_size_limit = {config["file_size_limit"]}

# Tools that require user confirmation before running
confirm_tools = [{tools_list}]

# System prompt sent to the model
# Placeholders: {{cwd}}, {{platform}}, {{date}}
system_prompt = \'\'\'
{system_prompt}\'\'\'
'''

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write(toml_content)


def _init():
    """Initialize config."""
    return _load_config()


_cfg = _init()

MODEL = _cfg["model"]
AVAILABLE_MODELS = _cfg["available_models"]
SHOW_REASONING = _cfg["show_reasoning"]
CONFIRM_TOOLS = _cfg["confirm_tools"]
FILE_SIZE_LIMIT = _cfg["file_size_limit"]
SYSTEM_PROMPT_TEMPLATE = _cfg["system_prompt"]


def set_model(model_name: str) -> bool:
    """Switch to a different model at runtime. Returns True if successful."""
    global MODEL, _cfg
    if model_name not in AVAILABLE_MODELS:
        return False
    MODEL = model_name
    _cfg["model"] = model_name
    _save_config(_cfg)
    return True


def get_models() -> list[tuple[str, bool]]:
    """Return list of (model_name, is_current)."""
    return [(name, name == MODEL) for name in AVAILABLE_MODELS]
