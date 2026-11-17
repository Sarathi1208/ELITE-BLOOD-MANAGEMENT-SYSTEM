# ELITE BLOOD MANAGEMENT SYSTEM

A Flask + SQLite academic mini project for donor registration, donor discovery, blood inventory and blood request administration.

## 1. Requirements
- Python 3.10 or newer
- pip
- A modern web browser

## 2. Installation (Windows)
1. Extract `ELITE_BLOOD_MANAGEMENT_SYSTEM.zip`.
2. Open Command Prompt or VS Code terminal inside the extracted folder.
3. Create and activate a virtual environment:
   ```bat
   python -m venv venv
   venv\Scripts\activate
   ```
4. Install dependencies:
   ```bat
   pip install -r requirements.txt
   ```
5. Recommended: set a strong secret key and admin credentials before first launch:
   ```bat
   set SECRET_KEY=replace-with-a-long-random-secret
   set ADMIN_EMAIL=admin@eliteblood.com
   set ADMIN_PASSWORD=YourStrongAdminPassword123!
   ```
   PowerShell: `$env:SECRET_KEY="..."`, `$env:ADMIN_EMAIL="..."`, `$env:ADMIN_PASSWORD="..."`.
6. Start the app: `python app.py`
7. Visit **http://127.0.0.1:5000**.

The SQLite database is automatically created at `database/elite_blood.db` on first run. Eight blood group rows and an initial admin account are seeded.

## 3. Default administrator login
If environment variables are not set before first run:
- Email: `admin@eliteblood.com`
- Password: `Admin@123`

**Change the default password for any demonstration beyond a local classroom machine.** The admin account is created only if it does not exist; changing environment variables later does not change an existing password. To reset a local demo, stop the app and delete `database/elite_blood.db`, then restart (this deletes all demo data).

## 4. Main user flow
### Donor
1. Select **Become a Donor** and create an account.
2. Complete the donor profile: age, gender, blood group, phone, city, address and optional medical certificate.
3. Donors appear in **Find Donors** only while marked available.
4. Use the dashboard to edit the profile, see inventory and submit requests.

### Administrator
1. Sign in with the administrator account.
2. Open **Admin** for donor/request/stock statistics.
3. Use **Donors** to search profiles and enable/disable availability.
4. Use **Requests** to mark a request Pending, Approved or Rejected.
5. Use **Manage Stock** to set units for each blood group.

Approving a request deducts units from matching stock. Approval is blocked when stock is insufficient. Moving an approved request to Pending or Rejected restores units. Re-saving an already approved request does not deduct stock twice.

## 5. Database tables
- `users`: account name, unique email, password hash and role.
- `donors`: profile, age, gender, blood group, phone, city, address, certificate filename and availability.
- `inventory`: one row for each of eight blood groups and its unit count.
- `blood_requests`: patient/hospital/contact details, units, status and submitting account.

## 6. Project file map
- `app.py`: Flask routes, validation, authentication, SQLite schema and business logic.
- `config.py`, `models.py`: small organization/reference modules; database initialization and SQL are kept in `app.py` for straightforward demonstration.
- `templates/`: Jinja2 HTML pages.
- `static/css/style.css`: responsive burgundy-and-white UI.
- `static/js/script.js`: mobile navigation and client-side form checks.
- `database/`: generated SQLite database.
- `uploads/certificates/`: uploaded PDF/JPG/PNG certificates.

## 7. Validation and security notes
- Passwords are stored as Werkzeug password hashes, never plain text.
- SQL statements use SQLite parameter binding.
- Email addresses are unique (case-insensitive).
- Donor age is checked in application logic and the database.
- Certificate upload accepts PDF, PNG, JPG and JPEG only, limits size to 5 MB, uses a sanitized randomized filename and is downloadable only by an administrator.
- User/admin routes check login and role.
- Replace the Flask secret key before deployment.
- This is an academic starter, not a production medical service. Before public deployment, add CSRF protection, HTTPS, stronger phone/identity verification, audit logs, backups, privacy/consent workflows, stricter access to donor contact details, malware scanning and formal medical eligibility/compatibility checks.

## 8. Troubleshooting
- **`python` is not recognized:** install Python, enable “Add Python to PATH”, and reopen the terminal.
- **`No module named flask`:** activate the virtual environment and run `pip install -r requirements.txt`.
- **Port 5000 is busy:** change the port in the final `app.run(...)` line of `app.py` and use the matching URL.
- **Admin password environment variable has no effect:** the database may already contain the original admin. Delete the local database only if you are comfortable losing its data, then restart.

## 9. Important medical disclaimer
This application is for academic demonstration only. Donor matching by blood group and city is a directory filter, not clinical compatibility testing. It does not verify donor eligibility, crossmatching, infectious-disease screening, blood storage conditions or real-time blood-bank stock. Always use an authorized blood bank and qualified medical professionals. For emergencies, contact the hospital/emergency services directly.
