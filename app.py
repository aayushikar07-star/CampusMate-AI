from flask import (
    Flask,
    render_template,
    render_template_string,
    request,
    jsonify,
)
from werkzeug.utils import secure_filename
from pypdf import PdfReader
from dotenv import load_dotenv
from google import genai

import os
import re
import json
import time
import secrets
import random
import html


# ==========================================================
# CONFIGURATION
# ==========================================================

load_dotenv()

app = Flask(__name__)

# Vercel's deployed filesystem is read-only except for /tmp.
# Keep local uploads in the project folder, but use /tmp on Vercel.
if os.getenv("VERCEL"):
    UPLOAD_FOLDER = os.path.join("/tmp", "campusmate_uploads")
else:
    UPLOAD_FOLDER = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "uploads"
    )

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

# Temporary server-side quiz storage.
# Quiz data is not stored in browser cookies.
QUIZ_STORE = {}

# A quiz expires after two hours.
QUIZ_EXPIRY_SECONDS = 2 * 60 * 60


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

    for page_number, page in enumerate(
        reader.pages,
        start=1
    ):
        print(
            f"Reading page {page_number}/{total_pages}..."
        )

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
                    input=prompt
                )

                result = response.output_text

                if not result or not result.strip():
                    raise ValueError(
                        "Gemini returned an empty response."
                    )

                print("SUCCESS! Model used:", model_name)

                return result.strip()

            except Exception as error:
                print(
                    f"Model {model_name} failed: {error}"
                )

                if attempt == 1:
                    delay = 2 + random.uniform(0, 1)

                    print(
                        f"Retrying in {delay:.1f} seconds..."
                    )

                    time.sleep(delay)

    print("All Gemini models failed.")

    return None


# ==========================================================
# HELPER: SAVE AND VALIDATE PDF
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
        + secrets.token_hex(4)
        + "_"
        + filename
    )

    file_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        unique_name
    )

    file.save(file_path)

    print("PDF saved successfully:", filename)

    return file_path


# ==========================================================
# HELPER: READ AND VALIDATE PDF
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
            box-shadow: 0 5px 20px rgba(0,0,0,.06);
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


