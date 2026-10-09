from flask import (
    Flask,
    render_template,
    request,
    render_template_string,
    session,
)
from werkzeug.utils import secure_filename
from pypdf import PdfReader
from dotenv import load_dotenv
from google import genai

import os
import time
import random
import html
import json
import re
import secrets


# ==========================================================
# CONFIGURATION
# ==========================================================

load_dotenv()

app = Flask(__name__)

app.secret_key = os.getenv("FLASK_SECRET_KEY") or secrets.token_hex(32)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 15 * 1024 * 1024

MAX_TEXT_LENGTH = 20000

GEMINI_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-2.5-flash",
]


# ==========================================================
# GEMINI SETUP
# ==========================================================

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError(
        "GEMINI_API_KEY was not found. "
        "Please check your .env file."
    )

client = genai.Client(api_key=api_key)


# ==========================================================
# HOME PAGE
# ==========================================================

@app.route("/")
def home():
    return render_template("index.html")


# ==========================================================
# PDF TEXT EXTRACTION
# ==========================================================

def extract_pdf_text(file_path):

    reader = PdfReader(file_path)

    extracted_pages = []

    total_pages = len(reader.pages)

    print("\n========== PDF EXTRACTION ==========")
    print("Total pages:", total_pages)

    for page_number, page in enumerate(reader.pages, start=1):

        print(f"Reading page {page_number}/{total_pages}...")

        page_text = page.extract_text()

        if page_text:
            extracted_pages.append(page_text)

    text = "\n\n".join(extracted_pages)

    print("Extracted text length:", len(text))
    print("========== EXTRACTION COMPLETE ==========\n")

    return text


# ==========================================================
# GEMINI AI FUNCTION
# ==========================================================

def ask_gemini(prompt):

    print("\n======================================")
    print("STARTING GEMINI AI")
    print("======================================")

    for model_name in GEMINI_MODELS:

        print(f"\nTrying model: {model_name}")

        for attempt in range(1, 3):

            try:

                print(f"Attempt {attempt}/2")

                response = client.interactions.create(
                    model=model_name,
                    input=prompt,
                )

                result = response.output_text

                if not result or not result.strip():
                    raise ValueError(
                        "Gemini returned an empty response."
                    )

                print(f"SUCCESS! Model used: {model_name}")

                return result.strip()

            except Exception as error:

                print(f"Model {model_name} failed: {error}")

                if attempt == 1:

                    delay = 2 + random.uniform(0, 1)

                    print(f"Retrying in {delay:.1f} seconds...")

                    time.sleep(delay)

    print("All Gemini models failed.")

    return None


# ==========================================================
# HELPER: VALIDATE AND SAVE PDF
# ==========================================================

def save_uploaded_pdf(file, prefix=""):

    if file is None or not file.filename:
        raise ValueError("Please select a PDF file.")

    if not file.filename.lower().endswith(".pdf"):
        raise ValueError("Please upload a PDF file.")

    filename = secure_filename(file.filename)

    if not filename:
        raise ValueError("The uploaded filename is invalid.")

    unique_name = (
        prefix
        + str(int(time.time() * 1000))
        + "_"
        + filename
    )

    file_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        unique_name,
    )

    file.save(file_path)

    print("PDF saved successfully:", filename)

    return file_path


# ==========================================================
# HELPER: READ AND VALIDATE PDF TEXT
# ==========================================================

def read_and_limit_pdf(file_path):

    text = extract_pdf_text(file_path)

    if not text.strip():
        raise ValueError(
            "No readable text was found in this PDF. "
            "It may contain scanned images instead of "
            "selectable text."
        )

    if len(text) > MAX_TEXT_LENGTH:

        print(
            f"PDF text limited to {MAX_TEXT_LENGTH} characters."
        )

        text = text[:MAX_TEXT_LENGTH]

    return text


# ==========================================================
# HELPER: DISPLAY RESULTS
# ==========================================================

