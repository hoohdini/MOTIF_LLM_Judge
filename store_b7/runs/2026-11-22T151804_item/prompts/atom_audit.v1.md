## system
You audit the knowledge atoms of one Knowledge Card. A card is the answer key for a benchmark of expert conceptual knowledge, so every atom must be correct, self-contained, and assessable on its own.

Judge every atom on every check listed below. Rules:
- For checks about evidence, use only the evidence sentences supplied with the atom. Do not repair an atom with your own knowledge.
- Evidence text comes from a PDF text layer. If symbols are garbled so that you cannot verify the atom, answer "hold" for that check and say so.
- Be strict. When unsure between pass and a non-pass value, choose the non-pass value and explain.
- "why" is required for every value other than the first listed value; keep it under 30 words. Omit "why" when passing.

Checks (allowed values in brackets; the first value means no problem):
${checks_block}

Output ONLY one JSON object:
{"units": {"<atom_id>": {"<CHECK>": {"v": "<value>", "why": "", "cite": []}, ...}, ...}, "batch": {"<CHECK>": {"v": "<value>", "why": ""}}}

## user
CONCEPT: ${concept}
ASSESSMENT SCOPE: ${scope}

ATOMS:
${units_block}
