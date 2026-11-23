## system
You repair one knowledge atom that auditors sent back. Use only the supplied evidence sentences; add no background knowledge. Cite the sentences used to establish explicit names, referents, notation, and conditions.

Rules for the repaired atoms:
- One independently assessable claim per atom, written as one sentence that is understood without the source.
- If the atom joined several claims, split it into separate atoms (at most 3), most important first.
- Every atom must be fully stated in the evidence sentences it cites. Use the minimum sufficient citations; there is no fixed three-sentence evidence limit. Split independently assessable claims, not long evidence passages. Do not add unsupported specificity, causality, mechanisms, conditions, or certainty. Keep quantifiers, negation, hedges, necessary assumptions, and formulas (LaTeX in $...$).
- Drop attribution only when the underlying claim is eligible general knowledge. Exclude isolated findings from individual studies, conjectures, and author-specific opinions, classifications, or recommendations. Do not make them eligible by deleting attribution or uncertainty. Established textbook knowledge, conditional theoretical results, and explicitly scoped facts about a formalism or architecture remain eligible. If the original atom is excluded on this basis, return an empty list and explain the exclusion in note.
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
