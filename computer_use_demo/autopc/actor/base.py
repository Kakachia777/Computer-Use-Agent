from enum import Enum

class APIProvider(Enum):
    ANTHROPIC = "anthropic"
    GPT4 = "gpt4"  # Added GPT-4 provider
    BEDROCK = "bedrock"

# Additional base classes or utilities can be added here if needed 