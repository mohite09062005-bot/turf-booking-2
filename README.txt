TURFBOOK - FULL FRONTEND + FLASK BACKEND
=========================================

This package contains:
- index.html: your TurfBook frontend
- app.py: Flask backend + SQLite database + customer/admin authentication
- requirements.txt: Python dependency list

IMPORTANT
---------
Run the website through Flask. Do not open index.html directly and do not
expect GitHub Pages to run Python. Flask serves the frontend and API from
the same address, so customer bookings from different devices are stored in
one shared database when the backend is hosted publicly.

LOCAL SETUP IN VS CODE (WINDOWS)
--------------------------------
1. Extract this ZIP to a folder, for example Desktop\TurfBook.
2. Open VS Code.
3. Select File > Open Folder and choose the extracted TurfBook folder.
4. Open Terminal > New Terminal.
5. Check Python is installed:
       py --version

6. Create a virtual environment:
       py -m venv .venv

7. Activate it in PowerShell:
       .\.venv\Scripts\Activate.ps1

   If PowerShell blocks activation, run this once in that terminal:
       Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   Then activate again:
       .\.venv\Scripts\Activate.ps1

8. Install Flask:
       py -m pip install -r requirements.txt

9. Set a private admin password and session secret in the same terminal:
       $env:TURFBOOK_ADMIN_PASSWORD = "Choose-A-Strong-Admin-Password"
       $env:FLASK_SECRET_KEY = py -c "import secrets; print(secrets.token_hex(32))"

   Keep these values private. Do not put them in index.html or upload them
   to GitHub. The admin password is NOT admin123.

10. Start the website:
       py app.py

11. Open this address in your browser:
       http://127.0.0.1:5000

ADMIN LOGIN
-----------
Click Admin in the website navigation and enter the password you set in
TURFBOOK_ADMIN_PASSWORD. If you did not set it, the local-only fallback is
ChangeMe123! (change it before using the site publicly).

DATABASE
--------
The first run automatically creates turfbook.db in this folder.
Users and bookings are saved in this SQLite database.
Do not delete turfbook.db if you want to keep your booking records.
Back it up regularly.

HOW TO TEST
-----------
1. Open the site and register a customer account.
2. Log in as that customer.
3. Select a turf, date and available time.
4. Confirm the booking.
5. Open another browser/incognito session and register another customer.
6. Try to book the same turf/date/time: the backend rejects the duplicate.
7. Log in as Admin. The booking should appear in All Bookings.
8. Log in as the first customer to see their own booking.

USING IT WITH YOUR PUBLIC WEBSITE
---------------------------------
GitHub Pages only hosts static files; it cannot run this Flask/Python backend.
For customers on different devices to share bookings, deploy this Flask app
to a Python-capable host and use its public HTTPS URL. This package is
configured to serve BOTH index.html and the API from the same Flask app.
For production hosting:
- Set TURFBOOK_ADMIN_PASSWORD to a strong password.
- Set FLASK_SECRET_KEY to a long random secret.
- Set COOKIE_SECURE=1 when HTTPS is enabled.
- Use a host with persistent disk/storage for turfbook.db, or replace SQLite
  with a managed database if the host has ephemeral storage.
- Back up the database.
- Do not run the Flask development server as a production server.

NOTES
-----
- Existing localStorage customer accounts/bookings are not automatically
  imported. New accounts and bookings are stored in the backend database.
- This is a working local full-stack starter. Public access requires deploying
  the Flask application to a server; running it on your PC only serves your PC.
