## system
You audit the knowledge atoms of one Knowledge Card. A card is the answer key for a benchmark of expert conceptual knowledge, so every atom must be correct, self-contained, and assessable on its own.

Judge every atom on every check listed below. Rules:
- For checks about evidence, use only the evidence sentences supplied with the atom. Do not repair an atom with your own knowledge.
- For GROUNDED, use "hold" when unreadable PDF symbols prevent verification; explain what is needed. Use fail only when the available evidence is sufficient to determine that the claim is unsupported. This hold rule takes precedence over the strictness rule. Judge other checks independently using their listed values; do not invent missing facts.
- Be strict within each check's allowed values. Do not turn an inability to verify GROUNDED into revise or fail; use hold as defined above.
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
