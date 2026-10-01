from flask import Flask, render_template, request
import os
from pypdf import PdfReader

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload_file():

    if "file" not in request.files:
        return "No file selected"

    file = request.files["file"]

    if file.filename == "":
        return "No file selected"

    if not file.filename.lower().endswith(".pdf"):
        return "Please upload a PDF file"

    file_path = os.path.join(
        app.config["UPLOAD_FOLDER"],
        file.filename
    )

    file.save(file_path)

    # Extract text from PDF
    reader = PdfReader(file_path)

    text = ""

    for page in reader.pages:
        page_text = page.extract_text()

        if page_text:
            text += page_text + "\n"

    return f"""
    <h1>PDF Uploaded Successfully! ✅</h1>

    <h2>Extracted Text:</h2>

    <pre>{text}</pre>

    <br>

    <a href="/">← Back</a>
    """


if __name__ == "__main__":
    app.run(debug=True)