def show_result(
    title,
    subtitle,
    heading,
    result,
    question=None
):
    safe_result = html.escape(result).replace(
        "\n",
        "<br>\n"
    )

    return render_template_string(
        RESULT_TEMPLATE,
        title=title,
        subtitle=subtitle,
        result_heading=heading,
        result=safe_result,
        question=question
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

        file_path = save_uploaded_pdf(
            request.files["file"]
        )

        text = read_and_limit_pdf(file_path)

        prompt = f"""
You are CampusMate AI, an academic study assistant.

Analyze the study material below.

Organize your answer into these sections:

1. SUMMARY
Explain the main ideas in simple language.

2. IMPORTANT POINTS
List important concepts, definitions, facts and formulas.

3. EXAM-ORIENTED QUESTIONS
Create five useful questions based on the material.

4. KEY TERMS
Explain important technical terms briefly.

5. QUICK REVISION
Provide concise revision notes.

Rules:
- Base factual claims on the provided material.
- Do not invent information.
- Clearly state if requested information is missing.
- Keep the explanation student-friendly.
- Use headings and bullet points.

STUDY MATERIAL:
<study_material>
{text}
</study_material>
"""

        ai_result = ask_gemini(prompt)

        if not ai_result:
            ai_result = (
                "The AI service is temporarily unavailable. "
                "Please try again later."
            )

        return show_result(
            title="Study Material Analyzer",
            subtitle="AI-powered analysis of your study material",
            heading="📚 Your Study Notes",
            result=ai_result
        )

    except ValueError as error:
        return show_result(
            title="Upload Error",
            subtitle="Please check your uploaded file",
            heading="⚠️ Unable to Analyze PDF",
            result=str(error)
        ), 400

    except Exception as error:
        print("STUDY MATERIAL ERROR:", error)

        return show_result(
            title="Error",
            subtitle="Something went wrong",
            heading="⚠️ An Error Occurred",
            result="CampusMate AI could not process this PDF."
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

        question = request.form.get(
            "question",
            ""
        ).strip()

        if not question:
            raise ValueError("Please enter your question.")

        file_path = save_uploaded_pdf(
            request.files["file"],
            prefix="ask_notes_"
        )

        text = read_and_limit_pdf(file_path)

        prompt = f"""
You are CampusMate AI, an academic assistant.

Answer the student's question using ONLY the provided notes.

Rules:
1. Use information supported by the notes.
2. Do not invent facts or quotations.
3. Explain the answer in student-friendly language.
4. If the answer is not present, say:
   "I couldn't find the answer in the uploaded notes."
5. Start with a direct answer, followed by a brief explanation.

STUDY MATERIAL:
<study_material>
{text}
</study_material>

STUDENT QUESTION:
<student_question>
{question}
</student_question>
"""

        answer = ask_gemini(prompt)

        if not answer:
            answer = (
                "The AI service is temporarily unavailable. "
                "Please try again."
            )

        return show_result(
            title="Ask Your Notes",
            subtitle="Get answers from your study material",
            heading="🤖 CampusMate AI's Answer",
            result=answer,
            question=question
        )

    except ValueError as error:
        return show_result(
            title="Ask Your Notes",
            subtitle="Please check your question and PDF",
            heading="⚠️ Unable to Answer",
            result=str(error)
        ), 400

    except Exception as error:
        print("ASK YOUR NOTES ERROR:", error)

        return show_result(
            title="Ask Your Notes",
            subtitle="Something went wrong",
            heading="⚠️ An Error Occurred",
            result="CampusMate AI could not process your question.",
            question=request.form.get("question", "").strip()
        ), 500


# ==========================================================
# QUIZ STORAGE HELPERS
# ==========================================================

def cleanup_old_quizzes():
    """Remove expired quiz data from server memory."""

    current_time = time.time()

    expired_ids = [
        quiz_id
        for quiz_id, quiz_data in QUIZ_STORE.items()
        if current_time - quiz_data["created_at"]
        > QUIZ_EXPIRY_SECONDS
    ]

    for quiz_id in expired_ids:
        QUIZ_STORE.pop(quiz_id, None)


def extract_json_from_response(response_text):
    """Parse JSON, including JSON surrounded by code fences."""

    cleaned = response_text.strip()

    cleaned = re.sub(
        r"^```(?:json)?\s*",
        "",
        cleaned,
        flags=re.IGNORECASE
    )

    cleaned = re.sub(
        r"\s*```$",
        "",
        cleaned
    )

    try:
        return json.loads(cleaned)

    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")

        if start == -1 or end == -1 or end <= start:
            raise ValueError(
                "The AI did not return valid quiz JSON."
            )

        return json.loads(cleaned[start:end + 1])


def validate_questions(data, requested_count):
    """Validate every generated question before displaying it."""

    if not isinstance(data, dict):
        raise ValueError("Invalid quiz response from the AI.")

    questions = data.get("questions")

    if not isinstance(questions, list):
        raise ValueError(
            "The AI response does not contain a questions list."
        )

    if len(questions) != requested_count:
        raise ValueError(
            f"The AI generated {len(questions)} questions "
            f"instead of {requested_count}. Please try again."
        )

    validated = []

    for index, item in enumerate(questions):
        if not isinstance(item, dict):
            raise ValueError("An invalid question was generated.")

        question_text = item.get("question")
        options = item.get("options")
        answer = item.get("answer")
        explanation = item.get("explanation", "")

        if not isinstance(question_text, str) or not question_text.strip():
            raise ValueError(
                f"Question {index + 1} has no question text."
            )

        if (
            not isinstance(options, list)
            or len(options) != 4
            or not all(
                isinstance(option, str) and option.strip()
                for option in options
            )
        ):
            raise ValueError(
                f"Question {index + 1} must have four options."
            )

        # Accept only an integer answer index from 0 to 3.
        # bool is excluded because bool is a subclass of int.
        if (
            not isinstance(answer, int)
            or isinstance(answer, bool)
            or answer not in range(4)
        ):
            raise ValueError(
                f"Question {index + 1} has an invalid answer key."
            )

        if not isinstance(explanation, str):
            explanation = ""

        validated.append({
            "question": question_text.strip(),
            "options": [option.strip() for option in options],
            "answer": answer,
            "explanation": explanation.strip()
        })

    return validated


# ==========================================================
# QUIZ HTML TEMPLATE
# ==========================================================

QUIZ_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">

    <meta name="viewport"
          content="width=device-width, initial-scale=1.0">

    <title>AI Quiz Generator | CampusMate AI</title>

    <style>
        * {
            box-sizing: border-box;
        }

        body {
            margin: 0;
            padding: 24px 16px;
            font-family: Arial, sans-serif;
            background: #f5f7fb;
            color: #222;
        }

        .container {
            max-width: 850px;
            margin: auto;
        }

        .header, .question-card, .result-card {
            background: white;
            padding: 24px;
            border-radius: 16px;
            margin-bottom: 20px;
            box-shadow: 0 5px 20px rgba(0,0,0,.06);
        }

        h1 {
            color: #4f46e5;
            margin-top: 0;
        }

        .question-card h3 {
            margin-top: 0;
            line-height: 1.5;
        }

        .option {
            display: flex;
            align-items: flex-start;
            gap: 10px;
            padding: 13px;
            margin: 10px 0;
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 9px;
            cursor: pointer;
            line-height: 1.5;
        }

        .option:hover {
            background: #eef2ff;
        }

        .option input {
            margin-top: 4px;
            flex-shrink: 0;
        }

        .button {
            border: none;
            display: inline-block;
            padding: 13px 22px;
            background: #4f46e5;
            color: white;
            font-size: 16px;
            border-radius: 9px;
            cursor: pointer;
        }

        .button:disabled {
            opacity: .65;
            cursor: wait;
        }

        .secondary {
            background: #334155;
            text-decoration: none;
            margin-left: 8px;
        }

        .message {
            padding: 14px;
            border-radius: 9px;
            margin: 16px 0;
            display: none;
            line-height: 1.5;
        }

        .error {
            color: #991b1b;
            background: #fee2e2;
        }

        .success {
            color: #166534;
            background: #dcfce7;
        }

        .correct {
            border-left: 5px solid #16a34a;
            background: #f0fdf4;
        }

        .incorrect {
            border-left: 5px solid #dc2626;
            background: #fef2f2;
        }

        .answer-review {
            margin-top: 14px;
            padding: 14px;
            border-radius: 8px;
            line-height: 1.6;
        }

        .score {
            font-size: 24px;
            font-weight: bold;
            color: #4f46e5;
        }

        @media (max-width: 600px) {
            .header, .question-card, .result-card {
                padding: 18px;
            }

            .secondary {
                margin: 12px 0 0;
            }
        }
    </style>
</head>

<body>
<div class="container">

    <div class="header">
        <h1>📝 CampusMate AI Quiz</h1>

        <p>
            Answer the questions generated from your study material.
        </p>

        <p>
            Questions: <strong>{{ questions|length }}</strong>
            &nbsp; | &nbsp;
            Difficulty: <strong>{{ difficulty }}</strong>
        </p>
    </div>

    <div id="message" class="message" role="alert"></div>

    <form id="quizForm">

        <input
            type="hidden"
            name="quiz_id"
            value="{{ quiz_id }}"
        >

        {% for item in questions %}

            {% set question_index = loop.index0 %}

            <section class="question-card"
                     id="question-{{ question_index }}">

                <h3>
                    {{ question_index + 1 }}.
                    {{ item.question }}
                </h3>

                {% for option in item.options %}

                    <label class="option">

                        <input
                            type="radio"
                            name="q{{ question_index }}"
                            value="{{ loop.index0 }}"
                        >

                        <span>
                            {{ ["A", "B", "C", "D"][loop.index0] }}.
                            {{ option }}
                        </span>

                    </label>

                {% endfor %}

            </section>

        {% endfor %}

        <button
            type="submit"
            id="submitButton"
            class="button"
        >
            Submit Quiz
        </button>

        <a href="/" class="button secondary">
            Back to Home
        </a>

    </form>

    <section
        id="results"
        class="result-card"
        style="display: none;"
        aria-live="polite"
    ></section>

</div>

<script>
(function () {
    const quizForm = document.getElementById("quizForm");
    const submitButton = document.getElementById("submitButton");
    const message = document.getElementById("message");
    const results = document.getElementById("results");

    function showMessage(text, type) {
        message.textContent = text;
        message.className = "message " + type;
        message.style.display = "block";
    }

    function addTextElement(parent, tag, text, className) {
        const element = document.createElement(tag);
        element.textContent = text;

        if (className) {
            element.className = className;
        }

        parent.appendChild(element);
        return element;
    }

    quizForm.addEventListener("change", function (event) {
        if (event.target.matches('input[type="radio"]')) {
            message.style.display = "none";
        }
    });

    quizForm.addEventListener("submit", async function (event) {
        event.preventDefault();

        if (submitButton.disabled) {
            return;
        }

        const questionCards = Array.from(
            quizForm.querySelectorAll(".question-card")
        );

        const unanswered = [];

        questionCards.forEach(function (card, index) {
            const selected = card.querySelector(
                'input[type="radio"]:checked'
            );

            if (!selected) {
                unanswered.push(index + 1);
            }
        });

        if (unanswered.length > 0) {
            showMessage(
                "You have not answered question(s): " +
                unanswered.join(", ") +
                ". Please answer them before submitting.",
                "error"
            );

            const firstUnanswered = document.getElementById(
                "question-" + (unanswered[0] - 1)
            );

            if (firstUnanswered) {
                firstUnanswered.scrollIntoView({
                    behavior: "smooth",
                    block: "center"
                });
            }

            return;
        }

        submitButton.disabled = true;
        submitButton.textContent = "Submitting...";

        showMessage(
            "Checking your answers...",
            "success"
        );

        try {
            const formData = new FormData(quizForm);

            const response = await fetch("/quiz/submit", {
                method: "POST",
                body: formData
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(
                    data.error || "Unable to submit the quiz."
                );
            }

            message.style.display = "none";

            results.replaceChildren();
            results.style.display = "block";

            addTextElement(
                results,
                "h2",
                "🎉 Quiz Results"
            );

            addTextElement(
                results,
                "p",
                "You answered " + data.answered +
                " out of " + data.total + " questions."
            );

            addTextElement(
                results,
                "p",
                "Unanswered questions: " + data.unanswered
            );

            addTextElement(
                results,
                "p",
                "Score: " + data.score + " / " + data.total,
                "score"
            );

            const percentage = data.total > 0
                ? Math.round((data.score / data.total) * 100)
                : 0;

            addTextElement(
                results,
                "p",
                "Percentage: " + percentage + "%"
            );

            addTextElement(
                results,
                "h3",
                "Answer Review"
            );

            data.results.forEach(function (item) {
                const review = document.createElement("div");

                review.className =
                    "answer-review " +
                    (item.is_correct ? "correct" : "incorrect");

                addTextElement(
                    review,
                    "h4",
                    "Question " + item.number + ": " + item.question
                );

                addTextElement(
                    review,
                    "p",
                    "Your answer: " +
                    (item.selected_answer || "Not answered")
                );

                addTextElement(
                    review,
                    "p",
                    "Correct answer: " + item.correct_answer
                );

                if (item.explanation) {
                    addTextElement(
                        review,
                        "p",
                        "Explanation: " + item.explanation
                    );
                }

                addTextElement(
                    review,
                    "strong",
                    item.is_correct ? "✓ Correct" : "✗ Incorrect"
                );

                results.appendChild(review);
            });

            questionCards.forEach(function (card) {
                card.querySelectorAll(
                    'input[type="radio"]'
                ).forEach(function (input) {
                    input.disabled = true;
                });
            });

            submitButton.style.display = "none";

            results.scrollIntoView({
                behavior: "smooth",
                block: "start"
            });

        } catch (error) {
            showMessage(
                error.message ||
                "Something went wrong while submitting your quiz.",
                "error"
            );

            submitButton.disabled = false;
            submitButton.textContent = "Submit Quiz";
        }
    });
})();
</script>

</body>
</html>
"""


# ==========================================================
# FEATURE 3: AI QUIZ GENERATOR
# ==========================================================

@app.route("/quiz", methods=["POST"])
def generate_quiz():
    print("\n========== AI QUIZ GENERATOR ==========")

    try:
        if "file" not in request.files:
            raise ValueError("Please select a PDF file.")

        file = request.files["file"]

        requested_count_text = request.form.get(
            "num_questions",
            "5"
        )

        difficulty = request.form.get(
            "difficulty",
            "Easy"
        ).strip().title()

        if requested_count_text not in {"5", "10", "15"}:
            raise ValueError(
                "Please select 5, 10 or 15 questions."
            )

        if difficulty not in {"Easy", "Medium", "Hard"}:
            raise ValueError(
                "Please select Easy, Medium or Hard difficulty."
            )

        requested_count = int(requested_count_text)

        file_path = save_uploaded_pdf(
            file,
            prefix="quiz_"
        )

        text = read_and_limit_pdf(file_path)

        prompt = f"""
You are CampusMate AI, an academic quiz generator.

Create exactly {requested_count} multiple-choice questions
from the provided study material.

Difficulty: {difficulty}

Return ONLY valid JSON in this exact format:

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
      "answer": 0,
      "explanation": "Brief explanation"
    }}
  ]
}}

