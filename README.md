# Contact Book

A desktop contact book built with Python and Tkinter.

The app stores data in PostgreSQL and supports adding, updating, deleting, 
searching, and selecting contacts. It can also suggest and normalize US 
billing addresses using Google Places APIs.

## Features

- Create contacts tied to a company
- Update existing contact and company details
- Delete contacts
- Search by company ID, company name, or client name
- Select a contact and return values to the parent form
- Optional billing-address autocomplete and normalization via Google Maps Places APIs

## Tech Stack

- Python
- Tkinter
- PostgreSQL
- psycopg2
- python-dotenv
- requests

## Requirements

- Python 3.10+
- PostgreSQL server
- A PostgreSQL database with required tables

## Installation

1. Clone the repository:

   ```sh
   git clone https://github.com/theOrganizedMind/contact_book.git
   cd contact_book
   ```

2. Create and activate a virtual environment (recommended):

   Windows (PowerShell):
   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

   Windows (cmd):
   ```bat
   py -m venv .venv
   .venv\Scripts\activate
   ```

3. Install dependencies:

   ```sh
   pip install -r requirements.txt
   ```

## Environment Variables

Create a .env file in the project root.

```env
POSTGRESQL_HOST=host
POSTGRESQL_PORT=port
DATABASE=your_database_name
POSTGRESQL_USER=your_username
POSTGRESQL_PASSWORD=your_password

# Optional: enables billing address autocomplete/normalization
GOOGLE_MAPS_API=your_google_maps_api_key
```

Notes:

- If GOOGLE_MAPS_API is not set, the app still works, but address autocomplete is disabled.
- The repository is configured to ignore .env.

## Database Setup

Create the required tables before launching the app:

```sql
CREATE TABLE IF NOT EXISTS company (
    company_id INTEGER PRIMARY KEY,
    company_name TEXT NOT NULL,
    street TEXT,
    city TEXT,
    state TEXT,
    zip TEXT
);

CREATE TABLE IF NOT EXISTS client (
    client_id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES company(company_id) ON DELETE CASCADE,
    first_name TEXT NOT NULL,
    last_name TEXT,
    phone TEXT NOT NULL,
    email TEXT
);
```

## Usage

Run the app:

```sh
python contact_book.py
```

## Project Files

- contact_book.py: Tkinter UI and contact management logic
- postgresql.py: PostgreSQL connection helper
- requirements.txt: Python dependencies
- contacts.json: sample/legacy contact data file
- .gitignore: ignored files and folders
- LICENSE.txt: project license

## Security Notes

- Do not commit real credentials or a real .env file.
- Treat contact records as potentially sensitive data in production usage.

## License

This project is licensed under the MIT License. See LICENSE.txt for details.