RESULT_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">

    <meta name="viewport"
          content="width=device-width, initial-scale=1.0">

    <title>{{ title }} | CampusMate AI</title>

    <style>

        * {
            box-sizing: border-box;
        }

        body {
            margin: 0;
            padding: 30px 16px;
            font-family: Arial, sans-serif;
            background: #f5f7fb;
            color: #222;
        }

        .container {
            max-width: 900px;
            margin: auto;
        }

        .header, .card {
            background: white;
            padding: 28px;
            margin-bottom: 20px;
            border-radius: 16px;
            box-shadow: 0 5px 20px rgba(0, 0, 0, 0.06);
        }

        h1 {
            color: #4f46e5;
            margin-top: 0;
        }

        .question {
            background: #eef2ff;
            padding: 16px;
            border-radius: 10px;
            margin-bottom: 24px;
        }

        .result {
            line-height: 1.8;
            font-size: 16px;
            overflow-wrap: anywhere;
        }

        .button {
            display: inline-block;
            padding: 12px 20px;
            background: #4f46e5;
            color: white;
            text-decoration: none;
            border-radius: 8px;
            margin-top: 20px;
        }

        .button:hover {
            background: #3730a3;
        }

        @media (max-width: 600px) {
            .header, .card {
                padding: 20px;
            }
        }

    </style>
</head>

<body>

    <div class="container">

        <div class="header">
            <h1>🤖 CampusMate AI</h1>
            <p>{{ subtitle }}</p>
        </div>

        <div class="card">

            {% if question %}
            <div class="question">
                <strong>Your Question:</strong>
                <p>{{ question }}</p>
            </div>
            {% endif %}

            <h2>{{ result_heading }}</h2>

            <div class="result">{{ result | safe }}</div>

            <a href="/" class="button">
                ← Back to CampusMate AI
            </a>

        </div>

    </div>

</body>
</html>
"""


def show_result(title, subtitle, heading, result, question=None):

    safe_result = html.escape(str(result)).replace("\n", "<br>\n")

    return render_template_string(
        RESULT_TEMPLATE,
        title=title,
        subtitle=subtitle,
        result_heading=heading,
        result=safe_result,
        question=question,
    )


# ==========================================================
# FEATURE 1: STUDY MATERIAL ANALYZER
# ==========================================================

@app.route("/upload", methods=["POST"])
def upload_file():

    print("\n========== STUDY MATERIAL ANALYZER ==========")

    try:

        if "file" not in request.files:
            raise ValueError("Please select a PDF file.")

        file = request.files["file"]

        file_path = save_uploaded_pdf(file)

        text = read_and_limit_pdf(file_path)

        prompt = f"""
You are CampusMate AI, an academic study assistant.

Analyze the study material provided below.

Organize your answer using these sections:

1. SUMMARY
Explain the main ideas in simple language.

2. IMPORTANT POINTS
List important concepts, definitions, facts, and formulas.

3. EXAM-ORIENTED QUESTIONS
Create five useful questions based on the material.

4. KEY TERMS
List technical terms and explain them briefly.

5. QUICK REVISION
Provide concise revision notes.

IMPORTANT RULES:

- Base factual claims on the provided study material.
- Do not invent information or claim the PDF says something
  that it does not say.
- If information needed for a section is missing, say so.
- Keep the answer student-friendly.
- Use headings and bullet points.

STUDY MATERIAL:
<study_material>
{text}
</study_material>
"""

        ai_result = ask_gemini(prompt)

        if not ai_result:

            ai_result = (
                "CampusMate AI could not analyze your PDF "
                "because the AI service is temporarily unavailable. "
                "Please try again later."
            )

        return show_result(
            title="Study Material Analyzer",
            subtitle="AI-powered analysis of your study material",
            heading="📚 Your Study Notes",
            result=ai_result,
        )

    except ValueError as error:

        return show_result(
            title="Upload Error",
            subtitle="Please check your uploaded file",
            heading="⚠️ Unable to Analyze PDF",
            result=str(error),
        ), 400

    except Exception as error:

        print("STUDY MATERIAL ERROR:", error)

        return show_result(
            title="Error",
            subtitle="Something went wrong",
            heading="⚠️ An Error Occurred",
            result=(
                "CampusMate AI could not process this PDF. "
                "Please check the file and try again."
            ),
        ), 500


# ==========================================================
# FEATURE 2: ASK YOUR NOTES
# ==========================================================

@app.route("/ask", methods=["POST"])
def ask_notes():

    print("\n========== ASK YOUR NOTES ==========")

    try:

        if "file" not in request.files:
            raise ValueError("Please select a PDF file.")

        file = request.files["file"]

        question = request.form.get("question", "").strip()

        if not question:
            raise ValueError("Please enter your question.")

        file_path = save_uploaded_pdf(
            file,
            prefix="ask_notes_",
        )

        text = read_and_limit_pdf(file_path)

        prompt = f"""
You are CampusMate AI, an academic assistant.

Answer the student's question using the study material below.

