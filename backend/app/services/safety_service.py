"""
Medical-safety handling for the chatbot.

IMPORTANT, STATED PLAINLY: this is a keyword-and-rule layer, not a
medical triage system. It is intentionally conservative — it would
rather over-warn (tell someone to seek care when they didn't strictly
need to) than under-warn. It CANNOT reliably detect every emergency,
and passing its unit tests does NOT mean it is medically safe. It is a
guardrail around an educational tool, nothing more.

Three jobs:
  1. Detect language suggesting a medical emergency or high-risk
     symptom, and return an emergency message that is shown INSTEAD of
     any model answer (we never let the LLM freelance on these).
  2. Provide the standing medical disclaimer appended to normal answers.
  3. Give the provider a system instruction that constrains it to
     educational information only.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Phrases that should trigger an immediate "seek professional care"
# response, bypassing the model entirely. Deliberately broad. These are
# matched case-insensitively as whole-ish words/phrases.
_EMERGENCY_PATTERNS = [
    # systemic / infection signs
    r"\bfever\b", r"\bhigh temperature\b",
    r"\bspreading (fast|quickly|rapidly)\b", r"\brapidly (worsening|spreading)\b",
    r"\bpus\b", r"\boozing\b", r"\bred streaks?\b",
    r"\bswelling\b", r"\bswollen\b",
    r"\bcan('?t| not) breathe\b", r"\bdifficulty breathing\b", r"\btrouble breathing\b",
    r"\bthroat (closing|swelling|tight)\b",
    r"\bface (swelling|swollen)\b", r"\blips? (swelling|swollen)\b",
    r"\banaphylaxis\b", r"\ballergic reaction\b",
    # severe pain / systemic illness
    r"\bsevere pain\b", r"\bextreme pain\b", r"\bunbearable\b",
    r"\bdizzy\b", r"\bfainting\b", r"\bpassing out\b",
    # self-harm / crisis — route to human help, never the product
    r"\bsuicid", r"\bself[- ]?harm\b", r"\bkill myself\b", r"\bend my life\b",
    r"\bhurt myself\b",
]

_EMERGENCY_REGEX = re.compile("|".join(_EMERGENCY_PATTERNS), re.IGNORECASE)

# Self-harm / crisis is handled separately with a different, more
# careful message that points to human crisis support rather than a
# dermatologist.
_CRISIS_REGEX = re.compile(
    r"\bsuicid|\bself[- ]?harm\b|\bkill myself\b|\bend my life\b|\bhurt myself\b",
    re.IGNORECASE,
)

MEDICAL_DISCLAIMER = (
    "This is general educational information about skin care, not medical "
    "advice, diagnosis, or treatment. For a persistent, worsening, painful, "
    "or concerning skin problem, please see a qualified doctor or "
    "dermatologist."
)

EMERGENCY_MESSAGE = (
    "Some of what you described can be a sign of a problem that needs "
    "prompt medical attention — for example infection, a severe allergic "
    "reaction, or rapidly worsening symptoms. I can't assess this safely. "
    "Please contact a doctor now, or use your local emergency number / "
    "nearest emergency department if symptoms are severe or getting worse "
    "quickly (such as trouble breathing, facial or throat swelling, high "
    "fever, spreading redness, or severe pain). "
    + MEDICAL_DISCLAIMER
)

CRISIS_MESSAGE = (
    "It sounds like you may be going through something very difficult. I'm "
    "not able to help with this, but you deserve support from a real "
    "person right now. Please reach out to a local crisis or mental-health "
    "helpline, or contact a trusted person or a doctor. If you are in "
    "immediate danger, please use your local emergency number."
)

# The instruction handed to any LLM provider (mock or real) so its
# behavior is constrained the same way regardless of which one answers.
SYSTEM_INSTRUCTION = (
    "You are Kashvi, DermaCare AI's skincare companion: warm, clear and "
    "professional. Get straight to the point: no filler or small talk "
    "('Hey there!', 'I'm doing great', 'Great question!'), no emojis, and "
    "for a greeting just say hello briefly and ask what skin help they "
    "need. Pick your answer length by "
    "the question. DETAILED MODE: when the user asks for a skincare "
    "routine, for products, for ingredients or their composition / "
    "concentrations, or says 'in detail', 'explain fully' or similar, give "
    "a complete, well-organised answer: short bold section labels, numbered "
    "routine steps (morning and night when relevant), each product or "
    "ingredient with what it does, typical concentration, how to use it "
    "and cautions; a small table is fine for comparisons. CHAT MODE: for "
    "everything else, talk like a knowledgeable friend in a few short "
    "sentences (usually under 120 words), plain sentences, no tables or "
    "headings. In both modes don't add your own "
    "disclaimer paragraph - the app shows one - and, when it would help, "
    "end with one short follow-up question about the user's skin or goals. "
    "You are an educational skin-care information assistant. You provide "
    "general, non-diagnostic information about skin care only. You must "
    "NOT diagnose conditions, prescribe or recommend specific medications "
    "or doses, or claim to cure anything. Do not guarantee results. If a "
    "user describes severe, rapidly worsening, painful, infected, or "
    "otherwise concerning symptoms, tell them to seek professional medical "
    "care. Keep answers clear and avoid overstating certainty. Always make "
    "clear this is general information, not a substitute for a doctor. "
    "Reply in the same language the user wrote in — English, Hindi, or a "
    "Hindi-English mix (Hinglish) — rather than defaulting to English."
)


@dataclass
class SafetyVerdict:
    is_blocked: bool          # True -> return `message` INSTEAD of calling the LLM
    message: str | None       # the safe response to return, if blocked
    category: str | None      # "crisis" | "emergency" | None


def screen_user_message(text: str) -> SafetyVerdict:
    """Checked BEFORE the message ever reaches a provider. If it trips a
    rule, we return a fixed safe message and never call the LLM for this
    turn — the model doesn't get a chance to give unsafe guidance on a
    high-risk message."""
    if _CRISIS_REGEX.search(text):
        return SafetyVerdict(is_blocked=True, message=CRISIS_MESSAGE, category="crisis")
    if _EMERGENCY_REGEX.search(text):
        return SafetyVerdict(is_blocked=True, message=EMERGENCY_MESSAGE, category="emergency")
    return SafetyVerdict(is_blocked=False, message=None, category=None)


def append_disclaimer(answer: str) -> str:
    """Appended to every normal (non-blocked) assistant answer, so the
    educational-only framing is always present even if the model forgot
    it."""
    answer = answer.rstrip()
    if MEDICAL_DISCLAIMER.lower()[:40] in answer.lower():
        return answer  # don't double up if the model already included it
    return f"{answer}\n\n{MEDICAL_DISCLAIMER}"
