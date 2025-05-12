from flask import Flask, request, render_template, send_file
import sqlite3
import io
import fitz  # PyMuPDF
import re

app = Flask(__name__)

# Extract attributes from PDF text
def extract_data_from_pdf(file_bytes):
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    print("=== Extracted PDF Text ===")
    print(text)

    data = {
        'confirmation_number': None,
        'first_name': None,
        'last_name': None,
        'room': None,
        'arrival': None,
        'departure': None
    }

    # Extract full name and split into first and last
    name_pattern = r'Name[^a-zA-Z0-9]*([^\n\r]+)'
    name_match = re.search(name_pattern, text, re.IGNORECASE)
    if name_match:
        full_name = name_match.group(1).strip()
        parts = [p.strip() for p in full_name.split(',')]
        if len(parts) == 2:
            data['first_name'], data['last_name'] = parts
        else:
            data['first_name'] = full_name

    # Other fields
    patterns = {
        'confirmation_number': r'Confirmation\s*Number[^a-zA-Z0-9]*([\w\-\/]+)',
        'room': r'Room[^a-zA-Z0-9]*([^\n\r]+)',
        'arrival': r'Arrival[^a-zA-Z0-9]*([^\n\r]+)',
        'departure': r'Departure[^a-zA-Z0-9]*([^\n\r]+)'
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            data[key] = match.group(1).strip()

    print("=== Extracted Data ===")
    print(data)

    return data

@app.route("/", methods=["GET", "POST"])
def upload():
    if request.method == "POST":
        file = request.files.get("pdf")
        if not file:
            return "No file uploaded.", 400

        file_bytes = file.read()
        data = extract_data_from_pdf(file_bytes)

        if not data['confirmation_number']:
            return "Confirmation Number not found in PDF."

        conn = sqlite3.connect('pdf_storage.db')
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                confirmation_number TEXT,
                first_name TEXT,
                last_name TEXT,
                room TEXT,
                arrival TEXT,
                departure TEXT,
                pdf BLOB
            )
        ''')

        cursor.execute('''
            INSERT INTO documents (confirmation_number, first_name, last_name, room, arrival, departure, pdf)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['confirmation_number'],
            data['first_name'],
            data['last_name'],
            data['room'],
            data['arrival'],
            data['departure'],
            file_bytes
        ))

        conn.commit()
        conn.close()

        return f"PDF uploaded for {data['first_name']} {data['last_name']} (Confirmation: {data['confirmation_number']})"

    return render_template("upload.html")


@app.route("/retrieve", methods=["GET", "POST"])
def retrieve():
    if request.method == "POST":
        filters = {
            'confirmation_number': request.form.get("confirmation_number"),
            'first_name': request.form.get("first_name"),
            'last_name': request.form.get("last_name")
        }

        query = "SELECT confirmation_number, first_name, last_name, pdf FROM documents WHERE 1=1"
        params = []

        for key, value in filters.items():
            if value:
                query += f" AND {key} LIKE ?"
                params.append(f"%{value}%")

        conn = sqlite3.connect('pdf_storage.db')
        cursor = conn.cursor()
        cursor.execute(query, params)
        result = cursor.fetchone()
        conn.close()

        if result:
            confirmation_number, first_name, last_name, pdf_data = result
            filename = f"{confirmation_number}_{first_name}_{last_name}.pdf"
            return send_file(
                io.BytesIO(pdf_data),
                download_name=filename,
                as_attachment=False,
                mimetype='application/pdf'
            )
        else:
            return "No matching PDF found."

    return render_template("retrieve.html")

if __name__ == "__main__":
    app.run(debug=True)
