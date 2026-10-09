"""Console program for employee leave registration, requests, and export."""

import csv
import json
from datetime import date
from pathlib import Path

DEFAULT_ANNUAL_LEAVE_DAYS = 20
LEAVE_TYPES = ("annual", "sick", "unpaid")
BALANCE_LEAVE_TYPES = frozenset({"annual", "sick"})
EMPLOYEE_FIELDS = (
    "employee_id",
    "name",
    "department",
    "annual_leave_days",
    "leave_requests",
)
REQUEST_FIELDS = (
    "request_id",
    "leave_type",
    "start_date",
    "end_date",
    "days",
    "reason",
    "status",
)
CSV_FIELDS = (
    "employee_id",
    "name",
    "department",
    "annual_leave_days",
    "remaining_leave_days",
    *REQUEST_FIELDS,
)


def empty_records():
    return {"employees": {}}


def records_are_valid(data):
    if not isinstance(data, dict) or not isinstance(data.get("employees"), dict):
        return False
    for employee_id, employee in data["employees"].items():
        if not isinstance(employee, dict):
            return False
        if any(field not in employee for field in EMPLOYEE_FIELDS):
            return False
        if employee["employee_id"] != employee_id:
            return False
        if not isinstance(employee["name"], str) or not isinstance(employee["department"], str):
            return False
        if not _is_whole_number(employee["annual_leave_days"]):
            return False
        if not isinstance(employee["leave_requests"], list):
            return False
        for request in employee["leave_requests"]:
            if not _request_is_valid(request):
                return False
    return True


def load_records(path):
    """Read employees.json. A missing file starts an empty roster."""
    path = Path(path)
    if not path.exists():
        return empty_records()
    try:
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Could not read {path}: {exc}")
        return None
    if not records_are_valid(data):
        print(f"{path} does not match the expected employee records format.")
        return None
    return data


def save_records(records, path):
    """Write the in-memory roster to JSON. Return True when the file is written."""
    path = Path(path)
    try:
        with path.open("w", encoding="utf-8") as handle:
            json.dump(records, handle, indent=2)
            handle.write("\n")
    except OSError as exc:
        print(f"Could not save records to {path}: {exc}")
        return False
    print(f"Saved records to {path}")
    return True


def export_csv(records, path):
    """Write one CSV row per leave request. Employees with none still get a row."""
    path = Path(path)
    try:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
            writer.writeheader()
            for employee in records["employees"].values():
                remaining = remaining_leave_days(employee)
                requests = employee["leave_requests"]
                if not requests:
                    writer.writerow(_csv_row(employee, remaining, None))
                    continue
                for request in requests:
                    writer.writerow(_csv_row(employee, remaining, request))
    except OSError as exc:
        print(f"Could not export records to {path}: {exc}")
        return False
    print(f"Exported records to {path}")
    return True


def inclusive_days(start, end):
    """Calendar days from start through end, both included."""
    return (end - start).days + 1


def used_leave_days(employee):
    """Days that reduce the balance. Unpaid leave is stored and ignored here."""
    return sum(
        request["days"]
        for request in employee["leave_requests"]
        if request["leave_type"] in BALANCE_LEAVE_TYPES
    )


def remaining_leave_days(employee):
    return employee["annual_leave_days"] - used_leave_days(employee)


def find_employee(records, employee_id):
    return records["employees"].get(employee_id.strip())


def next_request_id(records):
    highest = 0
    for employee in records["employees"].values():
        for request in employee["leave_requests"]:
            number = _request_number(request["request_id"])
            if number is not None:
                highest = max(highest, number)
    return f"L{highest + 1:03d}"


def show_menu():
    print()
    print("Employee Leave Management")
    print("1. Register Employee")
    print("2. View Employees")
    print("3. Search Employee")
    print("4. Apply for Leave")
    print("5. Check Leave Balance")
    print("6. View Leave Requests")
    print("7. Save Records (JSON)")
    print("8. Export Records (CSV)")
    print("9. Exit")


def register_employee(records):
    employee_id = input("Employee id: ").strip()
    if not employee_id:
        print("Employee id is required.")
        return
    if employee_id in records["employees"]:
        print(f"{employee_id} is already registered.")
        return

    name = input("Name: ").strip()
    if not name:
        print("Name is required.")
        return

    department = input("Department: ").strip()
    allowance = _read_allowance()
    if allowance is None:
        return

    records["employees"][employee_id] = {
        "employee_id": employee_id,
        "name": name,
        "department": department,
        "annual_leave_days": allowance,
        "leave_requests": [],
    }
    print(f"Registered {employee_id}: {name}.")


def view_employees(records):
    employees = list(records["employees"].values())
    if not employees:
        print("No employees registered.")
        return
    for employee in employees:
        print(_employee_summary(employee))


def search_employee(records):
    query = input("Enter employee id or name: ").strip()
    if not query:
        print("Enter an id or name.")
        return
    needle = query.lower()
    matches = [
        employee
        for employee in records["employees"].values()
        if employee["employee_id"].lower() == needle or needle in employee["name"].lower()
    ]
    if not matches:
        print(f"No employee matches {query!r}.")
        return
    for employee in matches:
        print(_employee_summary(employee))
        _print_employee_requests(employee)


