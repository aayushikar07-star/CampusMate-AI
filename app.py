from flask import Flask, render_template, request
import os
import time
import random

from pypdf import PdfReader
from dotenv import load_dotenv
from google import genai

load_dotenv()

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# --------------------------------------------------
# GEMINI SETUP
# --------------------------------------------------

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError(
        "GEMINI_API_KEY was not found. "
        "Please check your .env file."
    )

client = genai.Client(api_key=api_key)

GEMINI_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-2.5-flash",
]


# --------------------------------------------------
# HOME PAGE
# --------------------------------------------------

@app.route("/")
def home():
    return render_template("index.html")


# --------------------------------------------------
# FUNCTION TO READ PDF
# --------------------------------------------------

def extract_pdf_text(file_path):

    reader = PdfReader(file_path)

    text = ""

    total_pages = len(reader.pages)

    print("Total pages:", total_pages)

    for page_number, page in enumerate(reader.pages, start=1):

        print(
            f"Reading page "
            f"{page_number}/{total_pages}..."
        )

        page_text = page.extract_text()

        if page_text:
            text += page_text + "\n"

    return text


# --------------------------------------------------
# GEMINI FUNCTION
# --------------------------------------------------

def ask_gemini(prompt):

    print("\n======================================")
    print("STARTING GEMINI AI")
    print("======================================")

    for model_name in GEMINI_MODELS:

        print(f"\nTrying model: {model_name}")

        for attempt in range(1, 3):

            try:

                print(
                    f"Attempt {attempt}/2"
                )

                interaction = client.interactions.create(
                    model=model_name,
                    input=prompt
                )

                result = interaction.output_text

                if not result:
                    raise ValueError(
                        "Gemini returned an empty response."
                    )

                print(
                    f"SUCCESS! Model used: "
                    f"{model_name}"
                )

                return result

            except Exception as e:

                print(
                    f"Model {model_name} failed."
                )

                print(
                    "Error:",
                    str(e)
                )

                if attempt == 1:

                    delay = 2 + random.uniform(0, 1)

                    print(
                        f"Retrying in "
                        f"{delay:.1f} seconds..."
                    )

                    time.sleep(delay)

    return None


# --------------------------------------------------
# STUDY MATERIAL ANALYZER
# --------------------------------------------------

@app.route("/upload", methods=["POST"])
def upload_file():

    print("\n======================================")
    print("STUDY MATERIAL UPLOAD")
    print("======================================")

    if "file" not in request.files:

        return """
        <h2>No file selected.</h2>
        <a href="/">← Go Back</a>
        """

    file = request.files["file"]

    if file.filename == "":

        return """
        <h2>No file selected.</h2>
        <a href="/">← Go Back</a>
        """

    if not file.filename.lower().endswith(".pdf"):

        return """
        <h2>Please upload a PDF file.</h2>
        <a href="/">← Go Back</a>
        """

    try:

        file_path = os.path.join(
            app.config["UPLOAD_FOLDER"],
            file.filename
        )

        file.save(file_path)

        print("1. File saved successfully.")
        print("File:", file.filename)

    except Exception as e:

        print("FILE SAVE ERROR:", e)

        return f"""
        <h2>Could not save the file.</h2>
        <p>{str(e)}</p>
        <a href="/">← Go Back</a>
        """

    try:

        print("2. Starting PDF reading...")

        text = extract_pdf_text(file_path)

        print("3. PDF text extracted.")
        print(
            "4. Extracted text length:",
            len(text)
        )

    except Exception as e:

        print("PDF READING ERROR:", e)

        return f"""
        <h2>Unable to read this PDF.</h2>
        <p>{str(e)}</p>
        <a href="/">← Go Back</a>
        """

    if not text.strip():

        return """
        <h2>Unable to read this PDF</h2>

        <p>
        This PDF may contain scanned images
        instead of selectable text.
        </p>

        <a href="/">← Try Another PDF</a>
        """

    # Prevent extremely large requests
    MAX_TEXT_LENGTH = 20000

    if len(text) > MAX_TEXT_LENGTH:

        text = text[:MAX_TEXT_LENGTH]

        print(
            "PDF text limited to",
            MAX_TEXT_LENGTH,
            "characters."
        )

    prompt = f"""
You are CampusMate AI, an AI-powered
academic assistant for college students.

Analyze the following study material.

Provide:

1. SUMMARY

Give a simple and clear summary.

2. IMPORTANT POINTS

List important concepts,
definitions, formulas and facts.

3. EXAM-ORIENTED QUESTIONS

Create 5 useful questions
based only on the material.

4. KEY TERMS

List important technical terms
and explain them briefly.

5. QUICK REVISION

Give a short revision section.

IMPORTANT:

- Use only information from the PDF.
- Do not invent information.
- Keep the explanation student-friendly.
- Use headings and bullet points.

STUDY MATERIAL:

{text}
"""

    ai_result = ask_gemini(prompt)

    if not ai_result:

        ai_result = """
CampusMate AI could not analyze the PDF
right now.

The AI service may be temporarily busy.

Please try again in a few moments.
"""

    formatted_result = (
        ai_result
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br>")
    )

    return f"""
    <!DOCTYPE html>

    <html>

    <head>

        <meta charset="UTF-8">

        <meta name="viewport"
              content="width=device-width,
                       initial-scale=1.0">

        <title>
            CampusMate AI - Analysis
        </title>

        <style>

            body {{
                font-family: Arial, sans-serif;
                background: #f5f7fb;
                margin: 0;
                padding: 30px;
                color: #222;
            }}

            .container {{
                max-width: 1000px;
                margin: auto;
            }}

            .header {{
                background: white;
                padding: 25px;
                border-radius: 15px;
                margin-bottom: 20px;
                box-shadow:
                    0 5px 20px
                    rgba(0,0,0,0.06);
            }}

            h1 {{
                color: #4f46e5;
            }}

            .result {{
                background: white;
                padding: 30px;
                border-radius: 15px;
                line-height: 1.7;
                box-shadow:
                    0 5px 20px
                    rgba(0,0,0,0.06);
            }}

            .button {{
                display: inline-block;
                margin-top: 20px;
                padding: 12px 20px;
                background: #4f46e5;
                color: white;
                text-decoration: none;
                border-radius: 8px;
            }}

        </style>

    </head>

    <body>

        <div class="container">

            <div class="header">

                <h1>
                    🤖 CampusMate AI
                </h1>

                <p>
                    AI analysis of your study material
                </p>

            </div>

            <div class="result">

                {formatted_result}

            </div>

            <a href="/" class="button">
                ← Analyze Another PDF
            </a>

        </div>

    </body>

    </html>
    """