STRICT INSTRUCTIONS:

1. Read the study material carefully.
2. Identify information relevant to the question.
3. Base the answer on the provided study material.
4. Explain supported information clearly and simply.
5. If only part of the answer is supported, explain that part
   and identify what is missing.
6. If the answer cannot be found, respond:
   "I couldn't find the answer in the uploaded notes."
7. Never invent quotations or claim the notes contain
   information that is not present.

STUDY MATERIAL:
<study_material>
{text}
</study_material>

STUDENT QUESTION:
<student_question>
{question}
</student_question>

Answer using the instructions above.
"""

        answer = ask_gemini(prompt)

        if not answer:

            answer = (
                "CampusMate AI could not answer your question "
                "because the AI service is temporarily unavailable. "
                "Please try again in a few moments."
            )

        return show_result(
            title="Ask Your Notes",
            subtitle="Get answers from your study material",
            heading="🤖 CampusMate AI's Answer",
            result=answer,
            question=question,
        )

    except ValueError as error:

        return show_result(
            title="Ask Your Notes",
            subtitle="Please check your question and uploaded PDF",
            heading="⚠️ Unable to Answer",
            result=str(error),
        ), 400

    except Exception as error:

        print("ASK YOUR NOTES ERROR:", error)

        return show_result(
            title="Ask Your Notes",
            subtitle="Something went wrong",
            heading="⚠️ An Error Occurred",
            result="CampusMate AI could not process your question. Please try again.",
            question=request.form.get("question", "").strip(),
        ), 500


# ==========================================================
# FEATURE 3: AI QUIZ GENERATOR
# ==========================================================

@app.route("/quiz", methods=["POST"])
def generate_quiz():

    print("\n========== AI QUIZ GENERATOR ==========")

    try:

        # --------------------------------------
        # 1. Validate the uploaded PDF
        # --------------------------------------

        if "file" not in request.files:
            raise ValueError("Please select a PDF file.")

        file = request.files["file"]

        file_path = save_uploaded_pdf(
            file,
            prefix="quiz_",
        )

        text = read_and_limit_pdf(file_path)

        # --------------------------------------
        # 2. Validate quiz settings
        # --------------------------------------

        allowed_counts = {5, 10, 15}

        try:
            num_questions = int(
                request.form.get("num_questions", "10")
            )
        except (TypeError, ValueError):
            raise ValueError("Please choose a valid question count.")

        if num_questions not in allowed_counts:
            raise ValueError(
                "Choose 5, 10, or 15 questions."
            )

        difficulty = request.form.get(
            "difficulty",
            "Medium",
        ).strip().capitalize()

        if difficulty not in {"Easy", "Medium", "Hard"}:
            raise ValueError(
                "Choose Easy, Medium, or Hard difficulty."
            )

        # --------------------------------------
        # 3. Ask Gemini to generate MCQs
        # --------------------------------------

        prompt = f"""
You are CampusMate AI, an educational quiz generator.

Create exactly {num_questions} multiple-choice questions
from the supplied study material.

DIFFICULTY: {difficulty}

DIFFICULTY GUIDELINES:

Easy:
Test basic definitions, facts, and direct understanding.

Medium:
Test understanding, comparisons, and application of concepts.

Hard:
Test deeper reasoning and relationships between concepts,
but do not require facts outside the provided material.

STRICT SOURCE RULES:

- Use only information supported by the supplied material.
- Do not invent facts, formulas, or concepts.
- If the material does not support enough distinct questions,
  generate only the number of good questions it supports.
- Every question must have exactly four answer options.
- Exactly one option must be correct.
- The three incorrect options must be plausible but clearly incorrect.
- Explanations must be supported by the supplied material.
- Do not include the answer in the question itself.

Return ONLY valid JSON. Do not use Markdown code fences.

Use exactly this structure:

{{
  "questions": [
    {{
      "question": "Question text",
      "options": [
        "Option A",
        "Option B",
        "Option C",
        "Option D"
      ],
      "correct_answer": 0,
      "explanation": "Explanation based on the study material"
    }}
  ]
}}

IMPORTANT:
- correct_answer must be an integer from 0 to 3.
- 0 means the first option, 1 the second, 2 the third,
  and 3 the fourth.
- Do not return any other keys.
- Generate no more than {num_questions} questions.

