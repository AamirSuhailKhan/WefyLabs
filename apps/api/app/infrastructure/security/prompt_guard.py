import re
from typing import Tuple

PROMPT_INJECTION_PATTERNS = [
    r"ignore (all )?previous instructions",
    r"disregard (all )?prior (prompts|instructions)",
    r"system prompt",
    r"you are now a",
    r"override your instructions",
    r"act as an unrestrained",
    r"jailbreak",
    r"DAN mode",
    r"developer mode",
]

def validate_prompt_injection(user_input: str) -> Tuple[bool, str]:
    """
    Analyzes incoming user message strings for prompt injection attempts,
    delimiter abuse, and system instruction overrides.
    Returns (is_safe: bool, sanitized_text: str).
    """
    if not user_input:
        return True, ""

    input_lower = user_input.lower()
    for pattern in PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, input_lower):
            clean_text = "[Filtered message containing prompt injection attack]"
            return False, clean_text

    # Strip dangerous control characters and markdown block escapes
    clean = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', user_input)
    clean = clean.replace("```", "").replace("system:", "").replace("assistant:", "").strip()
    return True, clean[:1000]
