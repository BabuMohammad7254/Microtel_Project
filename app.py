
    from flask import Flask, request, render_template, send_file
    import sqlite3
    import io
    import fitz  # PyMuPDF
    import re

    app = Flask(__name__)

    def extract_data_from_pdf(file_bytes):
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()

        data = {
            'confirmation_number': None,
            'first_name': None,
            'last_name': None,
            'room': None,
            'arrival': None,
            'departure': None
        }

        name_match = re.search(r'Name[^a-zA-Z0-9]*([^
]+)', text, re.IGNORECASE)
        if name_match:
            full_name = name_match.group(1).strip()
            parts = [p.strip() for p in full_name.split(',')]
            if len(parts) == 2:
                data['first_name'], data['last_name'] = parts
            else:
                data['first_name'] = full_name

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

        return data

    @app.route("/portal", methods=["GET", "POST"])
    def portal():
        message = ""
        pdf_stream = None
        pdf_name = ""

        if request.method == "POST":
            action = request.form.get("action")

            if action == "upload":
                file = request.files.get("pdf")
                if file:
                    file_bytes = file.read()
                    data = extract_data_from_pdf(file_bytes)

                    if not data['confirmation_number']:
                        message = "Confirmation Number not found in PDF."
                    else:
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
                        message = f"Uploaded: {data['first_name']} {data['last_name']}"
                else:
                    message = "No file uploaded."

            elif action == "retrieve":
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
                    pdf_name = f"{confirmation_number}_{first_name}_{last_name}.pdf"
                    pdf_stream = io.BytesIO(pdf_data)
                else:
                    message = "No matching PDF found."

        return render_template("portal.html", message=message, pdf_stream=pdf_stream, pdf_name=pdf_name)

    if __name__ == "__main__":
        app.run()
