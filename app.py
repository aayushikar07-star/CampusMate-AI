from flask import Flask, render_template, request
import os
import time
import random

from pypdf import PdfReader
from dotenv import load_dotenv
from google import genai


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ============================================================
# GEMINI SETUP
# ============================================================

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError(
        "GEMINI_API_KEY was not found. "
        "Please check your .env file."
    )

client = genai.Client(api_key=api_key)


# ============================================================
# GEMINI MODELS
# ============================================================

# If one model is temporarily unavailable, CampusMate AI
# automatically tries the next model.

GEMINI_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-2.5-flash",
]


# ============================================================
# HOME PAGE
# ============================================================

@app.route("/")
def home():
    return render_template("index.html")


# ============================================================
# PDF UPLOAD + AI ANALYSIS
# ============================================================

@app.route("/upload", methods=["POST"])
def upload_file():

    print("\n======================================")
    print("UPLOAD REQUEST RECEIVED")
    print("======================================")

    # --------------------------------------------------------
    # CHECK FILE
    # --------------------------------------------------------

    if "file" not in request.files:

        print("ERROR: No file field found.")

        return """
        <h2>No file selected.</h2>
        <a href="/">← Go Back</a>
        """

    file = request.files["file"]

    if file.filename == "":

        print("ERROR: Empty filename.")

        return """
        <h2>No file selected.</h2>
        <a href="/">← Go Back</a>
        """

    # --------------------------------------------------------
    # CHECK PDF
    # --------------------------------------------------------

    if not file.filename.lower().endswith(".pdf"):

        print("ERROR: File is not a PDF.")

        return """
        <h2>Please upload a PDF file.</h2>
        <a href="/">← Go Back</a>
        """

    # --------------------------------------------------------
    # SAVE PDF
    # --------------------------------------------------------

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

    # ========================================================
    # READ PDF
    # ========================================================

    try:

        print("2. Starting PDF reading...")

        reader = PdfReader(file_path)

        text = ""

        total_pages = len(reader.pages)

        print("Total pages:", total_pages)

        for page_number, page in enumerate(
            reader.pages,
            start=1
        ):

            print(
                f"Reading page "
                f"{page_number}/{total_pages}..."
            )

            page_text = page.extract_text()

            if page_text:

                text += page_text + "\n"

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

    # ========================================================
    # CHECK EXTRACTED TEXT
    # ========================================================

    if not text.strip():

        print("ERROR: No readable text found.")

        return """
        <h2>Unable to read this PDF</h2>

        <p>
        This PDF may contain scanned images instead
        of selectable text.
        </p>

        <p>
        Please try a text-based PDF.
        </p>

        <a href="/">← Try Another PDF</a>
        """

    # ========================================================
    # LIMIT TEXT
    # ========================================================

    MAX_TEXT_LENGTH = 20000

    if len(text) > MAX_TEXT_LENGTH:

        print(
            f"PDF is large. Limiting text "
            f"from {len(text)} to "
            f"{MAX_TEXT_LENGTH} characters."
        )

        text = text[:MAX_TEXT_LENGTH]

    # ========================================================
    # GEMINI PROMPT
    # ========================================================

    prompt = f"""
You are CampusMate AI, an AI-powered academic
assistant designed for college students.

Analyze the following study material and provide
useful, exam-oriented information.

Use these sections:

1. SUMMARY

Give a simple and clear summary of the material.

2. IMPORTANT POINTS

List the most important concepts, definitions,
formulas, facts, or ideas that a student should
remember.

3. EXAM-ORIENTED QUESTIONS

Create 5 useful questions based only on the
provided material.

Include a mixture of:
- Short-answer questions
- Conceptual questions
- Descriptive questions

4. KEY TERMS

List important technical terms and briefly
explain each one.

5. QUICK REVISION

Give a short revision section that a student
can read before an exam.

IMPORTANT RULES:

- Use only information from the provided study material.
- Do not invent information.
- Keep the explanation student-friendly.
- Use headings and bullet points.
- Make the response useful for exam preparation.

STUDY MATERIAL:

{text}
"""

    # ========================================================
    # TRY GEMINI MODELS
    # ========================================================

    ai_result = None
    successful_model = None

    print("\n======================================")
    print("STARTING GEMINI AI ANALYSIS")
    print("======================================")

    for model_name in GEMINI_MODELS:

        print(
            f"\nTrying model: {model_name}"
        )

        # Each model gets up to 2 attempts.
        for attempt in range(1, 3):

            try:

                print(
                    f"Attempt {attempt}/2"
                )

                interaction = client.interactions.create(
                    model=model_name,
                    input=prompt
                )

                ai_result = interaction.output_text

                if not ai_result:

                    raise ValueError(
                        "Gemini returned an empty response."
                    )

                successful_model = model_name

                print(
                    f"SUCCESS! Model used: "
                    f"{model_name}"
                )

                break

            except Exception as e:

                error_message = str(e)

                print(
                    f"Model {model_name} failed."
                )

                print(
                    "Error:",
                    error_message
                )

                # Wait before retrying the same model.
                if attempt == 1:

                    delay = (
                        2 + random.uniform(0, 1)
                    )

                    print(
                        f"Retrying "
                        f"{model_name} "
                        f"in {delay:.1f} seconds..."
                    )

                    time.sleep(delay)

        # Stop trying models once one succeeds.
        if ai_result:

            break

    # ========================================================
    # IF ALL MODELS FAILED
    # ========================================================

    if not ai_result:

        print(
            "\nALL GEMINI MODELS FAILED."
        )

        ai_result = """
CampusMate AI could not analyze the document
right now.

The AI service appears to be temporarily busy.

Please wait a little while and try again.

Your PDF upload and text extraction are working
correctly; the issue is with the AI service
availability.
"""

    # ========================================================
    # FORMAT RESULT SAFELY
    # ========================================================

    formatted_result = (
        ai_result
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br>")
    )

    # ========================================================
    # RESULT PAGE
    # ========================================================

    model_display = (
        successful_model
        if successful_model
        else "Temporarily unavailable"
    )

    return f"""
    <!DOCTYPE html>

    <html lang="en">

    <head>

        <meta charset="UTF-8">

        <meta name="viewport"
              content="width=device-width,
                       initial-scale=1.0">

        <title>
            CampusMate AI - Analysis
        </title>

        <style>

            * {{
                box-sizing: border-box;
            }}

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

            .header h1 {{
                margin: 0;
                color: #4f46e5;
            }}

            .header p {{
                color: #666;
            }}

            .model {{
                margin-top: 10px;
                font-size: 13px;
                color: #777;
            }}

            .result {{
                background: white;
                padding: 30px;
                border-radius: 15px;
                box-shadow:
                    0 5px 20px
                    rgba(0,0,0,0.06);

                line-height: 1.7;
                font-size: 16px;

                overflow-wrap: break-word;
            }}

            .back-button {{
                display: inline-block;
                margin-top: 20px;
                padding: 12px 20px;

                background: #4f46e5;
                color: white;

                text-decoration: none;
                border-radius: 8px;
            }}

            .back-button:hover {{
                background: #3730a3;
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

                <div class="model">
                    AI Model: {model_display}
                </div>

            </div>

            <div class="result">

                {formatted_result}

            </div>

            <a
                class="back-button"
                href="/"
            >
                ← Analyze Another PDF
            </a>

        </div>

    </body>

    </html>
    """


# ============================================================
# RUN FLASK
# ============================================================

if __name__ == "__main__":

    print("\n======================================")
    print("CampusMate AI is starting...")
    print("Open: http://127.0.0.1:5000")
    print("======================================\n")

    app.run(debug=True)
