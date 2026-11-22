## system
You review benchmark items against the knowledge atom each one tests. The items test whether a model knows the atom (recall and recognition), and the test taker sees only the question and options.

Judge each item on the checks listed on its CHECKS line. Rules:
- Use only the atom and its evidence as ground truth, except where a check says to use general domain knowledge.
- For KEY_CORRECT, use "hold" when unreadable PDF symbols prevent verification; explain what is needed. Use fail when the supplied information permits a judgment and the key is wrong or the item is underdetermined. Missing premises in the item are an item defect, not automatically a hold.
- Be strict within each check's allowed values. The KEY_CORRECT hold rule takes precedence over this strictness rule. Judge other checks independently; do not infer a wrong key merely from inability to verify the source.
- "why" is required for every value other than pass; keep it under 30 words. Omit "why" when passing.

Checks (allowed values in brackets):
${checks_block}

Output ONLY one JSON object:
{"units": {"<item_id>": {"<CHECK>": {"v": "<value>", "why": "", "cite": []}, ...}, ...}}

## user
CONCEPT: ${concept}

ITEMS:
${units_block}
