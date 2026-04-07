NOTES_SYSTEM = """You are an expert university lecturer with 20 years of experience writing world-class lecture notes.
You balance academic rigour with genuine accessibility.
You always ground abstract concepts in concrete examples before formalising them.
Your notes are thorough, engaging, and written in a voice students actually want to read."""


def build_notes_prompt(topic: str, level: str, duration: int,
                       objectives: str, style: str, language: str) -> str:
    obj_block = objectives.strip() if objectives and objectives.strip() \
        else f"Cover {topic} comprehensively for {level}-level learners."

    return f"""{NOTES_SYSTEM}

Write comprehensive lecture notes on "{topic}" for {level}-level students.
Duration: {duration} minutes. Pedagogy: {style}. Write ENTIRELY in {language}.

LEARNING OBJECTIVES:
{obj_block}

Structure using EXACTLY these ICAP tags (used for colour-coding only — keep them):

[PASSIVE] 1. INTRODUCTION AND CONTEXT
Why this topic matters. Historical background. Real-world relevance. A compelling hook. At least 3 detailed paragraphs.

[PASSIVE] 2. CORE DEFINITIONS AND TERMINOLOGY
Define every key term precisely with examples. At least 6-8 terms. Use **Term**: definition format.

[ACTIVE] 3. CORE CONCEPT EXPLANATIONS
Deep dive into each major concept. Step-by-step reasoning. Multiple representations. At least 3-4 major concepts, each 2+ paragraphs with bullet points.

[ACTIVE] 4. WORKED EXAMPLES
Use "Example:" to start each. At least 3 fully worked examples of increasing difficulty. Show every step and explain WHY.

[CONSTRUCTIVE] 5. CRITICAL THINKING & ANALYSIS
Open-ended analysis questions. "What if" scenarios. Mini case study. At least 4 prompts requiring deep thought.

[CONSTRUCTIVE] 6. COMMON MISCONCEPTIONS
At least 5 common errors. For each: why students make it, then the correct understanding.

[INTERACTIVE] 7. COLLABORATIVE ACTIVITIES
Pair/group activities with specific prompts. Think-pair-share. Peer teaching exercise.

[INTERACTIVE] 8. REAL-WORLD APPLICATION
A substantial real-world scenario to solve collaboratively. Include reflection questions.

[PASSIVE] 9. SUMMARY & KEY TAKEAWAYS
Bullet-point recap of every major concept. A cheat sheet of key formulas/rules.

[CONSTRUCTIVE] 10. SELF-ASSESSMENT
5 self-check questions (recall, application, analysis). A "one-minute paper" prompt.

Formatting rules:
- Use **bold** for key terms
- Use bullet points with - for lists
- Start worked examples with "Example:"
- Write in clear, engaging academic language
- Aim for at least 2,500 words total
"""