STUDY MATERIAL:
<study_material>
{text}
</study_material>
"""

        print(
            f"Generating {num_questions} questions "
            f"at {difficulty} difficulty..."
        )

        ai_result = ask_gemini(prompt)

        if not ai_result:
            raise RuntimeError(
                "The AI service is temporarily unavailable. "
                "Please try generating the quiz again."
            )

        # --------------------------------------
        # 4. Parse and validate Gemini's JSON
        # --------------------------------------

        cleaned_result = ai_result.strip()

        # Remove Markdown fences if Gemini returns them.
        cleaned_result = re.sub(
            r"^```(?:json)?\s*",
            "",
            cleaned_result,
            flags=re.IGNORECASE,
        )

        cleaned_result = re.sub(
            r"\s*```$",
            "",
            cleaned_result,
        )

        try:
            quiz_data = json.loads(cleaned_result)
        except json.JSONDecodeError:

            # Attempt to recover a JSON object from the response.
            match = re.search(
                r"\{.*\}",
                cleaned_result,
                flags=re.DOTALL,
            )

            if not match:
                raise ValueError(
                    "The AI returned an invalid quiz format. "
                    "Please try again."
                )

            quiz_data = json.loads(match.group(0))

        raw_questions = quiz_data.get("questions", [])

        if not isinstance(raw_questions, list):
            raise ValueError(
                "The AI returned an invalid question list. "
                "Please try again."
            )

        # Validate questions before showing them to the student.
        questions = []

        for item in raw_questions:

            if not isinstance(item, dict):
                continue

            question_text = item.get("question")
            options = item.get("options")
            correct_answer = item.get("correct_answer")
            explanation = item.get("explanation", "")

            if not isinstance(question_text, str):
                continue

            if not isinstance(options, list) or len(options) != 4:
                continue

            if not all(isinstance(option, str) for option in options):
                continue

            if (
                isinstance(correct_answer, bool)
                or not isinstance(correct_answer, int)
                or correct_answer not in range(4)
            ):
                continue

            if not all(option.strip() for option in options):
                continue

            questions.append({
                "question": question_text.strip(),
                "options": [option.strip() for option in options],
                "correct_answer": correct_answer,
                "explanation": (
                    explanation.strip()
                    if isinstance(explanation, str)
                    else ""
                ),
            })

            if len(questions) >= num_questions:
                break

        if not questions:
            raise ValueError(
                "No valid quiz questions could be generated. "
                "Try another PDF with more readable study content."
            )

        print("Valid questions generated:", len(questions))

        # --------------------------------------
        # 5. Create a temporary quiz identifier
        # --------------------------------------

        quiz_id = secrets.token_urlsafe(16)

        # Store the answer key on the server, not in the HTML.
        if "active_quizzes" not in session:
            session["active_quizzes"] = {}

        active_quizzes = session["active_quizzes"]

        active_quizzes[quiz_id] = {
            "questions": questions,
            "difficulty": difficulty,
        }

        # Keep the session small and limit retained quiz data.
        if len(active_quizzes) > 3:
            oldest_keys = list(active_quizzes.keys())[:-3]

            for old_key in oldest_keys:
                active_quizzes.pop(old_key, None)

        session["active_quizzes"] = active_quizzes
        session.modified = True

        # --------------------------------------
        # 6. Display the interactive quiz
        # --------------------------------------

        return render_template_string(
            QUIZ_TEMPLATE,
            quiz_id=quiz_id,
            questions=questions,
            difficulty=difficulty,
            total=len(questions),
        )

    except ValueError as error:

        return show_result(
            title="AI Quiz Generator",
            subtitle="Please check your PDF and quiz settings",
            heading="⚠️ Unable to Generate Quiz",
            result=str(error),
        ), 400

    except Exception as error:

        print("QUIZ GENERATOR ERROR:", error)

        return show_result(
            title="AI Quiz Generator",
            subtitle="Something went wrong",
            heading="⚠️ Quiz Generation Failed",
            result=(
                "CampusMate AI could not generate your quiz. "
                "Please try again. If the problem continues, "
                "check the Flask terminal for the error."
            ),
        ), 500


# ==========================================================
# INTERACTIVE QUIZ PAGE
# ==========================================================

QUIZ_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">

<head>

    <meta charset="UTF-8">

    <meta name="viewport"
          content="width=device-width, initial-scale=1.0">

    <title>AI Quiz | CampusMate AI</title>

    <style>

        * {
            box-sizing: border-box;
        }

        body {
            font-family: Arial, sans-serif;
            background: #f5f7fb;
            color: #222;
            margin: 0;
            padding: 30px 16px;
        }

        .container {
            max-width: 850px;
            margin: auto;
        }

        .header, .card {
            background: white;
            padding: 26px;
            border-radius: 16px;
            margin-bottom: 22px;
            box-shadow: 0 5px 20px rgba(0, 0, 0, 0.06);
        }

        h1 {
            color: #4f46e5;
        }

        .question-card {
            background: #fafaff;
            padding: 20px;
            border: 1px solid #e4e7ff;
            border-radius: 12px;
            margin-bottom: 22px;
        }

        .question-number {
            color: #4f46e5;
            font-weight: bold;
        }

        .option {
            display: block;
            padding: 13px;
            margin: 10px 0;
            border: 1px solid #ddd;
            border-radius: 8px;
            background: white;
            cursor: pointer;
            line-height: 1.5;
        }

        .option:hover {
            border-color: #4f46e5;
            background: #f5f5ff;
        }

        .option input {
            margin-right: 10px;
        }

        button, .back-button {
            display: inline-block;
            padding: 13px 22px;
            border: none;
            border-radius: 8px;
            background: #4f46e5;
            color: white;
            font-size: 15px;
            cursor: pointer;
            text-decoration: none;
        }

        button:hover, .back-button:hover {
            background: #3730a3;
        }

        .score {
            padding: 20px;
            border-radius: 12px;
            background: #eef2ff;
            margin-bottom: 20px;
        }

        .feedback {
            padding: 13px;
            margin-top: 12px;
            background: white;
            border-radius: 8px;
            line-height: 1.6;
        }

        .correct {
            border-left: 5px solid #16a34a;
        }

        .incorrect {
            border-left: 5px solid #dc2626;
        }

        .muted {
            color: #666;
        }

        @media (max-width: 600px) {
            .header, .card {
                padding: 18px;
            }

            button, .back-button {
                width: 100%;
                text-align: center;
            }
        }

    </style>

</head>

<body>

<div class="container">

    <div class="header">

        <h1>📝 CampusMate AI Quiz</h1>

        <p>
            Difficulty:
            <strong>{{ difficulty }}</strong>
        </p>

        <p class="muted">
            {{ total }} questions • Choose one answer per question.
        </p>

    </div>

    <div class="card">

        <form id="quizForm">

            <input
                type="hidden"
                id="quizId"
                value="{{ quiz_id }}"
            >

            {% for item in questions %}

            <div class="question-card">

                <p class="question-number">
                    Question {{ loop.index }} of {{ total }}
                </p>

                <h3>{{ item.question }}</h3>

                {% for option in item.options %}

                <label class="option">

                    <input
                        type="radio"
                        name="q{{ loop.index0 }}"
                        value="{{ loop.index0 }}"
                    >

                    {{ ["A", "B", "C", "D"][loop.index0] }}.
                    {{ option }}

                </label>

                {% endfor %}

                <div
                    class="feedback"
                    id="feedback{{ loop.index0 }}"
                    hidden
                ></div>

            </div>

            {% endfor %}

            <button type="submit" id="submitButton">
                ✅ Submit Quiz
            </button>

        </form>

        <div id="scoreCard" class="score" hidden></div>

        <a href="/" class="back-button">
            ← Back to CampusMate AI
        </a>

    </div>

</div>

<script>

    const quizForm = document.getElementById("quizForm");
    const submitButton = document.getElementById("submitButton");
    const scoreCard = document.getElementById("scoreCard");

    quizForm.addEventListener("submit", async function(event) {

        event.preventDefault();

        const totalQuestions = {{ total }};
        const answers = {};

        for (let i = 0; i < totalQuestions; i++) {

            const selected = document.querySelector(
                'input[name="q' + i + '"]:checked'
            );

            if (!selected) {
                alert("Please answer Question " + (i + 1) + " before submitting.");
                return;
            }

            answers[i] = Number(selected.value);
        }

        submitButton.disabled = true;
        submitButton.textContent = "Checking your answers...";

        try {

            const response = await fetch("/quiz/submit", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    quiz_id: document.getElementById("quizId").value,
                    answers: answers
                })
            });

            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.error || "Could not check the quiz.");
            }

            scoreCard.hidden = false;

            scoreCard.replaceChildren();

            const heading = document.createElement("h2");
            heading.textContent = "🎉 Your Quiz Results";

            const score = document.createElement("h3");
            score.textContent =
                "Your Score: " + result.score + " / " + result.total;

            const percentage = document.createElement("p");
            percentage.textContent =
                "Percentage: " + result.percentage + "%";

            const message = document.createElement("p");
            message.textContent = result.message;

            scoreCard.append(heading, score, percentage, message);

            result.results.forEach(function(item, index) {

                const feedback = document.getElementById(
                    "feedback" + index
                );

                feedback.hidden = false;
                feedback.replaceChildren();

                const status = document.createElement("strong");

                status.textContent = item.is_correct
                    ? "✅ Correct!"
                    : "❌ Incorrect";

                const correct = document.createElement("p");
                correct.textContent =
                    "Correct answer: " + item.correct_option;

                const explanation = document.createElement("p");
                explanation.textContent =
                    "Explanation: " + item.explanation;

                feedback.append(status, correct, explanation);

                feedback.classList.add(
                    item.is_correct ? "correct" : "incorrect"
                );

            });

            document.querySelectorAll(
                '#quizForm input[type="radio"]'
            ).forEach(function(input) {
                input.disabled = true;
            });

            submitButton.textContent = "Quiz Submitted";

            scoreCard.scrollIntoView({
                behavior: "smooth",
                block: "center"
            });

        } catch (error) {

            alert(error.message);

            submitButton.disabled = false;
            submitButton.textContent = "✅ Submit Quiz";

        }

    });

</script>

</body>
</html>
"""