def apply_for_leave(records):
    employee_id = input("Employee id: ").strip()
    employee = find_employee(records, employee_id)
    if employee is None:
        print(f"No employee with id {employee_id}.")
        return

    leave_type = input("Leave type (annual, sick, unpaid): ").strip().lower()
    if leave_type not in LEAVE_TYPES:
        print("Leave type must be annual, sick, or unpaid.")
        return

    start = _read_date("Start date")
    if start is None:
        return
    end = _read_date("End date")
    if end is None:
        return
    if end < start:
        print("End date must be on or after the start date.")
        return

    reason = input("Reason: ").strip()
    days = inclusive_days(start, end)
    if leave_type in BALANCE_LEAVE_TYPES:
        remaining = remaining_leave_days(employee)
        if days > remaining:
            print(f"That request is {days} days, and {remaining} remain.")
            return

    request = {
        "request_id": next_request_id(records),
        "leave_type": leave_type,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "days": days,
        "reason": reason,
        "status": "submitted",
    }
    employee["leave_requests"].append(request)
    print(f"Submitted {request['request_id']} for {days} day(s).")


def check_leave_balance(records):
    employee_id = input("Employee id: ").strip()
    employee = find_employee(records, employee_id)
    if employee is None:
        print(f"No employee with id {employee_id}.")
        return
    print(f"Allowance: {employee['annual_leave_days']}")
    print(f"Used (annual and sick): {used_leave_days(employee)}")
    print(f"Remaining: {remaining_leave_days(employee)}")


def view_leave_requests(records):
    found = False
    for employee in records["employees"].values():
        for request in employee["leave_requests"]:
            found = True
            print(
                f"{request['request_id']}  {employee['employee_id']}  {employee['name']}  "
                f"{request['leave_type']}  {request['start_date']} to {request['end_date']}  "
                f"{request['days']} day(s)  {request['status']}  {request['reason']}"
            )
    if not found:
        print("No leave requests.")


def confirm_exit():
    answer = input("Choose to exit? (y/n): ").strip().lower()
    if answer in {"y", "yes"}:
        return True
    print("Returning to the main menu.")
    return False


def main():
    base = Path(__file__).resolve().parent
    data_path = base / "employees.json"
    csv_path = base / "leave_records.csv"
    records = load_records(data_path)
    if records is None:
        raise SystemExit(1)

    if data_path.exists():
        print(f"Loaded {len(records['employees'])} employee(s) from {data_path}")
    else:
        print("No saved records found. Starting with an empty roster.")

    while True:
        show_menu()
        choice = input("Select an option (1-9): ").strip()
        if choice == "1":
            register_employee(records)
        elif choice == "2":
            view_employees(records)
        elif choice == "3":
            search_employee(records)
        elif choice == "4":
            apply_for_leave(records)
        elif choice == "5":
            check_leave_balance(records)
        elif choice == "6":
            view_leave_requests(records)
        elif choice == "7":
            save_records(records, data_path)
        elif choice == "8":
            export_csv(records, csv_path)
        elif choice == "9":
            if confirm_exit() and save_records(records, data_path):
                print("Goodbye.")
                break
        else:
            print("Invalid option. Choose 1-9.")


def _is_whole_number(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _request_is_valid(request):
    if not isinstance(request, dict):
        return False
    if any(field not in request for field in REQUEST_FIELDS):
        return False
    if request["leave_type"] not in LEAVE_TYPES:
        return False
    if not _is_whole_number(request["days"]) or request["days"] < 1:
        return False
    return all(isinstance(request[field], str) for field in REQUEST_FIELDS if field != "days")


def _request_number(request_id):
    if isinstance(request_id, str) and request_id.startswith("L") and request_id[1:].isdigit():
        return int(request_id[1:])
    return None


def _read_allowance():
    raw = input(f"Annual leave days [{DEFAULT_ANNUAL_LEAVE_DAYS}]: ").strip()
    if raw == "":
        return DEFAULT_ANNUAL_LEAVE_DAYS
    try:
        allowance = int(raw)
    except ValueError:
        print("Annual leave days must be a whole number.")
        return None
    if allowance < 0:
        print("Annual leave days cannot be negative.")
        return None
    return allowance


def _read_date(label):
    raw = input(f"{label} (YYYY-MM-DD): ").strip()
    try:
        return date.fromisoformat(raw)
    except ValueError:
        print("Use a date in YYYY-MM-DD form.")
        return None


def _employee_summary(employee):
    department = employee["department"] or "—"
    return (
        f"{employee['employee_id']}  {employee['name']}  {department}  "
        f"allowance {employee['annual_leave_days']}  "
        f"remaining {remaining_leave_days(employee)}"
    )


def _print_employee_requests(employee):
    if not employee["leave_requests"]:
        print("  No leave requests.")
        return
    for request in employee["leave_requests"]:
        print(
            f"  {request['request_id']}  {request['leave_type']}  "
            f"{request['start_date']} to {request['end_date']}  "
            f"{request['days']} day(s)  {request['status']}  {request['reason']}"
        )


def _csv_row(employee, remaining, request):
    row = {
        "employee_id": employee["employee_id"],
        "name": employee["name"],
        "department": employee["department"],
        "annual_leave_days": employee["annual_leave_days"],
        "remaining_leave_days": remaining,
    }
    for field in REQUEST_FIELDS:
        row[field] = "" if request is None else request[field]
    return row


if __name__ == "__main__":
    main()
