def build_slideshow_prompt(topic: str, level: str, duration: int,
                           notes: str, language: str) -> str:
    context = f"Based on these detailed lecture notes:\n{notes[:3500]}" \
        if notes and len(notes) > 100 else f"Topic: {topic}"

    return f"""{context}

You are a university professor delivering a live {duration}-minute lecture on "{topic}" at {level} level in {language}.

Create 18 detailed lecture slides. Each narration should be a full paragraph of ACTUAL SPOKEN LECTURE CONTENT — 80-150 words, conversational, like a real professor speaking live to students. Include transitions, emphasis, examples, analogies. Say things like "Now, what I want you to notice here is...", "This is really important...", "Think about it this way...", "Let me give you a concrete example..."

RESPOND WITH ONLY A JSON ARRAY. No text before or after. No markdown fences.

Format per slide:
{{"title":"Slide title","bullets":["Point 1 — detailed sentence","Point 2 — detailed sentence","Point 3 — detailed sentence","Point 4 — detailed sentence"],"narration":"FULL spoken paragraph 80-150 words","icap":"passive","type":"content"}}

The 18 slides must cover:
1. Title/welcome (type="title", icap="passive")
2. Why this matters — real-world hook
3. Learning objectives — what students will DO by end
4. ICAP learning guide — how today is structured
5. Core concept 1 — first major idea
6. Core concept 2
7. Core concept 3
8. Key definitions — precise terminology
9. Worked example 1 (type="example", icap="active")
10. Worked example 2 — harder (type="example", icap="active")
11. Visual/Mental model — how to picture concepts
12. Common misconception 1 (icap="constructive")
13. Common misconception 2
14. Critical thinking challenge (icap="constructive")
15. Peer discussion activity (type="activity", icap="interactive")
16. Real-world application (icap="interactive")
17. Key takeaways (type="summary")
18. Closing — next steps, encouragement (type="title")

Rules:
- Narrations MUST be 80-150 words — real spoken voice
- Bullets must be complete informative sentences
- Level: {level} — calibrate depth accordingly
- Language: {language}

Return ONLY the JSON array starting with [ and ending with ]."""