# ==========================================================
# SUBMIT QUIZ AND CALCULATE SCORE
# ==========================================================

@app.route("/quiz/submit", methods=["POST"])
def submit_quiz():

    try:

        data = request.get_json(silent=True) or {}

        quiz_id = data.get("quiz_id")
        answers = data.get("answers")

        if not isinstance(quiz_id, str):
            return {
                "error": "Invalid quiz. Please generate a new quiz."
            }, 400

        if not isinstance(answers, dict):
            return {
                "error": "Please submit your answers."
            }, 400

        active_quizzes = session.get("active_quizzes", {})
        quiz = active_quizzes.get(quiz_id)

        if not quiz:
            return {
                "error": (
                    "This quiz has expired or is no longer available. "
                    "Please generate a new quiz."
                )
            }, 400

        questions = quiz["questions"]

        if len(answers) != len(questions):
            return {
                "error": "Please answer every question."
            }, 400

        score = 0
        results = []

        for index, question in enumerate(questions):

            submitted_answer = answers.get(str(index))

            if (
                isinstance(submitted_answer, bool)
                or not isinstance(submitted_answer, int)
                or submitted_answer not in range(4)
            ):
                return {
                    "error": "One or more answers are invalid."
                }, 400

            correct_answer = question["correct_answer"]
            is_correct = submitted_answer == correct_answer

            if is_correct:
                score += 1

            results.append({
                "is_correct": is_correct,
                "correct_option": (
                    "ABCD"[correct_answer]
                    + ". "
                    + question["options"][correct_answer]
                ),
                "explanation": question["explanation"],
            })

        total = len(questions)
        percentage = round((score / total) * 100)

        if percentage == 100:
            message = "Excellent! You answered every question correctly!"
        elif percentage >= 70:
            message = "Great job! You have a good understanding of the material."
        elif percentage >= 40:
            message = "Good effort! Review the explanations to improve."
        else:
            message = "Keep practising! Review your notes and try again."

        # Invalidate this quiz so it cannot be submitted repeatedly.
        active_quizzes.pop(quiz_id, None)
        session["active_quizzes"] = active_quizzes
        session.modified = True

        return {
            "score": score,
            "total": total,
            "percentage": percentage,
            "message": message,
            "results": results,
        }

    except Exception as error:

        print("QUIZ SUBMISSION ERROR:", error)

        return {
            "error": "Could not calculate your score. Please try again."
        }, 500


# ==========================================================
# FILE TOO LARGE ERROR
# ==========================================================

@app.errorhandler(413)
def file_too_large(error):

    return show_result(
        title="File Too Large",
        subtitle="Please upload a smaller PDF",
        heading="⚠️ Upload Limit Exceeded",
        result=(
            "Your PDF exceeds the 15 MB upload limit. "
            "Please choose a smaller file."
        ),
    ), 413


# ==========================================================
# START FLASK
# ==========================================================

if __name__ == "__main__":

    print("\n======================================")
    print("CampusMate AI is starting...")
    print("Open: http://127.0.0.1:5000")
    print("======================================\n")

    app.run(debug=True)