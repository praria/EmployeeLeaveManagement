"""Streamlit interface for the employee leave roster."""

import json
from datetime import date

import streamlit as st

import leave_management as lm

MENU = (
    "1. Register Employee",
    "2. View Employees",
    "3. Search Employee",
    "4. Apply for Leave",
    "5. Check Leave Balance",
    "6. View Leave Requests",
    "7. Save Records (JSON)",
    "8. Export Records (CSV)",
    "9. Save and finish",
)


def main():
    st.set_page_config(page_title="Employee Leave Management", layout="wide")
    _load_session()
    records = st.session_state.records

    notice = st.session_state.pop("notice", None)
    if notice:
        st.success(notice)

    st.title("Employee Leave Management")
    if _is_dirty():
        st.caption("Changes stay in this session until you save.")
    else:
        st.caption(f"Roster file: {lm.DATA_PATH.name}")

    _sidebar(records)
    page = st.session_state.menu_page
    if page == MENU[0]:
        _page_register(records)
    elif page == MENU[1]:
        _page_view(records)
    elif page == MENU[2]:
        _page_search(records)
    elif page == MENU[3]:
        _page_apply(records)
    elif page == MENU[4]:
        _page_balance(records)
    elif page == MENU[5]:
        _page_requests(records)
    elif page == MENU[6]:
        _page_save(records)
    elif page == MENU[7]:
        _page_export(records)
    else:
        _page_finish(records)


def _load_session():
    if "records" in st.session_state:
        return
    loaded = lm.load_records(lm.DATA_PATH)
    if loaded is None:
        st.error(
            f"Could not load {lm.DATA_PATH}. "
            "Fix that file before continuing, so a later save does not replace it."
        )
        st.stop()
    st.session_state.records = loaded
    st.session_state.saved_snapshot = _snapshot(loaded)
    st.session_state.register_form_id = 0


def _sidebar(records):
    st.sidebar.metric("Employees", len(records["employees"]))
    if _is_dirty():
        st.sidebar.warning("Unsaved changes")
    else:
        st.sidebar.caption("Saved")
    st.sidebar.radio("Menu", MENU, key="menu_page")


def _page_register(records):
    st.subheader("Register Employee")
    st.caption("The allowance is 20 days when you leave the default in place.")
    form_id = st.session_state.register_form_id
    with st.form(f"register-{form_id}"):
        employee_id = st.text_input("Employee id")
        name = st.text_input("Name")
        department = st.text_input("Department")
        allowance = st.number_input(
            "Annual leave days",
            min_value=0,
            value=lm.DEFAULT_ANNUAL_LEAVE_DAYS,
            step=1,
        )
        submitted = st.form_submit_button("Register")
    if not submitted:
        return

    error = lm.register_employee_record(
        records,
        employee_id,
        name,
        department,
        _as_allowance(allowance),
    )
    if error:
        st.error(error)
        return
    st.session_state.register_form_id += 1
    st.session_state.notice = f"Registered {employee_id.strip()}: {name.strip()}."
    st.rerun()


def _page_view(records):
    st.subheader("View Employees")
    rows = lm.employee_rows(records)
    if not rows:
        st.info("No employees registered.")
        return
    st.dataframe(rows, width="stretch", hide_index=True)


def _page_search(records):
    st.subheader("Search Employee")
    query = st.text_input("Employee id or name")
    if not query.strip():
        st.info("Enter an id or part of a name.")
        return
    matches = lm.search_employees(records, query)
    if not matches:
        st.warning(f"No employee matches {query.strip()!r}.")
        return
    for employee in matches:
        summary = lm.balance_summary(employee)
        st.markdown(f"**{employee['employee_id']} — {employee['name']}**")
        st.write(
            f"{employee['department'] or 'No department'} · "
            f"allowance {summary['allowance']} · remaining {summary['remaining']}"
        )
        requests = employee["leave_requests"]
        if requests:
            st.dataframe(requests, width="stretch", hide_index=True)
        else:
            st.caption("No leave requests.")