IMPORTANT RULES:

1. Generate exactly {requested_count} questions.
2. Every question must have exactly four options.
3. The answer must be an integer from 0 to 3.
4. The answer integer identifies the correct option:
   0 = first option, 1 = second, 2 = third, 3 = fourth.
5. Each question must have one correct answer.
6. Include a brief explanation of the correct answer.
7. Base the questions and answers on the provided material.
8. Do not invent facts absent from the material.
9. Match the requested difficulty.
10. Do not include Markdown fences or text outside the JSON.
11. Use different questions rather than repeating the same fact.
12. Ensure every question is clear and every answer key is valid.

STUDY MATERIAL:
<study_material>
{text}
</study_material>
"""

        response_text = ask_gemini(prompt)

        if not response_text:
            raise RuntimeError(
                "The AI service is temporarily unavailable. "
                "Please try generating the quiz again."
            )

        data = extract_json_from_response(response_text)

        questions = validate_questions(
            data,
            requested_count
        )

        cleanup_old_quizzes()

        quiz_id = secrets.token_urlsafe(24)

        # Store correct answers on the server.
        QUIZ_STORE[quiz_id] = {
            "questions": questions,
            "difficulty": difficulty,
            "created_at": time.time()
        }

        print(
            f"Quiz generated successfully: "
            f"{len(questions)} questions."
        )

        return render_template_string(
            QUIZ_TEMPLATE,
            quiz_id=quiz_id,
            questions=questions,
            difficulty=difficulty
        )

    except ValueError as error:
        return show_result(
            title="AI Quiz Generator",
            subtitle="Please check your PDF and quiz settings",
            heading="⚠️ Could Not Generate Quiz",
            result=str(error)
        ), 400

    except Exception as error:
        print("QUIZ GENERATION ERROR:", error)

        return show_result(
            title="AI Quiz Generator",
            subtitle="Something went wrong",
            heading="⚠️ Quiz Generation Failed",
            result=(
                "CampusMate AI could not generate your quiz. "
                "Please check the terminal for details and try again."
            )
        ), 500


# ==========================================================
# QUIZ SUBMISSION AND SCORING
# ==========================================================

@app.route("/quiz/submit", methods=["POST"])
def submit_quiz():
    print("\n========== QUIZ SUBMISSION ==========")

    try:
        quiz_id = request.form.get(
            "quiz_id",
            ""
        ).strip()

        if not quiz_id:
            return jsonify({
                "error": "Quiz ID is missing. Please generate a new quiz."
            }), 400

        cleanup_old_quizzes()

        quiz_data = QUIZ_STORE.get(quiz_id)

        if not quiz_data:
            return jsonify({
                "error": (
                    "This quiz has expired or the server restarted. "
                    "Please generate a new quiz."
                )
            }), 410

        questions = quiz_data["questions"]

        score = 0
        answered = 0
        results = []

        for index, item in enumerate(questions):
            # Each question has its own radio name:
            # q0, q1, q2, and so on.
            field_name = f"q{index}"

            selected_value = request.form.get(field_name)

            selected_index = None

            if selected_value is not None:
                try:
                    selected_index = int(selected_value)
                except (TypeError, ValueError):
                    selected_index = None

            # A valid answer must be one of the four option indexes.
            if (
                selected_index is not None
                and selected_index in range(4)
            ):
                answered += 1

            is_correct = (
                selected_index is not None
                and selected_index == item["answer"]
            )

            if is_correct:
                score += 1

            selected_answer = None

            if (
                selected_index is not None
                and selected_index in range(4)
            ):
                selected_answer = item["options"][selected_index]

            correct_answer = item["options"][item["answer"]]

            results.append({
                "number": index + 1,
                "question": item["question"],
                "selected_answer": selected_answer,
                "correct_answer": correct_answer,
                "is_correct": is_correct,
                "explanation": item["explanation"]
            })

        total = len(questions)
        unanswered = total - answered

        print(
            f"Answered: {answered}/{total}; "
            f"Score: {score}/{total}"
        )

        return jsonify({
            "success": True,
            "total": total,
            "answered": answered,
            "unanswered": unanswered,
            "score": score,
            "results": results
        })

    except Exception as error:
        print("QUIZ SUBMISSION ERROR:", error)

        return jsonify({
            "error": "The quiz could not be scored. Please try again."
        }), 500


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
            "Please choose a smaller PDF."
        )
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