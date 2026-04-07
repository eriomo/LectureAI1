def build_study_plan_prompt(topic: str, level: str, background: str, language: str) -> str:
    return f"""Create a personalised 7-day study plan for a student studying "{topic}" at {level} level.
Student background: {background if background else 'General learner'}.
Write in {language}.

For each day include:
- Study focus (30-60 min session)
- 2-3 specific tasks
- One self-check question
- A daily motivational tip

End with 3 recommended resources (books/papers/videos). Be specific and actionable.
Format clearly with Day 1, Day 2 etc as headers."""


def build_feedback_prompt(title: str, description: str, max_score: int,
                          content: str) -> str:
    return f"""You are a helpful academic assistant reviewing a student assignment.

Assignment: {title}
Instructions: {description}
Max score: {max_score}
Student submission: {content}

Give concise, encouraging feedback in 3-4 sentences.
Note one specific strength and one concrete area to improve.
Do not assign a numerical score.
End with a brief motivational sentence addressing the student directly."""


def build_live_question_prompt(topic: str, level: str, question: str) -> str:
    return f"""Instructor. Topic: "{topic}" Level: {level}.
Student question: "{question}"

Answer in under 150 words. Use plain language. Note one common misconception related to this.
End with one probing follow-up question to deepen thinking."""


def build_confusion_rescue_prompt(topic: str, level: str, confusion: str) -> str:
    return f"""Instructor. Topic: "{topic}" Level: {level}.
Students are confused about: "{confusion}"

Give: (1) A fresh analogy that explains it differently, (2) A 3-minute activity to rescue understanding, (3) One sentence to re-engage the class."""


def build_pacing_prompt(topic: str, total: int, elapsed: int, segment: str) -> str:
    remaining = total - elapsed
    return f"""Instructor. Topic: "{topic}". {total}min total. {elapsed}min elapsed. {remaining}min remaining. Currently on: "{segment}".

Are they on track? What should they do RIGHT NOW? What can be cut or compressed if needed? Be direct and specific."""


def build_concept_check_prompt(topic: str, level: str, question: str, correct_pct: int) -> str:
    return f"""Instructor. Topic: "{topic}" Level: {level}. Asked: "{question}". {correct_pct}% correct.

Interpret this result. What does it tell you about understanding? What should the instructor do in the next 5 minutes to address the gap?"""


def build_student_question_prompt(topic: str, level: str, name: str,
                                  year: str, background: str, question: str) -> str:
    return f"""Friendly tutor. Topic: "{topic}". Student: {name}, {year}, background: {background}, level: {level}.
Question: "{question}"

Answer in under 150 words. Use plain language. End with encouragement using their name."""


def build_video_script_prompt(topic: str, level: str) -> str:
    return f"""Write a 5-minute video lecture script for "{topic}" at {level} level.
Include: hook intro, what it is, how it works, real example, common mistakes, summary outro.
Use natural spoken language with [PAUSE] markers. Write as if speaking directly to camera."""


def build_rubric_prompt(task: str, rubric_type: str) -> str:
    return f"""Create a detailed grading rubric for a {rubric_type} assignment: "{task}".
Include 4-5 criteria with Excellent/Good/Adequate/Poor descriptors and point ranges.
Format as a clear table with criteria, performance levels, and point allocations."""
