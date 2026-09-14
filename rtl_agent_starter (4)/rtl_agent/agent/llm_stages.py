"""
The actual two-stage LLM calls. Uses the Anthropic Python SDK -- swap the
client/model if you're using a different provider, the prompting structure
stays the same.

pip install anthropic
export ANTHROPIC_API_KEY=...
"""

from __future__ import annotations
import json
import re
from anthropic import Anthropic

from . import prompts

client = Anthropic()
MODEL = "claude-sonnet-4-6"


def _extract_json_array(text: str) -> list[dict]:
    """LLMs occasionally wrap JSON in prose or fences despite instructions.
    Pull out the first [...] block defensively rather than trusting raw
    text -- this alone prevents a surprising number of pipeline crashes."""
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON array found in Stage-1 response:\n{text[:500]}")
    return json.loads(match.group(0))


def _extract_verilog(text: str) -> str:
    """Strip markdown fences if the model added them anyway."""
    fenced = re.search(r"```(?:verilog)?\s*(.*?)```", text, re.DOTALL)
    return fenced.group(1).strip() if fenced else text.strip()


def stage1_diagnose(module_name: str, rtl_text: str, sta_summary: str,
                     cdc_findings: list[dict]) -> list[dict]:
    """RTL + timing + CDC findings -> list of bottleneck diagnoses.
    No code is generated here -- this call is pure analysis, which is what
    makes it possible to log and audit independently of any fix attempt."""
    user_msg = prompts.STAGE1_USER_TEMPLATE.format(
        module_name=module_name,
        rtl_text=rtl_text,
        sta_summary=sta_summary or "(no STA violations reported)",
        cdc_findings_json=json.dumps(cdc_findings, indent=2),
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=prompts.STAGE1_DIAGNOSTIC_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )
    text = "".join(block.text for block in response.content if block.type == "text")
    return _extract_json_array(text)


def stage2_refactor(module_name: str, rtl_text: str, diagnosis: dict) -> str:
    """RTL + ONE diagnosis entry -> refactored RTL. Called once per
    diagnosis entry, highest severity first, so each transformation is
    independently verifiable rather than batched into one unreviewable
    rewrite."""
    user_msg = prompts.STAGE2_USER_TEMPLATE.format(
        module_name=module_name,
        rtl_text=rtl_text,
        diagnosis_json=json.dumps(diagnosis, indent=2),
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        system=prompts.STAGE2_REFACTOR_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )
    text = "".join(block.text for block in response.content if block.type == "text")
    return _extract_verilog(text)


def self_heal_retry(module_name: str, broken_rtl: str, error_log: str) -> str:
    """Feed the exact failure back and ask for a fix. This is the whole
    self-healing loop -- it's one extra LLM call, not a separate system."""
    user_msg = (
        f"MODULE: {module_name}\n\nCURRENT (BROKEN) SOURCE:\n```verilog\n{broken_rtl}\n```\n\n"
        + prompts.SELF_HEAL_TEMPLATE.format(error_log=error_log)
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        system=prompts.STAGE2_REFACTOR_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )
    text = "".join(block.text for block in response.content if block.type == "text")
    return _extract_verilog(text)
