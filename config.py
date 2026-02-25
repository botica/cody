"""Configuration loader for Cody."""

import tomllib
import os

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.toml")

DEFAULTS = {
    "api_key": "",
    "model": "google/gemini-3-flash-preview",
    "model_pricing": {
        "google/gemini-3-pro-preview": (2.00, 12.00),
        "google/gemini-3-flash-preview": (1.00, 3.00),
        "minimax/minimax-m2.1": (0.30, 1.20),
        "x-ai/grok-code-fast-1": (0.20, 1.50),
        "z-ai/glm-4.7": (0.40, 1.50),
        "deepseek/deepseek-r1": (0.70, 2.40),
        "openai/gpt-5.2": (1.75, 14.00),
        "moonshotai/kimi-k2.5": (0.45, 2.25),
        "anthropic/claude-opus-4.6": (5.00, 25.00),
        "anthropic/claude-sonnet-4.6": (3.00, 15.00),
    },
    "max_turn_cost": 0.66,
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
            if key == "model_pricing":
                _config[key] = {k: tuple(v) for k, v in value.items()}
            elif key == "confirm_tools":
                _config[key] = set(value)
            else:
                _config[key] = value

    return _config


def _save_config(config):
    """Save config to config.toml with comments."""
    # Build pricing lines
    pricing_lines = []
    for model, prices in config["model_pricing"].items():
        pricing_lines.append(f'"{model}" = [{prices[0]}, {prices[1]}]')

    # Build confirm_tools array
    tools_list = ", ".join(f'"{t}"' for t in sorted(config["confirm_tools"]))

    # Escape the system prompt for TOML multiline string
    system_prompt = config["system_prompt"]

    toml_content = f'''# Cody Configuration
# Edit this file to customize your setup. Changes take effect on restart.

# Your OpenRouter API key (get one at https://openrouter.ai/keys)
api_key = "{config["api_key"]}"

# Model to use (browse available models at https://openrouter.ai/models)
# Format: "provider/model-name"
model = "{config["model"]}"

# Maximum cost per turn in USD - prevents runaway API costs
max_turn_cost = {config["max_turn_cost"]}

# Show model reasoning/thinking output (for models that support it)
show_reasoning = {str(config["show_reasoning"]).lower()}

# Maximum file size in bytes that can be read (default: 10MB)
file_size_limit = {config["file_size_limit"]}

# Tools that require user confirmation before running
# Available: "write_file", "edit_file", "delete_file", "fetch_webpage", "web_search", "run_bash", "read_file", "list_directory"
confirm_tools = [{tools_list}]

# System prompt sent to the model
# Placeholders: {{cwd}}, {{platform}}, {{date}}
system_prompt = \'\'\'
{system_prompt}\'\'\'

# Model pricing for cost tracking
# Format: "provider/model-name" = [input_cost_per_million, output_cost_per_million]
# Find pricing at https://openrouter.ai/models
[model_pricing]
{chr(10).join(pricing_lines)}
'''

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write(toml_content)


def prompt_api_key():
    """Prompt user for API key and save config."""
    global _config
    print("no API key found.")
    print("get one at: https://openrouter.ai/keys\n")

    api_key = input("enter your OpenRouter API key: ").strip()
    if not api_key:
        return False

    _config = _load_config()
    _config["api_key"] = api_key
    _save_config(_config)
    print(f"saved to {CONFIG_PATH}\n")
    return True


def _validate_model_pricing(config):
    """Validate that the selected model has valid pricing configured."""
    model = config["model"]
    pricing = config["model_pricing"].get(model)

    if pricing is None:
        raise ValueError(
            f"model '{model}' not found in model_pricing.\n"
            f'add it to config.toml: "{model}" = [input_cost, output_cost]'
        )

    if len(pricing) != 2:
        raise ValueError(
            f"model '{model}' has invalid pricing: {pricing}\n"
            f"pricing must be [input_cost, output_cost] per million tokens."
        )

    if not all(isinstance(p, (int, float)) for p in pricing):
        raise ValueError(
            f"model '{model}' pricing values must be numbers, got: {pricing}"
        )


def _init():
    """Initialize config."""
    config = _load_config()
    _validate_model_pricing(config)
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


def set_model(model_name: str) -> bool:
    """Switch to a different model at runtime. Returns True if successful."""
    global MODEL, _cfg
    if model_name not in MODEL_PRICING:
        return False
    MODEL = model_name
    _cfg["model"] = model_name
    _save_config(_cfg)
    return True


def get_models() -> list[tuple[str, tuple[float, float], bool]]:
    """Return list of (model_name, (input_cost, output_cost), is_current)."""
    models = []
    for name, prices in MODEL_PRICING.items():
        # Skip invalid entries (must be tuple/list of 2 numbers)
        if not isinstance(prices, (tuple, list)) or len(prices) != 2:
            continue
        if not all(isinstance(p, (int, float)) for p in prices):
            continue
        models.append((name, prices, name == MODEL))
    return models
