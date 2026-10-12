
import streamlit as st
import pandas as pd
from pathlib import Path
from io import BytesIO

from database import (
    initialize_database,
    add_user,
    get_items,
    find_item,
    authenticate_user,
    create_first_admin,
    has_users,
    acknowledge_oath,
    add_item,
    issue_item,
    return_item,
    get_movements,
    get_notifications,
    mark_notifications_read,
)

from barcode_utils import create_barcode_image
from export import create_excel_export


# =========================================================
# PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="Digital Filing System",
    page_icon="📁",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =========================================================
# BANKING-STYLE THEME
# =========================================================

st.markdown(
    """
    <style>
    :root {
        --navy: #102A43;
        --navy-light: #243F5A;
        --blue: #2870A8;
        --page-bg: #F4F7FA;
        --white: #FFFFFF;
        --border: #DCE4EC;
        --text: #243447;
        --muted: #64748B;
        --green: #18794E;
        --red: #B42318;
        --orange: #B54708;
    }

    .stApp {
        background-color: var(--page-bg);
        color: var(--text);
    }

    [data-testid="stSidebar"] {
        background-color: var(--navy);
        border-right: 1px solid #29445F;
    }

    [data-testid="stSidebar"] * {
        color: #FFFFFF !important;
    }

    [data-testid="stSidebar"] [data-testid="stRadio"] label {
        padding: 7px 9px;
        border-radius: 7px;
    }

    [data-testid="stSidebar"] hr {
        border-color: #456078;
    }

    .brand-title {
        font-size: 25px;
        font-weight: 800;
        color: var(--navy);
        margin-bottom: 2px;
    }

    .brand-subtitle {
        color: var(--muted);
        font-size: 13px;
        margin-bottom: 22px;
    }

    .section-heading {
        color: var(--navy);
        font-size: 20px;
        font-weight: 750;
        margin-top: 12px;
        margin-bottom: 12px;
    }

    .metric-card {
        background: var(--white);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 19px;
        min-height: 125px;
        box-shadow: 0 2px 6px rgba(16, 42, 67, 0.04);
    }

    .metric-label {
        color: var(--muted);
        font-size: 13px;
        font-weight: 600;
        margin-bottom: 8px;
    }

    .metric-value {
        color: var(--navy);
        font-size: 30px;
        font-weight: 800;
    }

    .metric-note {
        color: var(--muted);
        font-size: 12px;
        margin-top: 4px;
    }

    .panel {
        background: var(--white);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 18px;
        margin-bottom: 12px;
    }

    div[data-testid="stButton"] button,
    div[data-testid="stDownloadButton"] button {
        border-radius: 8px;
        font-weight: 650;
        min-height: 42px;
    }

    div[data-testid="stButton"] button[kind="primary"] {
        background: var(--navy);
        border: 1px solid var(--navy);
        color: #FFFFFF;
    }

    div[data-testid="stButton"] button[kind="primary"]:hover {
        background: var(--navy-light);
        border-color: var(--navy-light);
    }

    div[data-testid="stTextInput"] input,
    div[data-testid="stSelectbox"] div[data-baseweb="select"] {
        border-radius: 8px;
    }

    div[data-testid="stDataFrame"] {
        border: 1px solid var(--border);
        border-radius: 9px;
        overflow: hidden;
    }

    .status-available {
        color: #18794E;
        font-weight: 700;
    }

    .status-out {
        color: #B54708;
        font-weight: 700;
    }

    .small-muted {
        color: var(--muted);
        font-size: 12px;
    }

    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    @media (max-width: 768px) {
        .brand-title {font-size: 22px;}
        .metric-card {padding: 13px; min-height: 105px;}
        .metric-value {font-size: 24px;}
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

initialize_database()


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def get_value(record, *keys, default=""):
    """Return the first available value from a database row/dict."""
    if not isinstance(record, dict):
        return default

    for key in keys:
        value = record.get(key)
        if value is not None:
            return value

    return default


def user_id(user):
    return get_value(user, "id", "user_id", default=None)


def user_role(user):
    return str(get_value(user, "role", default="User")).strip().lower()


def is_admin(user):
    return user_role(user) == "admin"


def is_view_only(user):
    return user_role(user) in ("view only", "view_only", "viewer")


def can_manage_files(user):
    return is_admin(user)


def can_move_files(user):
    return not is_view_only(user)


def get_file_id(item):
    return get_value(item, "file_id", "item_id", default="")


def get_file_name(item):
    return get_value(item, "file_name", "title", default="Unnamed file")


def get_file_status(item):
    return str(get_value(item, "status", default="Available"))


def is_file_out(item):
    status = get_file_status(item).strip().lower()
    return status in ("issued", "out", "borrowed", "checked out", "checked_out")


def format_file_table(items):
    """Prepare file rows for display without exposing internal user records."""
    rows = []

    for item in items:
        rows.append(
            {
                "File ID": get_file_id(item),
                "File Name": get_file_name(item),
                "Department": get_value(item, "department"),
                "Section": get_value(item, "section"),
                "Status": get_file_status(item),
                "Current Holder": get_value(
                    item, "current_holder_name", "current_holder",
                    default="—"
                ) or "—",
                "Barcode": get_value(item, "barcode"),
            }
        )

    return pd.DataFrame(rows)


def show_page_header(title, description=""):
    st.markdown(f'<div class="brand-title">{title}</div>', unsafe_allow_html=True)

    if description:
        st.markdown(
            f'<div class="brand-subtitle">{description}</div>',
            unsafe_allow_html=True,
        )


def metric_card(label, value, note, icon):
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{icon} &nbsp; {label}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-note">{note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def find_item_from_input(identifier):
    """Use the existing database lookup for file ID/barcode."""
    identifier = identifier.strip()

    if not identifier:
        return None

    return find_item(identifier)


def get_all_items():
    return get_items() or []


# =========================================================
# FIRST ADMINISTRATOR SETUP
# =========================================================

if not has_users():
    show_page_header(
        "📁 Digital Filing System",
        "Initial administrator registration",
    )

    st.info(
        "No users have been registered yet. Create the first administrator "
        "account to begin using the system."
    )

    with st.form("first_admin_form"):
        st.subheader("Create Administrator")

        admin_name = st.text_input("Full Name")
        admin_email = st.text_input("Organization Email")
        admin_department = st.text_input("Department")
        admin_section = st.text_input("Section (optional)")
        admin_staff_number = st.text_input("Staff Number")
        admin_password = st.text_input("Password", type="password")
        admin_confirm = st.text_input("Confirm Password", type="password")

        submitted = st.form_submit_button(
            "Create Administrator",
            type="primary",
            use_container_width=True,
        )

        if submitted:
            if not all(
                [
                    admin_name.strip(),
                    admin_email.strip(),
                    admin_department.strip(),
                    admin_staff_number.strip(),
                    admin_password,
                ]
            ):
                st.error("Please complete all required fields.")
            elif admin_password != admin_confirm:
                st.error("The passwords do not match.")
            else:
                try:
                    create_first_admin(
                        admin_name.strip(),
                        admin_email.strip(),
                        admin_department.strip(),
                        admin_section.strip() or None,
                        admin_staff_number.strip(),
                        admin_password,
                    )
                    st.success(
                        "Administrator created. You can now sign in."
                    )
                    st.rerun()
                except Exception as error:
                    st.error(f"Could not create administrator: {error}")

    st.stop()


# =========================================================
# LOGIN
# =========================================================

if "logged_in_user" not in st.session_state:
    st.session_state.logged_in_user = None

if st.session_state.logged_in_user is None:
    st.markdown("<br>", unsafe_allow_html=True)

    left, center, right = st.columns([1, 1.2, 1])

    with center:
        st.markdown(
            """
            <div class="panel" style="text-align:center;">
                <div style="font-size:46px;">📁</div>
                <div class="brand-title">Digital Filing System</div>
                <div class="brand-subtitle">
                    Secure file tracking and accountability
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.form("login_form"):
            st.subheader("Sign in")

            staff_number = st.text_input("Staff Number")
            password = st.text_input("Password", type="password")

            login_submitted = st.form_submit_button(
                "Sign In",
                type="primary",
                use_container_width=True,
            )

            if login_submitted:
                user = authenticate_user(
                    staff_number.strip(),
                    password,
                )

                if user:
                    st.session_state.logged_in_user = user
                    st.rerun()
                else:
                    st.error(
                        "Invalid staff number or password. Please try again."
                    )

    st.stop()


# =========================================================
# ACTIVE USER
# =========================================================

current_user = st.session_state.logged_in_user
current_user_id = user_id(current_user)
current_user_name = get_value(current_user, "name", default="Staff Member")
current_user_department = get_value(current_user, "department", default="—")
current_user_role = get_value(current_user, "role", default="User")


# =========================================================
# SIDEBAR NAVIGATION
# =========================================================

with st.sidebar:
    st.markdown(
        """
        <div style="padding:10px 4px 18px 4px;">
            <div style="font-size:34px;">📁</div>
            <div style="font-size:20px;font-weight:800;">
                Digital Filing System
            </div>
            <div style="font-size:12px;color:#D7E2ED !important;">
                File tracking & accountability
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

    st.markdown("**MAIN MENU**")

    pages = [
        "📊 Dashboard",
        "📷 Scan / Issue / Return",
        "🔎 Search Files",
        "🕒 Movement History",
        "🔔 Sona Notifications",
        "📜 Oath & Responsibilities",
    ]

    if is_admin(current_user):
        pages.extend(
            [
                "👤 Register User",
                "📁 Register File",
                "📤 Export to Excel",
            ]
        )

    selected_page = st.radio(
        "Navigation",
        pages,
        label_visibility="collapsed",
    )

    st.divider()

    st.markdown("**SIGNED-IN USER**")
    st.write(f"👤 {current_user_name}")
    st.caption(f"Department: {current_user_department}")
    st.caption(f"Role: {current_user_role}")

    if st.button("🚪 Sign Out", use_container_width=True):
        st.session_state.logged_in_user = None
        st.rerun()


# =========================================================
# DASHBOARD
# =========================================================

if selected_page == "📊 Dashboard":
    show_page_header(
        "📊 Dashboard",
        "Overview of file records, availability and daily operations.",
    )

    items = get_all_items()
    total_files = len(items)
    files_out = [item for item in items if is_file_out(item)]
    out_count = len(files_out)
    available_count = total_files - out_count

    notifications = get_notifications(current_user_id) or []
    unread_count = sum(
        1 for note in notifications
        if not bool(get_value(note, "is_read", default=0))
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        metric_card(
            "Total Files",
            total_files,
            "All registered files",
            "📁",
        )

    with col2:
        metric_card(
            "Available",
            available_count,
            "Ready for authorized use",
            "✅",
        )

    with col3:
        metric_card(
            "Files Out",
            out_count,
            "Currently issued",
            "📤",
        )

    with col4:
        metric_card(
            "Unread Alerts",
            unread_count,
            "Sona notifications",
            "🔔",
        )

    st.markdown('<div class="section-heading">⚡ Quick Actions</div>',
                unsafe_allow_html=True)

    quick1, quick2, quick3 = st.columns(3)

    with quick1:
        if st.button(
            "📷 Scan / Issue / Return",
            use_container_width=True,
        ):
            st.session_state.quick_page = "📷 Scan / Issue / Return"
            st.rerun()

    with quick2:
        if st.button(
            "🔎 Search Files",
            use_container_width=True,
        ):
            st.session_state.quick_page = "🔎 Search Files"
            st.rerun()

    with quick3:
        if is_admin(current_user):
            if st.button(
                "📁 Register New File",
                use_container_width=True,
            ):
                st.session_state.quick_page = "📁 Register File"
                st.rerun()
        else:
            if st.button(
                "🔔 View Notifications",
                use_container_width=True,
            ):
                st.session_state.quick_page = "🔔 Sona Notifications"
                st.rerun()

    st.markdown(
        '<div class="section-heading">📤 Files Currently Out</div>',
        unsafe_allow_html=True,
    )

    if files_out:
        out_rows = []

        for item in files_out:
            out_rows.append(
                {
                    "File ID": get_file_id(item),
                    "File Name": get_file_name(item),
                    "Department": get_value(item, "department"),
                    "Section": get_value(item, "section"),
                    "Current Holder": get_value(
                        item,
                        "current_holder_name",
                        "current_holder",
                        default="—",
                    ) or "—",
                    "Staff Number": get_value(
                        item, "current_holder_staff_number", default="—"
                    ) or "—",
                    "Status": get_file_status(item),
                }
            )

        st.dataframe(
            pd.DataFrame(out_rows),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.success("No files are currently marked as issued.")

    st.markdown(
        '<div class="section-heading">🕒 Recent File Activity</div>',
        unsafe_allow_html=True,
    )

    movements = get_movements() or []

    if movements:
        recent_rows = []

        for movement in movements[:8]:
            recent_rows.append(
                {
                    "File": get_value(
                        movement, "file_name", "title", default="—"
                    ),
                    "Staff Member": get_value(
                        movement, "user_name", "name", default="—"
                    ),
                    "Action": get_value(movement, "action", default="—"),
                    "Date & Time": get_value(
                        movement, "movement_time", default="—"
                    ),
                }
            )

        st.dataframe(
            pd.DataFrame(recent_rows),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No file movement has been recorded yet.")


# =========================================================
# SCAN / ISSUE / RETURN
# =========================================================

elif selected_page == "📷 Scan / Issue / Return":
    show_page_header(
        "📷 Scan / Issue / Return",
        "Enter or scan a file ID/barcode to retrieve the file record.",
    )

    if not can_move_files(current_user):
        st.info(
            "Your View Only role allows you to view records but not issue "
            "or return files."
        )

    identifier = st.text_input(
        "Scan or enter File ID / Barcode",
        placeholder="Example: DFS-000001",
        key="scan_identifier",
    )

    if st.button("🔍 Find File", type="primary"):
        if identifier.strip():
            st.session_state.scanned_item = find_item_from_input(identifier)
        else:
            st.warning("Enter or scan a file ID/barcode first.")

    item = st.session_state.get("scanned_item")

    if item:
        st.markdown('<div class="section-heading">File Details</div>',
                    unsafe_allow_html=True)

        d1, d2 = st.columns(2)

        with d1:
            st.write("**File ID:**", get_file_id(item))
            st.write("**File Name:**", get_file_name(item))
            st.write("**Department:**", get_value(item, "department"))
            st.write("**Section:**", get_value(item, "section") or "—")

        with d2:
            st.write("**Barcode:**", get_value(item, "barcode") or "—")
            st.write("**Status:**", get_file_status(item))
            st.write(
                "**Current Holder:**",
                get_value(
                    item,
                    "current_holder_name",
                    "current_holder",
                    default="None",
                ) or "None",
            )

        st.divider()

        if can_move_files(current_user):
            remarks = st.text_area(
                "Remarks (optional)",
                placeholder="Enter any relevant issue or return notes.",
                key="movement_remarks",
            )

            is_out = is_file_out(item)
            holder_id = get_value(item, "current_holder_id", default=None)

            if is_out and str(holder_id) == str(current_user_id):
                if st.button(
                    "↩️ Return This File",
                    type="primary",
                    use_container_width=True,
                ):
                    try:
                        return_item(
                            get_value(item, "id", "item_id"),
                            current_user_id,
                            remarks.strip(),
                        )
                        st.success("File returned successfully.")
                        st.session_state.scanned_item = None
                        st.rerun()
                    except Exception as error:
                        st.error(f"Could not return file: {error}")

            elif is_out:
                st.warning(
                    "This file is already issued to another staff member. "
                    "Only the current holder should return it through this "
                    "screen, unless your organization has an approved "
                    "administrator return procedure."
                )

            else:
                if st.button(
                    "📤 Issue This File to Me",
                    type="primary",
                    use_container_width=True,
                ):
                    try:
                        issue_item(
                            get_value(item, "id", "item_id"),
                            current_user_id,
                            remarks.strip(),
                        )
                        st.success("File issued successfully.")
                        st.session_state.scanned_item = None
                        st.rerun()
                    except Exception as error:
                        st.error(f"Could not issue file: {error}")
    elif identifier.strip() and st.session_state.get("scanned_item") is None:
        st.caption("Use Find File to look up the entered identifier.")


# =========================================================
# SEARCH FILES
# =========================================================

elif selected_page == "🔎 Search Files":
    show_page_header(
        "🔎 Search Files",
        "Search the file register by name, ID, department, section or status.",
    )

    items = get_all_items()

    if not items:
        st.info("No files have been registered yet.")
    else:
        search_term = st.text_input(
            "Search",
            placeholder="Type a file name, file ID, department or barcode...",
        )

        status_filter = st.selectbox(
            "Filter by Status",
            ["All", "Available", "Out"],
        )

        department_options = sorted(
            {
                str(get_value(item, "department", default=""))
                for item in items
                if get_value(item, "department", default="")
            }
        )

        department_filter = st.selectbox(
            "Filter by Department",
            ["All Departments"] + department_options,
        )

        filtered_items = []

        for item in items:
            searchable_text = " ".join(
                [
                    str(get_file_id(item)),
                    str(get_file_name(item)),
                    str(get_value(item, "department")),
                    str(get_value(item, "section")),
                    str(get_value(item, "barcode")),
                    str(get_value(item, "current_holder_name")),
                ]
            ).lower()

            if search_term.strip().lower() not in searchable_text:
                continue

            if status_filter == "Available" and is_file_out(item):
                continue

            if status_filter == "Out" and not is_file_out(item):
                continue

            if (
                department_filter != "All Departments"
                and str(get_value(item, "department"))
                != department_filter
            ):
                continue

            filtered_items.append(item)

        st.caption(f"{len(filtered_items)} file(s) found.")

        if filtered_items:
            st.dataframe(
                format_file_table(filtered_items),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.warning("No files match your search and filters.")

        st.markdown("### View an individual file")

        chosen_id = st.text_input(
            "Enter the File ID or barcode for details",
            placeholder="Example: DFS-000001",
        )

        if st.button("View File Details"):
            if chosen_id.strip():
                found = find_item(chosen_id.strip())

                if found:
                    st.session_state.detail_item = found
                else:
                    st.session_state.detail_item = None
                    st.warning("No matching file was found.")
            else:
                st.warning("Enter a file ID or barcode.")

        detail_item = st.session_state.get("detail_item")

        if detail_item:
            st.write("**File ID:**", get_file_id(detail_item))
            st.write("**File Name:**", get_file_name(detail_item))
            st.write("**Department:**", get_value(detail_item, "department"))
            st.write("**Section:**", get_value(detail_item, "section") or "—")
            st.write("**Status:**", get_file_status(detail_item))


# =========================================================
# MOVEMENT HISTORY
# =========================================================

elif selected_page == "🕒 Movement History":
    show_page_header(
        "🕒 Movement History",
        "Review recorded file issues and returns.",
    )

    movements = get_movements() or []

    if not movements:
        st.info("No file movements have been recorded.")
    else:
        rows = []

        for movement in movements:
            rows.append(
                {
                    "File ID": get_value(
                        movement, "system_file_id", "file_id", "item_id"
                    ),
                    "File Name": get_value(
                        movement, "file_name", "title"
                    ),
                    "Staff Member": get_value(
                        movement, "user_name", "name"
                    ),
                    "Staff Number": get_value(movement, "staff_number"),
                    "Action": get_value(movement, "action"),
                    "Date & Time": get_value(movement, "movement_time"),
                    "Remarks": get_value(movement, "remarks"),
                }
            )

        movement_df = pd.DataFrame(rows)

        search_movement = st.text_input(
            "Filter movement history",
            placeholder="Search by file, staff member or action...",
        )

        if search_movement.strip():
            mask = movement_df.astype(str).apply(
                lambda column: column.str.contains(
                    search_movement.strip(),
                    case=False,
                    na=False,
                )
            ).any(axis=1)

            movement_df = movement_df[mask]

        st.dataframe(
            movement_df,
            use_container_width=True,
            hide_index=True,
        )


# =========================================================
# SONA NOTIFICATIONS
# =========================================================

elif selected_page == "🔔 Sona Notifications":
    show_page_header(
        "🔔 Sona Notifications",
        "View system notifications and accountability alerts.",
    )

    notifications = get_notifications(current_user_id) or []

    if st.button("Mark All as Read"):
        try:
            mark_notifications_read(current_user_id)
            st.success("Notifications marked as read.")
            st.rerun()
        except Exception as error:
            st.error(f"Could not update notifications: {error}")

    if not notifications:
        st.info("There are no notifications to display.")
    else:
        for note in notifications:
            is_read = bool(get_value(note, "is_read", default=0))
            heading = get_value(note, "title", default="Notification")
            message = get_value(note, "message", default="")
            created_at = get_value(note, "created_at", default="")

            with st.container(border=True):
                col1, col2 = st.columns([5, 1])

                with col1:
                    st.markdown(f"**{heading}**")
                    st.write(message)

                    if created_at:
                        st.caption(str(created_at))

                with col2:
                    st.caption("Read" if is_read else "Unread")


# =========================================================
# OATH & RESPONSIBILITIES
# =========================================================

elif selected_page == "📜 Oath & Responsibilities":
    show_page_header(
        "📜 Oath & Responsibilities",
        "Read and acknowledge your responsibilities when handling physical files.",
    )

    st.markdown(
        """
        <div class="panel">
            <h3 style="color:#102A43;">Digital Filing System Oath</h3>
            I understand that physical files are official organizational
            records and must be handled responsibly.

            <ul>
                <li>I will only access files required for my authorized duties.</li>
                <li>I will provide accurate information when a file is issued or returned.</li>
                <li>I will not remove, alter, share or disclose file contents without authorization.</li>
                <li>I will keep files secure and return them according to organizational procedures.</li>
                <li>I will promptly report missing, damaged or incorrectly filed records.</li>
                <li>I understand that file movements may be recorded for accountability.</li>
            </ul>

            <p>
            <strong>Credit / Filing Administrator responsibilities:</strong>
            verify file identification, record movements accurately, protect
            records, and follow the organization's authorization procedures.
            </p>

            <p>
            <strong>File user responsibilities:</strong>
            use files only for authorized work, safeguard them while in their
            possession, and return them promptly.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.warning(
        "This is a system acknowledgement template. Have your organization "
        "approve the final wording before using it as an official policy."
    )

    already_acknowledged = bool(
        get_value(current_user, "oath_acknowledged", default=0)
    )

    if already_acknowledged:
        st.success("Your account shows that you have acknowledged the oath.")
        oath_date = get_value(current_user, "oath_date", default="")
        if oath_date:
            st.caption(f"Acknowledgement date: {oath_date}")
    else:
        confirm_oath = st.checkbox(
            "I have read and understood the responsibilities above."
        )

        if st.button(
            "Acknowledge Responsibilities",
            type="primary",
            disabled=not confirm_oath,
        ):
            try:
                acknowledge_oath(current_user_id)
                st.success("Your acknowledgement has been recorded.")
                st.rerun()
            except Exception as error:
                st.error(f"Could not record acknowledgement: {error}")


# =========================================================
# REGISTER USER — ADMIN ONLY
# =========================================================

elif selected_page == "👤 Register User":
    if not is_admin(current_user):
        st.error("Only administrators can register users.")
        st.stop()

    show_page_header(
        "👤 Register User",
        "Create an account for an authorized staff member.",
    )

    with st.form("register_user_form"):
        name = st.text_input("Full Name")
        email = st.text_input("Organization Email")
        department = st.text_input("Department")
        section = st.text_input("Section (optional)")
        staff_number = st.text_input("Staff Number")
        role = st.selectbox(
            "Role",
            ["User", "View Only", "Admin"],
        )
        password = st.text_input("Temporary Password", type="password")
        confirm_password = st.text_input(
            "Confirm Password",
            type="password",
        )

        submitted = st.form_submit_button(
            "Register User",
            type="primary",
            use_container_width=True,
        )

        if submitted:
            if not all(
                [
                    name.strip(),
                    email.strip(),
                    department.strip(),
                    staff_number.strip(),
                    password,
                ]
            ):
                st.error("Complete all required fields.")
            elif password != confirm_password:
                st.error("The passwords do not match.")
            else:
                try:
                    add_user(
                        name.strip(),
                        email.strip(),
                        department.strip(),
                        section.strip() or None,
                        staff_number.strip(),
                        role,
                        password,
                    )
                    st.success(f"User {name.strip()} registered successfully.")
                    st.rerun()
                except Exception as error:
                    st.error(f"Could not register user: {error}")


# =========================================================
# REGISTER FILE — ADMIN ONLY
# =========================================================

elif selected_page == "📁 Register File":
    if not is_admin(current_user):
        st.error("Only administrators can register files.")
        st.stop()

    show_page_header(
        "📁 Register File",
        "Add a physical file to the register and generate its barcode.",
    )

    with st.form("register_file_form"):
        file_name = st.text_input(
            "File Name",
            placeholder="Enter the official file name",
        )
        department = st.text_input("Department")
        section = st.text_input("Section (optional)")

        submitted = st.form_submit_button(
            "Register File",
            type="primary",
            use_container_width=True,
        )

        if submitted:
            if not file_name.strip() or not department.strip():
                st.error("File Name and Department are required.")
            else:
                try:
                    add_item(
                        file_name.strip(),
                        department.strip(),
                        section.strip() or None,
                    )

                    # Find the newly registered file from the existing DB.
                    current_items = get_all_items()
                    matches = [
                        item for item in current_items
                        if str(get_file_name(item)).strip().lower()
                        == file_name.strip().lower()
                        and str(get_value(item, "department")).strip().lower()
                        == department.strip().lower()
                        and str(get_value(item, "section") or "").strip().lower()
                        == (section.strip() or "").lower()
                    ]

                    if matches:
                        new_item = matches[-1]
                        barcode_value = (
                            get_value(new_item, "barcode")
                            or get_file_id(new_item)
                        )

                        st.success(
                            f"File registered. File ID: {get_file_id(new_item)}"
                        )

                        if barcode_value:
                            try:
                                barcode_path = create_barcode_image(
                                    str(barcode_value)
                                )

                                if barcode_path and Path(barcode_path).exists():
                                    st.image(
                                        barcode_path,
                                        caption=f"Barcode: {barcode_value}",
                                        width=360,
                                    )

                                    with open(barcode_path, "rb") as barcode_file:
                                        st.download_button(
                                            "⬇️ Download Barcode PNG",
                                            data=barcode_file.read(),
                                            file_name=(
                                                f"{get_file_id(new_item) or 'file'}"
                                                "_barcode.png"
                                            ),
                                            mime="image/png",
                                        )
                                else:
                                    st.warning(
                                        "The file was registered, but the "
                                        "barcode image could not be located."
                                    )
                            except Exception as barcode_error:
                                st.warning(
                                    "The file was registered, but barcode "
                                    f"generation failed: {barcode_error}"
                                )
                    else:
                        st.success("File registered successfully.")
                        st.info(
                            "Refresh the file register to view the new record."
                        )

                except Exception as error:
                    st.error(f"Could not register file: {error}")

    st.markdown("### Recently Registered Files")

    current_items = get_all_items()

    if current_items:
        st.dataframe(
            format_file_table(current_items[:10]),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No files have been registered yet.")


# =========================================================
# EXPORT TO EXCEL — ADMIN ONLY
# =========================================================

elif selected_page == "📤 Export to Excel":
    if not is_admin(current_user):
        st.error("Only administrators can export system records.")
        st.stop()

    show_page_header(
        "📤 Export to Excel",
        "Export file register and accountability records for authorized use.",
    )

    st.markdown(
        """
        <div class="panel">
            <strong>Before exporting</strong><br>
            Exported records may contain internal staff and file information.
            Store them securely and share them only with authorized personnel.
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button(
        "Prepare Excel Report",
        type="primary",
        use_container_width=True,
    ):
        try:
            excel_data = create_excel_export()

            if isinstance(excel_data, BytesIO):
                excel_data = excel_data.getvalue()

            st.download_button(
                "⬇️ Download Digital Filing System Report",
                data=excel_data,
                file_name="digital_filing_system_report.xlsx",
                mime=(
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                ),
                use_container_width=True,
            )

            st.success("Your Excel report is ready to download.")
        except Exception as error:
            st.error(f"Could not create Excel export: {error}")
