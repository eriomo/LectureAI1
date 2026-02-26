# 🎓 LectureAI

**Human-AI Co-Orchestration in Data Science Education**

> A working prototype that operationalises the three-layer co-orchestration framework from Jamil (2025), enabling AI-assisted teaching before, during, and after class.

🌐 **Live Demo:** [https://lectureai1-1.onrender.com/](https://lectureai1-1.onrender.com/)

---

## What Is LectureAI?

LectureAI is a web application built for data science educators that uses AI to support teaching at every stage of a lecture. It is based directly on the framework published by Professor Hasan Jamil:

> Jamil, H.M. (2025). *Human-AI Co-Orchestration in Data Science Education.* ACM Transactions on Computing Education. doi:10.1145/3785369

The system implements all **three layers** of the framework:

| Layer | When | What It Does |
|-------|------|-------------|
| **Layer 1** | Before class | AI co-designs lesson plans using the ICAP framework |
| **Layer 2** | During class | Real-time AI guidance while the lecture is happening |
| **Layer 3** | After class | Tiered practice questions and student support materials |

---

## Features

### 📋 Layer 1 — Lesson Builder
- Generates full lesson plans with 5 structured segments
- Every segment labelled with its **ICAP engagement level** (Passive / Active / Constructive / Interactive)
- Topic-specific analogies, in-class activities, and reflection questions
- 80+ topic suggestions with real-time autocomplete across 8 subject categories
- ICAP coverage breakdown at a glance
- Instructor approval checkboxes and note fields per segment

### 🔴 Layer 2 — Live Classroom Cockpit
Four real-time tools for use during a live lecture:

1. **Student Question Handler** — type a student question, get exact words to say out loud + follow-up
2. **Confusion Detector** — describe what students are lost on, get an alternative explanation + rescue activity
3. **Concept Check Interpreter** — enter % of students who answered correctly, get pacing advice
4. **Pacing Assistant** — enter time elapsed, get on-track/behind/ahead assessment + what to cut

### 📚 Layer 3 — Student Support
- Plain-language micro-explanation for every topic
- 6 tiered practice questions: 2 Easy, 2 Medium, 2 Hard
- Self-regulated learning (SRL) prompts

### 📊 Evaluation & Export
- 5-criterion evaluation rubric with scoring
- Export full lesson plan as a downloadable text file

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Frontend | HTML, CSS, JavaScript (single file, no framework) |
| Backend | Python + Flask |
| AI Model | Llama 3.3 70B via Groq API |
| Hosting | Render (free tier) |
| Version Control | GitHub |

---

## Running Locally

**Requirements:** Python 3.8+, a free [Groq API key](https://console.groq.com)

```bash
# 1. Clone the repo
git clone https://github.com/eriomo/LectureAI.git
cd LectureAI

# 2. Install dependencies
pip install flask flask-cors groq gunicorn

# 3. Set your API key
export GROQ_API_KEY=your_gsk_key_here

# 4. Run the server
python server.py

# 5. Open in browser
# http://localhost:5000
```

---

## Project Structure

```
LectureAI/
├── server.py               # Flask backend — all API routes
├── lectureai_gemini.html   # Complete frontend (single file)
├── requirements.txt        # Python dependencies
└── render.yaml             # Render deployment config
```

---

## API Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET | Serves the frontend |
| `/generate` | POST | Generates full lesson plan + student support |
| `/layer2/question` | POST | Handles student question mid-lecture |
| `/layer2/confusion` | POST | Generates confusion rescue strategy |
| `/layer2/conceptcheck` | POST | Interprets concept check results |
| `/layer2/pacing` | POST | Analyses lecture pacing |
| `/health` | GET | Health check |

---

## ICAP Framework

All content is tagged using the ICAP framework (Chi & Wylie, 2014):

- 🟠 **Passive** — students receive information
- 🟢 **Active** — students respond to prompts
- 🔵 **Constructive** — students produce something new
- 🟣 **Interactive** — students collaborate with peers

---

## Supervisor

**Professor Hasan Jamil** — University of Idaho  
Research area: Data Science Education, Human-AI Collaboration

---

## Author

**Omolola** — February 2026
