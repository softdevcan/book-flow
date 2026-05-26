"""Per-language prompt fragment registry.

Each `LangRules` entry holds the display name plus optional Stage 1 / Stage 2
rule blocks tuned for that target language. Missing entries fall through to
generic blocks — translation still works, just without language-specific
translationese guidance.

To add a language:
  1. Append a LangRules(...) entry below keyed by its ISO 639-1 code.
  2. Optionally add stage1_rules / stage2_rules tuned for the target language.
  3. Add the same code to SUPPORTED_TARGETS in app/schemas/language.py.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class LangRules:
    name: str
    stage1_rules: str | None = None
    stage2_rules: str | None = None


# ---- Turkish (TR) — extracted verbatim from the previous hardcoded prompt ----
# Preserves current EN->TR quality. Do not loosen unless you compare outputs.

TR_STAGE1_RULES = (
    "- Avoid \"AI Turkish\" (Translationese): Do not follow English sentence structures or "
    "passive voice traps (e.g., avoid overusing \"tarafından\", \"bunun hakkında\", "
    "\"sahip olmak\"). Break long English sentences into punchy, natural Turkish clauses "
    "where it improves readability."
)

TR_STAGE2_RULES = (
    "- Eliminate \"translationese\": remove overused passive voice, \"tarafından\", "
    "\"sahip olmak\", \"bunun hakkında\", and any calqued English sentence structures. "
    "Recast as idiomatic, flowing Turkish."
)

# ---- French (FR) ----------------------------------------------------------
FR_STAGE1_RULES = (
    "- Avoid Anglicisms and calques: do not transliterate English syntax. Prefer nominal "
    "phrasing where French naturally prefers it; avoid overuse of \"être en train de\" "
    "or literal possessives with \"avoir\". Match French sentence rhythm — French tolerates "
    "longer literary clauses than English, but avoid awkward chains of subordinates."
)

# ---- German (DE) ----------------------------------------------------------
DE_STAGE1_RULES = (
    "- Respect German clause order: verb-second (V2) in main clauses, verb-final in "
    "subordinate clauses. Do not preserve English SVO when German grammar demands otherwise. "
    "Avoid English-shaped participle chains; prefer relative clauses or full sentences."
)

# Generic fallbacks — used when a language has no tuned block.
GENERIC_STAGE1_RULES = (
    "- Avoid literal calques of source-language syntax. Translate idioms by their "
    "emotional/cultural equivalent in the target language, not word-for-word.\n"
    "- Match register and rhythm to scene context.\n"
    "- Preserve every clause, tense, and nuance — fidelity first; polish comes in Stage 2."
)

GENERIC_STAGE2_RULES = (
    "- Eliminate translationese typical of the target language: drop calqued source-language "
    "structures and recast as idiomatic literary prose.\n"
    "- Preserve meaning exactly — do not add, drop, or reinterpret content.\n"
    "- Dialogue must sound like a real native speaker of the target language."
)

LANG_RULES: dict[str, LangRules] = {
    "tr": LangRules(name="Turkish", stage1_rules=TR_STAGE1_RULES, stage2_rules=TR_STAGE2_RULES),
    "en": LangRules(name="English"),
    "fr": LangRules(name="French", stage1_rules=FR_STAGE1_RULES),
    "de": LangRules(name="German", stage1_rules=DE_STAGE1_RULES),
    "es": LangRules(name="Spanish"),
    "ru": LangRules(name="Russian"),
    "it": LangRules(name="Italian"),
    "pt": LangRules(name="Portuguese"),
}


def resolve_rules(code: str) -> LangRules:
    """Look up the LangRules for an ISO 639-1 code; unknown codes return a
    name-only entry so prompt formatting still works."""
    return LANG_RULES.get(code, LangRules(name=code.upper()))


def language_name(code: str) -> str:
    return resolve_rules(code).name


def stage1_rules_block(target_code: str) -> str:
    return resolve_rules(target_code).stage1_rules or GENERIC_STAGE1_RULES


def stage2_rules_block(target_code: str) -> str:
    return resolve_rules(target_code).stage2_rules or GENERIC_STAGE2_RULES
