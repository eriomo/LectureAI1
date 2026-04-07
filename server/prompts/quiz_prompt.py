def build_quiz_prompt(topic: str, level: str, notes: str, language: str) -> str:
    context = f"Based on these lecture notes:\n{notes[:1200]}" if notes and len(notes) > 100 \
        else f"Based on the topic: {topic}"
    return f"""{context}

Create exactly 5 multiple choice questions for {level}-level students on "{topic}". Write in {language}.

Return ONLY a valid JSON array — no preamble, no markdown fences:
[
  {{"q":"Question?","options":["A","B","C","D"],"ans":0,"exp":"Why A is correct"}},
  ...
]

The "ans" field is the 0-indexed position of the correct answer.
Make questions test understanding, not just recall. Vary difficulty across the 5 questions."""


def build_adaptive_quiz_prompt(topic: str, level: str, previous_results: list, language: str) -> str:
    """For adaptive quiz — adjusts difficulty based on previous answers."""
    correct = sum(1 for r in previous_results if r.get("correct"))
    total = len(previous_results)
    score_pct = (correct / total * 100) if total > 0 else 50

    if score_pct >= 80:
        next_difficulty = "harder than previous — assume the student understands basics, push deeper"
    elif score_pct <= 40:
        next_difficulty = "easier — more foundational, more scaffolded, with clearer distractors"
    else:
        next_difficulty = "similar difficulty to what was asked before"

    context = f"Previous Q&A results: {previous_results}\nScore so far: {correct}/{total}"

    return f"""{context}

The student scored {score_pct:.0f}%. Next question should be: {next_difficulty}.

Generate 1 new multiple choice question on "{topic}" at {level} level. Write in {language}.

Return ONLY valid JSON (single object, not array):
{{"q":"Question?","options":["A","B","C","D"],"ans":0,"exp":"Why A is correct","difficulty":"medium"}}"""