def _page_apply(records):
    st.subheader("Apply for Leave")
    st.caption("Annual and sick days reduce the balance. Unpaid days are stored and do not.")
    employee = _select_employee(records, "apply-employee")
    if employee is None:
        return

    summary = lm.balance_summary(employee)
    allowance, used, remaining = st.columns(3)
    allowance.metric("Allowance", summary["allowance"])
    used.metric("Used", summary["used"])
    remaining.metric("Remaining", summary["remaining"])

    leave_type = st.selectbox("Leave type", lm.LEAVE_TYPES)
    start, end = st.columns(2)
    start_date = start.date_input("Start date", value=date.today())
    end_date = end.date_input("End date", value=date.today())
    reason = st.text_input("Reason")

    can_submit = end_date >= start_date
    if not can_submit:
        st.warning("End date must be on or after the start date.")
    else:
        days = lm.inclusive_days(start_date, end_date)
        st.caption(f"{days} calendar day(s), including both dates.")
        if leave_type in lm.BALANCE_LEAVE_TYPES and days > summary["remaining"]:
            can_submit = False
            st.warning(f"That request is {days} days, and {summary['remaining']} remain.")

    if st.button("Submit leave request", type="primary", disabled=not can_submit):
        error = lm.submit_leave_request(
            records,
            employee["employee_id"],
            leave_type,
            start_date,
            end_date,
            reason,
        )
        if error:
            st.error(error)
            return
        request = employee["leave_requests"][-1]
        st.session_state.notice = (
            f"Submitted {request['request_id']} for {request['days']} day(s)."
        )
        st.rerun()


def _page_balance(records):
    st.subheader("Check Leave Balance")
    employee = _select_employee(records, "balance-employee")
    if employee is None:
        return
    summary = lm.balance_summary(employee)
    allowance, used, remaining = st.columns(3)
    allowance.metric("Allowance", summary["allowance"])
    used.metric("Used (annual and sick)", summary["used"])
    remaining.metric("Remaining", summary["remaining"])


def _page_requests(records):
    st.subheader("View Leave Requests")
    rows = lm.request_rows(records)
    if not rows:
        st.info("No leave requests.")
        return
    st.dataframe(rows, width="stretch", hide_index=True)


def _page_save(records):
    st.subheader("Save Records (JSON)")
    st.write(f"Roster file: `{lm.DATA_PATH}`")
    if _is_dirty():
        st.warning("This session has changes that are not in the file yet.")
    else:
        st.info("The file matches this session.")
    if st.button("Save records", type="primary"):
        _save(records)

    st.divider()
    st.write("Reload replaces this session with the file on disk.")
    discard = st.checkbox("Discard unsaved changes") if _is_dirty() else True
    if st.button("Reload from file", disabled=not discard):
        loaded = lm.load_records(lm.DATA_PATH)
        if loaded is None:
            st.error(f"Could not read {lm.DATA_PATH}.")
            return
        st.session_state.records = loaded
        st.session_state.saved_snapshot = _snapshot(loaded)
        st.session_state.notice = f"Reloaded {len(loaded['employees'])} employee(s)."
        st.rerun()


def _page_export(records):
    st.subheader("Export Records (CSV)")
    st.caption("Employees with no requests still appear, so the roster stays complete.")
    rows = lm.export_rows(records)
    if rows:
        st.dataframe(rows, width="stretch", hide_index=True)
    else:
        st.info("No employees to export.")
    csv_text = lm.records_as_csv(records)
    st.download_button(
        "Download CSV",
        data=csv_text,
        file_name=lm.CSV_PATH.name,
        mime="text/csv",
    )
    if st.button("Save CSV next to the program"):
        if lm.export_csv(records, lm.CSV_PATH):
            st.success(f"Exported records to {lm.CSV_PATH}")


def _page_finish(records):
    st.subheader("Save and finish")
    st.write(
        "This saves `employees.json` and leaves the page open. "
        "Close the browser tab when you are done."
    )
    confirmed = st.checkbox("Save the current roster")
    if st.button("Save and finish", type="primary", disabled=not confirmed):
        _save(records)


def _select_employee(records, key):
    employees = list(records["employees"].values())
    if not employees:
        st.info("Register an employee first.")
        return None
    labels = [f"{employee['employee_id']} — {employee['name']}" for employee in employees]
    choice = st.selectbox("Employee", labels, key=key)
    return employees[labels.index(choice)]


def _save(records):
    if not lm.save_records(records, lm.DATA_PATH):
        st.error(f"Could not save records to {lm.DATA_PATH}.")
        return
    st.session_state.saved_snapshot = _snapshot(records)
    st.session_state.notice = f"Saved records to {lm.DATA_PATH.name}."
    st.rerun()


def _snapshot(records):
    return json.dumps(records, sort_keys=True)


def _is_dirty():
    return _snapshot(st.session_state.records) != st.session_state.saved_snapshot


def _as_allowance(value):
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


if __name__ == "__main__":
    main()
