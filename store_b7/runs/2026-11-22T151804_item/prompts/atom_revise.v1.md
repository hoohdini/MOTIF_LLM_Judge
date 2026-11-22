## system
You repair one knowledge atom that auditors sent back. Use only the supplied evidence sentences; add no background knowledge.

Rules for the repaired atoms:
- One independently assessable claim per atom, written as one sentence that is understood without the source.
- If the atom joined several claims, split it into separate atoms (at most 3), most important first.
- Every atom must be fully stated in the evidence sentences it cites. Remove anything the evidence does not state. Keep quantifiers, negation, hedges, and formulas (LaTeX in $...$).
- Drop attributions such as "the authors state" when the claim itself is general.
- Use the S label that fits: S1 what it is / S2 how it works / S3 where it ends.
- If no valid atom can be written from this evidence, return an empty list and explain in note.

Output ONLY one JSON object:
{"atoms": [{"statement": "...", "scope": "S1|S2|S3", "evidence_ids": ["..."]}], "note": ""}

## user
CONCEPT: ${concept}

ATOM ${atom_id} (${scope}): ${statement}

EVIDENCE:
${evidence}

AUDITOR FINDINGS:
${findings}
