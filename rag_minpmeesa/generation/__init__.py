"""Construction du contexte et restitution contrôlée (chapitres 3.5 et 3.6)."""
from .numeric import extract_numbers, NumberMention, audit_numbers, NumericAudit
from .context import build_context, ContextBlock
from .guardrails import faithfulness_report, FaithfulnessReport
from .answer import Answerer, Answer

__all__ = [
    "extract_numbers", "NumberMention", "audit_numbers", "NumericAudit",
    "build_context", "ContextBlock",
    "faithfulness_report", "FaithfulnessReport",
    "Answerer", "Answer",
]
