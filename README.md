# Digital File Tracking System

A Streamlit-based digital filing system designed to improve physical file retrieval, tracking, and accountability.

## Version 1 Features

- Register staff users
- Store staff name, organization email, department, and staff number
- Register physical files
- Store file number and file name
- Generate a unique barcode value from the file number
- Search files
- Pick files
- Return files
- Track complete file movement history
- Identify the current holder of a file
- Dashboard showing file availability
- Export records to Excel

## Technology

- Python
- Streamlit
- SQLite
- Pandas
- OpenPyXL
- GitHub

## Project Structure

```text
digital-file-tracking-system/
│
├── app.py
├── database.py
├── barcode.py
├── export.py
├── requirements.txt
├── README.md
├── .gitignore
│
├── data/
│   └── .gitkeep
│
└── barcodes/
    └── .gitkeep
```

## Run Locally

Create and activate a virtual environment if desired:

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run Streamlit:

```bash
streamlit run app.py
```

The application will normally be available at:

```text
http://localhost:8501
```

## Database

Version 1 uses SQLite.

The local database is automatically created at:

```text
data/filing_system.db
```

The database is intentionally ignored by Git so organizational staff and file data are not uploaded to GitHub.

## Basic Workflow

1. Register staff users.
2. Register physical files.
3. The system generates a barcode value from each file number.
4. Search or enter the barcode when a file is picked.
5. Select the staff member receiving the file.
6. Click **PICK FILE**.
7. When the file is returned, enter/scan the same barcode.
8. Click **RETURN FILE**.
9. Review the movement history.
10. Export records to Excel when required.

## Important Security Note

Do not commit:

- The SQLite database
- Staff records
- File records
- Passwords
- API keys
- Authentication secrets
- Streamlit secrets

These are excluded through `.gitignore`.

## Planned Future Versions

### Version 2
- Printable barcode labels
- Actual barcode image generation
- USB barcode scanner support
- Phone/camera barcode scanning
- Better search and filtering

### Version 3
- Organization email authentication
- Microsoft 365 / Microsoft Entra ID authentication
- Role-based access control
- Administrator controls

### Version 4
- PostgreSQL production database
- Overdue file tracking
- Notifications/reminders
- Advanced reporting
- Deployment for multiple organizational users
