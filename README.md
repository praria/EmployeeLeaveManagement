# Employee Leave Management

A small Python program for registering employees, recording leave, and checking remaining days. The same roster rules run in a console menu and in a Streamlit page. Both read and write `employees.json`.

## Setup

Python 3.11 or newer is enough for the console program. The Streamlit page also needs the packages in `requirements.txt`.

```bash
python3 -m venv employeevenv
source employeevenv/bin/activate
pip install -r requirements.txt
```

On Windows, activate the environment with `employeevenv\Scripts\activate`.

## Run the console program

```bash
python leave_management.py
```

If `employees.json` is missing, the program starts with an empty roster. Options 1–6 change the roster in memory. Option 7 saves it. Option 9 asks you to confirm, then saves and exits.

| Option | Action |
| --- | --- |
| 1 | Register an employee |
| 2 | View employees |
| 3 | Search by id or name |
| 4 | Apply for leave |
| 5 | Check leave balance |
| 6 | View leave requests |
| 7 | Save records to `employees.json` |
| 8 | Export records to `leave_records.csv` |
| 9 | Save and exit |

Press Enter at the allowance prompt to keep the default of 20 days.

## Run the Streamlit page

```bash
streamlit run streamlit_app.py
```

The sidebar uses the same nine actions. Changes stay in the browser session until you choose **Save Records (JSON)** or **Save and finish**. **Export Records (CSV)** downloads `leave_records.csv` and can also write that file next to the program. **Save and finish** writes `employees.json` and leaves the page open; close the browser tab when you are done.

## Leave rules

- Leave types are `annual`, `sick`, and `unpaid`.
- Annual and sick days reduce the balance as soon as the request is submitted.
- Unpaid days are stored and do not reduce the balance.
- Dates are inclusive: 12 October through 14 October counts as 3 days.
- A request is rejected when the end date is before the start date, or when annual or sick days exceed the remaining balance.
- Remaining days are not stored. They are the allowance minus used annual and sick days.

## Records file

`employees.json` keeps employees keyed by id, with each employee's requests nested on that employee:

```json
{
  "employees": {
    "E001": {
      "employee_id": "E001",
      "name": "Ada Lovelace",
      "department": "Engineering",
      "annual_leave_days": 20,
      "leave_requests": [
        {
          "request_id": "L001",
          "leave_type": "annual",
          "start_date": "2026-10-12",
          "end_date": "2026-10-14",
          "days": 3,
          "reason": "Conference",
          "status": "submitted"
        }
      ]
    }
  }
}
```

The CSV export has one row per leave request. An employee with no requests still gets one row, so the full roster is included.

## Project files

| File | Purpose |
| --- | --- |
| `leave_management.py` | Roster rules and the console menu |
| `streamlit_app.py` | Streamlit page |
| `employees.json` | Saved roster |
| `requirements.txt` | Streamlit dependency |
| `.streamlit/config.toml` | Page colors for the Streamlit app |
