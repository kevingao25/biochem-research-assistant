GUARDRAIL_PROMPT = """You decide whether a question belongs in a biochemistry research assistant.

The assistant is for papers about bacteriophages, bacteria, molecular biology, genomics,
biomolecules, immune/defense systems such as CRISPR, anti-phage defense, and related wet-lab
or computational biology topics.

Return only JSON with this shape:
{{"allowed": true, "reason": "short reason"}}

Question:
{query}
"""


GRADE_DOCUMENTS_PROMPT = """Decide whether the paper excerpts are useful for answering the question.

Return only JSON with this shape:
{{"relevant": true, "reason": "short reason"}}

Question:
{query}

Paper excerpts:
{context}
"""


REWRITE_QUERY_PROMPT = """Rewrite this biochemistry research question into a better search query.

Focus on scientific terms, entities, mechanisms, and synonyms. Return only JSON with this shape:
{{"query": "rewritten search query", "reason": "short reason"}}

Question:
{query}
"""
