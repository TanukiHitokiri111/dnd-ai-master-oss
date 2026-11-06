"""
Точка входа для базы знаний D&D 5e.
Импортировать: from app.knowledge import format_srd_for_prompt, format_character_for_prompt
"""
from app.knowledge.srd_rules import format_srd_for_prompt, format_character_for_prompt, DND_SRD

__all__ = ["format_srd_for_prompt", "format_character_for_prompt", "DND_SRD"]