# --------------------------------------------------
# ASK YOUR NOTES
# --------------------------------------------------

@app.route("/ask", methods=["POST"])
def ask_notes():

    print("\n======================================")
    print("ASK YOUR NOTES")
    print("======================================")

    if "file" not in request.files:

        return """
        <h2>No PDF selected.</h2>
        <a href="/">← Go Back</a>
        """

    file = request.files["file"]

    question = request.form.get(
        "question",
        ""
    ).strip()

    if file.filename == "":

        return """
        <h2>Please select a PDF.</h2>
        <a href="/">← Go Back</a>
        """

    if not question:

        return """
        <h2>Please enter a question.</h2>
        <a href="/">← Go Back</a>
        """

    if not file.filename.lower().endswith(".pdf"):

        return """
        <h2>Please upload a PDF file.</h2>
        <a href="/">← Go Back</a>
        """

    try:

        file_path = os.path.join(
            app.config["UPLOAD_FOLDER"],
            "ask_notes_" + file.filename
        )

        file.save(file_path)

        print(
            "PDF saved for Ask Your Notes:",
            file.filename
        )

        text = extract_pdf_text(file_path)

        print(
            "Extracted text length:",
            len(text)
        )

    except Exception as e:

        print(
            "PDF ERROR:",
            str(e)
        )

        return f"""
        <h2>Could not read the PDF.</h2>
        <p>{str(e)}</p>
        <a href="/">← Go Back</a>
        """

    if not text.strip():

        return """
        <h2>No readable text found.</h2>

        <p>
        Please use a PDF containing selectable text.
        </p>

        <a href="/">← Go Back</a>
        """

    MAX_TEXT_LENGTH = 20000

    if len(text) > MAX_TEXT_LENGTH:

        text = text[:MAX_TEXT_LENGTH]

    prompt = f"""
You are CampusMate AI,
an academic assistant for college students.

Answer the student's question using
ONLY the information provided in
the study material below.

STUDY MATERIAL:

{text}

STUDENT QUESTION:

{question}

IMPORTANT RULES:

1. Answer only from the study material.

2. Do not invent facts.

3. If the answer cannot be found
   in the study material, say:

   "I couldn't find the answer
   in the uploaded notes."

4. Keep the answer clear and
   student-friendly.

5. Use bullet points when useful.

6. Explain technical concepts
   simply when possible.
"""

    answer = ask_gemini(prompt)

    if not answer:

        answer = """
Sorry, CampusMate AI could not answer
your question right now.

Please try again in a few moments.
"""

    formatted_answer = (
        answer
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br>")
    )

    return f"""
    <!DOCTYPE html>

    <html>

    <head>

        <meta charset="UTF-8">

        <meta name="viewport"
              content="width=device-width,
                       initial-scale=1.0">

        <title>
            CampusMate AI - Ask Your Notes
        </title>

        <style>

            body {{
                font-family: Arial, sans-serif;
                background: #f5f7fb;
                margin: 0;
                padding: 30px;
            }}

            .container {{
                max-width: 900px;
                margin: auto;
            }}

            .card {{
                background: white;
                padding: 30px;
                border-radius: 15px;
                box-shadow:
                    0 5px 20px
                    rgba(0,0,0,0.06);
            }}

            h1 {{
                color: #4f46e5;
            }}

            .question {{
                background: #eef2ff;
                padding: 15px;
                border-radius: 10px;
                margin: 20px 0;
            }}

            .answer {{
                line-height: 1.7;
                font-size: 16px;
            }}

            .button {{
                display: inline-block;
                margin-top: 20px;
                padding: 12px 20px;
                background: #4f46e5;
                color: white;
                text-decoration: none;
                border-radius: 8px;
            }}

        </style>

    </head>

    <body>

        <div class="container">

            <div class="card">

                <h1>
                    💬 Ask Your Notes
                </h1>

                <div class="question">

                    <strong>
                        Your Question:
                    </strong>

                    <p>
                        {question}
                    </p>

                </div>

                <h2>
                    🤖 CampusMate AI
                </h2>

                <div class="answer">

                    {formatted_answer}

                </div>

                <a href="/" class="button">
                    ← Ask Another Question
                </a>

            </div>

        </div>

    </body>

    </html>
    """


# --------------------------------------------------
# START FLASK
# --------------------------------------------------

if __name__ == "__main__":

    print("\n======================================")
    print("CampusMate AI is starting...")
    print("Open: http://127.0.0.1:5000")
    print("======================================\n")

    app.run(debug=True)