
import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime

from database import (
    initialize_database,
    add_user,
    get_users,
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
# BANKING-STYLE INTERFACE
# =========================================================

st.markdown(
    """
    <style>
    .stApp {
        background: #F4F7FA;
        color: #243447;
    }

    [data-testid="stSidebar"] {
        background: #102A43;
    }

    [data-testid="stSidebar"] * {
        color: white !important;
    }

    .brand-title {
        font-size: 27px;
        font-weight: 800;
        color: #102A43;
    }

    .section-heading {
        font-size: 21px;
        font-weight: 750;
        color: #102A43;
        margin-top: 16px;
        margin-bottom: 10px;
    }

    .metric-card {
        background: white;
        border: 1px solid #DCE4EC;
        border-radius: 12px;
        padding: 18px;
    }

    .metric-label {
        color: #64748B;
        font-size: 13px;
    }

    .metric-value {
        color: #102A43;
        font-size: 30px;
        font-weight: 800;
    }

    div[data-testid="stButton"] button,
    div[data-testid="stDownloadButton"] button {
        border-radius: 8px;
        min-height: 40px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# INITIALIZE DATABASE
# =========================================================

initialize_database()


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def value(record, key, default=None):
    if record is None:
        return default

    if isinstance(record, dict):
        return record.get(key, default)

    try:
        return record[key]
    except (KeyError, TypeError, IndexError):
        return default


def is_admin(user):
    return str(value(user, "role", "User")).lower() == "admin"


def is_view_only(user):
    return str(value(user, "role", "User")).lower() == "view only"


def user_id(user):
    return value(user, "id")


def file_id(item):
    return value(item, "file_id", value(item, "barcode", ""))


def file_name(item):
    return value(item, "file_name", "Unnamed file")


def file_status(item):
    return str(value(item, "status", "AVAILABLE")).upper()


def is_out(item):
    return file_status(item) == "OUT"


def can_move_files(user):
    return not is_view_only(user)


def can_modify_file(user, item):
    """
    UI-level ownership check.

    IMPORTANT:
    database.py must enforce the same rule independently.
    """
    if is_admin(user):
        return True

    return str(value(item, "created_by")) == str(user_id(user))


def can_view_file(user, item):
    """
    Option C:
    - Admins can view all files.
    - Users with a section can view files in that section.
    - Users without a section can view files in their department.
    """
    if is_admin(user):
        return True

    user_section = (
        value(user, "section", "") or ""
    ).strip()

    user_department = (
        value(user, "department", "") or ""
    ).strip().casefold()

    item_department = (
        value(item, "department", "") or ""
    ).strip().casefold()

    item_section = (
        value(item, "section", "") or ""
    ).strip()

    if user_section:
        return (
            user_section.casefold() == item_section.casefold()
            and user_department == item_department
        )

    return user_department == item_department


def visible_files(user):
    """
    Filter file rows for presentation.

    This is not a substitute for database-level authorization.
    """
    return [
        item
        for item in (get_items() or [])
        if can_view_file(user, item)
    ]


def header(title, subtitle=""):
    st.markdown(
        f'<div class="brand-title">{title}</div>',
        unsafe_allow_html=True,
    )

    if subtitle:
        st.caption(subtitle)

    st.divider()


def metric_card(label, number, note=""):
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{number}</div>
            <div class="metric-label">{note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def file_dataframe(items):
    rows = []

    for item in items:
        rows.append({
            "File ID": file_id(item),
            "File Name": file_name(item),
            "Department": value(item, "department", ""),
            "Section": value(item, "section", "") or "—",
            "Status": file_status(item),
            "Barcode": value(item, "barcode", ""),
            "Approval": value(item, "approval_status", "—"),
        })

    return pd.DataFrame(rows)


# =========================================================
# FIRST ADMIN SETUP
# =========================================================

if not has_users():
    st.title("📁 Digital Filing System")
    st.subheader("Initial Administrator Setup")

    st.info(
        "Create the first administrator account to set up "
        "the filing system."
    )

    with st.form("first_admin_form"):
        name = st.text_input("Full name")
        email = st.text_input("Organization email")
        department = st.text_input("Department")
        section = st.text_input("Section (optional)")
        staff_number = st.text_input("Staff number")
        password = st.text_input(
            "Create password",
            type="password",
        )
        confirm_password = st.text_input(
            "Confirm password",
            type="password",
        )

        submitted = st.form_submit_button(
            "Create Administrator",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        if not all([
            name.strip(),
            email.strip(),
            department.strip(),
            staff_number.strip(),
            password,
        ]):
            st.error("Complete all required fields.")

        elif password != confirm_password:
            st.error("The passwords do not match.")

        else:
            try:
                create_first_admin(
                    name.strip(),
                    email.strip(),
                    department.strip(),
                    section.strip() or None,
                    staff_number.strip(),
                    password,
                )

                st.success(
                    "Administrator created. You can now sign in."
                )
                st.rerun()

            except Exception as exc:
                st.error(f"Could not create administrator: {exc}")

    st.stop()


# =========================================================
# LOGIN
# =========================================================

if "logged_in_user" not in st.session_state:
    st.session_state.logged_in_user = None

if st.session_state.logged_in_user is None:
    left, center, right = st.columns([1, 1.2, 1])

    with center:
        st.markdown(
            """
            <div style="text-align:center;padding:20px;">
                <div style="font-size:48px;">📁</div>
                <div class="brand-title">Digital Filing System</div>
                <p>Secure file tracking and accountability</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.form("login_form"):
            st.subheader("Sign In")

            staff_number = st.text_input("Staff number")
            password = st.text_input(
                "Password",
                type="password",
            )

            submitted = st.form_submit_button(
                "Sign In",
                type="primary",
                use_container_width=True,
            )

        if submitted:
            account = authenticate_user(
                staff_number.strip(),
                password,
            )

            if account:
                st.session_state.logged_in_user = account
                st.rerun()
            else:
                st.error("Invalid staff number or password.")

    st.stop()


# =========================================================
# CURRENT USER
# =========================================================

current_user = st.session_state.logged_in_user
current_user_id = user_id(current_user)
current_user_name = value(current_user, "name", "Staff Member")
current_department = value(current_user, "department", "—")
current_section = value(current_user, "section", "") or "Not assigned"
current_role = value(current_user, "role", "User")


# =========================================================
# NAVIGATION
# =========================================================

pages = [
    "📊 Dashboard",
    "📁 Register File",
    "🔎 Search Files",
    "📷 Scan / Issue / Return",
    "🕒 Movement History",
    "📜 Audit Trail",
    "🔔 Sona Notifications",
    "📋 Oath & Responsibilities",
]

if is_admin(current_user):
    pages.extend([
        "👤 Register User",
        "✅ File Approvals",
        "📤 Export to Excel",
    ])

with st.sidebar:
    st.markdown("## 📁 Digital Filing System")
    st.caption("File tracking & accountability")
    st.divider()

    st.markdown("### MAIN MENU")

    selected_page = st.radio(
        "Navigation",
        pages,
        label_visibility="collapsed",
    )

    st.divider()
    st.markdown("### SIGNED-IN USER")
    st.write(current_user_name)
    st.caption(f"Department: {current_department}")
    st.caption(f"Section: {current_section}")
    st.caption(f"Role: {current_role}")

    if st.button("🚪 Sign Out", use_container_width=True):
        st.session_state.logged_in_user = None
        st.session_state.pop("scanned_item", None)
        st.session_state.pop("detail_item", None)
        st.rerun()


# =========================================================
# DASHBOARD
# =========================================================

if selected_page == "📊 Dashboard":
    header(
        "📊 Dashboard",
        "Overview of file records and daily operations.",
    )

    items = visible_files(current_user)
    files_out = [item for item in items if is_out(item)]
    available = [
        item for item in items
        if file_status(item) == "AVAILABLE"
    ]

    notifications = get_notifications(current_user_id) or []
    unread = sum(
        1 for note in notifications
        if not value(note, "is_read", 0)
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        metric_card("Visible Files", len(items), "Authorized records")

    with c2:
        metric_card("Available", len(available), "Ready for retrieval")

    with c3:
        metric_card("Files Out", len(files_out), "Currently issued")

    with c4:
        metric_card("Unread Alerts", unread, "Sona notifications")

    st.markdown(
        '<div class="section-heading">⚡ Quick Actions</div>',
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        if st.button("📁 Register New File", use_container_width=True):
            st.session_state.quick_action = "register"
            st.rerun()

    with c2:
        if st.button("🔎 Search Files", use_container_width=True):
            st.session_state.quick_action = "search"
            st.rerun()

    with c3:
        if st.button("🔔 Notifications", use_container_width=True):
            st.session_state.quick_action = "notifications"
            st.rerun()

    quick = st.session_state.pop("quick_action", None)

    if quick == "register":
        st.info("Select Register File in the sidebar.")
    elif quick == "search":
        st.info("Select Search Files in the sidebar.")
    elif quick == "notifications":
        st.info("Select Sona Notifications in the sidebar.")

    st.markdown("### Files Currently Out")

    if files_out:
        st.dataframe(
            file_dataframe(files_out),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.success("No visible files are currently out.")

    st.markdown("### Recent File Activity")

    try:
        movements = get_movements() or []
        if movements:
            st.dataframe(
                pd.DataFrame(movements).head(10),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No file movements recorded yet.")
    except Exception:
        st.info("Movement history is not available.")


# =========================================================
# REGISTER FILE
# =========================================================

elif selected_page == "📁 Register File":
    header(
        "📁 Register File",
        "Register a file and create a barcode label.",
    )

    if is_view_only(current_user):
        st.warning("Your View Only role cannot create files.")
        st.stop()

    with st.form("register_file_form"):
        name = st.text_input("File name")
        department = st.text_input(
            "Department",
            value=str(current_department),
        )
        section = st.text_input(
            "Section",
            value="" if current_section == "Not assigned"
            else str(current_section),
        )

        submitted = st.form_submit_button(
            "Create File",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        if not name.strip() or not department.strip():
            st.error("File name and department are required.")
        else:
            try:
                # IMPORTANT:
                # The secure database implementation must accept the
                # creator's ID, assign PENDING approval and log events.
                #
                # This call matches the legacy database API only.
                created_id = add_item(
                    name.strip(),
                    department.strip(),
                    section.strip() or None,
                )

                st.session_state.new_file_barcode = created_id
                st.success(f"File registered. File ID: {created_id}")

                st.warning(
                    "Connect creator ownership, pending approval, "
                    "and notifications in database.py before using "
                    "this workflow in production."
                )

            except Exception as exc:
                st.error(f"Could not register file: {exc}")

    barcode_value = st.session_state.get("new_file_barcode")

    if barcode_value:
        st.markdown("### Barcode Label")
        st.write(f"File ID / Barcode: **{barcode_value}**")

        try:
            barcode_image = create_barcode_image(barcode_value)

            st.image(
                barcode_image,
                caption=f"Barcode: {barcode_value}",
                width=420,
            )

            if hasattr(barcode_image, "getvalue"):
                image_bytes = barcode_image.getvalue()
            else:
                buffer = BytesIO()
                barcode_image.save(buffer, format="PNG")
                image_bytes = buffer.getvalue()

            st.download_button(
                "🖨️ Download Barcode Label",
                data=image_bytes,
                file_name=f"{barcode_value}_barcode.png",
                mime="image/png",
                use_container_width=True,
            )

        except Exception as exc:
            st.error(
                "Barcode generation failed. Check barcode_utils.py: "
                f"{exc}"
            )


# =========================================================
# SEARCH FILES
# =========================================================

elif selected_page == "🔎 Search Files":
    header(
        "🔎 Search Files",
        "Search authorized files by name, ID, department or barcode.",
    )

    items = visible_files(current_user)

    query = st.text_input(
        "Search",
        placeholder="Enter file name, file ID or barcode",
    )

    if query.strip():
        term = query.strip().casefold()

        items = [
            item for item in items
            if term in " ".join([
                str(file_id(item)),
                str(file_name(item)),
                str(value(item, "department", "")),
                str(value(item, "section", "")),
                str(value(item, "barcode", "")),
            ]).casefold()
        ]

    if items:
        st.dataframe(
            file_dataframe(items),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No matching files were found.")

    st.markdown("### View File Details")

    identifier = st.text_input(
        "File ID or barcode",
        key="detail_identifier",
    )

    if st.button("Find File"):
        item = find_item(identifier.strip()) if identifier.strip() else None

        if item and can_view_file(current_user, item):
            st.session_state.detail_item = item
        else:
            st.session_state.detail_item = None
            st.warning("No accessible file matched that identifier.")

    item = st.session_state.get("detail_item")

    if item and can_view_file(current_user, item):
        st.write("**File ID:**", file_id(item))
        st.write("**File name:**", file_name(item))
        st.write("**Department:**", value(item, "department"))
        st.write("**Section:**", value(item, "section") or "—")
        st.write("**Status:**", file_status(item))

        if can_modify_file(current_user, item) and not is_view_only(current_user):
            st.markdown("### Modify File")

            with st.form("modify_file_form"):
                updated_name = st.text_input(
                    "File name",
                    value=file_name(item),
                )

                save = st.form_submit_button("Save Changes")

            if save:
                st.warning(
                    "The secure update_file() database function "
                    "must be implemented before this form can save "
                    "changes. Do not update the files table directly "
                    "from app.py."
                )
        elif not is_admin(current_user):
            st.caption("You can view this file but cannot modify it.")


# =========================================================
# SCAN / ISSUE / RETURN
# =========================================================

elif selected_page == "📷 Scan / Issue / Return":
    header(
        "📷 Scan / Issue / Return",
        "Scan a barcode or enter the file ID.",
    )

    if is_view_only(current_user):
        st.info("Your role is View Only.")

    st.markdown("### Scan with Camera")

    camera_image = st.camera_input(
        "Point your camera at the barcode",
        key="barcode_camera",
    )

    if camera_image:
        st.info(
            "Camera capture is enabled. Barcode decoding must be "
            "connected in barcode_utils.py to read the image "
            "automatically. You can enter the decoded ID below."
        )

    identifier = st.text_input(
        "File ID or barcode",
        key="movement_identifier",
    )

    if st.button("Find File", type="primary"):
        item = find_item(identifier.strip()) if identifier.strip() else None

        if item and can_view_file(current_user, item):
            st.session_state.scanned_item = item
        else:
            st.session_state.scanned_item = None
            st.warning("File not found or access is not permitted.")

    item = st.session_state.get("scanned_item")

    if item and can_view_file(current_user, item):
        st.write("**File ID:**", file_id(item))
        st.write("**File name:**", file_name(item))
        st.write("**Status:**", file_status(item))
        st.write("**Department:**", value(item, "department"))
        st.write("**Section:**", value(item, "section") or "—")

        if not can_move_files(current_user):
            st.info("Your role does not permit file movements.")
        elif value(item, "approval_status", "APPROVED") == "PENDING":
            st.warning("This file is awaiting approval.")
        else:
            remarks = st.text_input("Movement remarks (optional)")

            if is_out(item):
                holder_id = value(item, "current_holder_id")

                if str(holder_id) == str(current_user_id):
                    if st.button("↩️ Return File"):
                        try:
                            return_item(
                                value(item, "id"),
                                current_user_id,
                                remarks,
                            )
                            st.success("File returned.")
                            st.session_state.scanned_item = None
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Could not return file: {exc}")
                else:
                    st.warning(
                        "This file is currently issued to another user."
                    )
            else:
                if st.button("📤 Issue File to Me"):
                    try:
                        issue_item(
                            value(item, "id"),
                            current_user_id,
                            remarks,
                        )
                        st.success("File issued successfully.")
                        st.session_state.scanned_item = None
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Could not issue file: {exc}")


# =========================================================
# MOVEMENT HISTORY — VIEW ONLY
# =========================================================

elif selected_page == "🕒 Movement History":
    header(
        "🕒 Movement History",
        "Read-only record of file issues and returns.",
    )

    try:
        movements = get_movements() or []

        if not is_admin(current_user):
            accessible_ids = {
                str(value(item, "id"))
                for item in visible_files(current_user)
            }

            movements = [
                movement for movement in movements
                if str(value(movement, "file_id")) in accessible_ids
                or str(value(movement, "system_file_id")) in {
                    str(file_id(item))
                    for item in visible_files(current_user)
                }
            ]

        if movements:
            st.dataframe(
                pd.DataFrame(movements),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No accessible movement records.")
    except Exception as exc:
        st.error(f"Could not load movement history: {exc}")


# =========================================================
# AUDIT TRAIL — STRICTLY READ ONLY
# =========================================================

elif selected_page == "📜 Audit Trail":
    header(
        "📜 Audit Trail",
        "Read-only record of file and system activity.",
    )

    st.info(
        "Audit history must be append-only. This page intentionally "
        "does not provide edit or delete controls."
    )

    # This must be connected to get_audit_logs() in database.py.
    try:
        from database import get_audit_logs

        audit_logs = get_audit_logs(
            user_id=None if is_admin(current_user) else current_user_id
        ) or []

        if audit_logs:
            if not is_admin(current_user):
                allowed_ids = {
                    str(value(item, "id"))
                    for item in visible_files(current_user)
                }

                audit_logs = [
                    log for log in audit_logs
                    if str(value(log, "file_record_id")) in allowed_ids
                    or str(value(log, "actor_id")) == str(current_user_id)
                ]

            st.dataframe(
                pd.DataFrame(audit_logs),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No audit records are available.")
    except ImportError:
        st.warning(
            "Audit display is not connected yet. Add get_audit_logs() "
            "and append-only audit storage to database.py."
        )
    except Exception as exc:
        st.error(f"Could not load audit trail: {exc}")


# =========================================================
# SONA NOTIFICATIONS
# =========================================================

elif selected_page == "🔔 Sona Notifications":
    header(
        "🔔 Sona Notifications",
        "System alerts and file activity notifications.",
    )

    notifications = get_notifications(current_user_id) or []

    if notifications:
        for note in notifications:
            title = value(note, "title", "Notification")
            message = value(note, "message", "")
            created_at = value(note, "created_at", "")
            read = bool(value(note, "is_read", 0))

            with st.container(border=True):
                st.markdown(f"**{title}**")
                st.write(message)
                st.caption(f"{created_at} · {'Read' if read else 'Unread'}")
    else:
        st.info("You have no notifications.")

    if st.button("Mark Notifications as Read"):
        try:
            mark_notifications_read(current_user_id)
            st.success("Notifications marked as read.")
            st.rerun()
        except Exception as exc:
            st.error(f"Could not update notifications: {exc}")


# =========================================================
# OATH & RESPONSIBILITIES
# =========================================================

elif selected_page == "📋 Oath & Responsibilities":
    header(
        "📋 Oath & Responsibilities",
        "Acknowledge your responsibilities when handling files.",
    )

    st.markdown("""
    ### Responsibilities of file users

    - Access only files permitted by your role and department.
    - Keep physical files secure and return them promptly.
    - Scan or verify a file before collection and return.
    - Do not share credentials or bypass access restrictions.
    - Report missing files, errors or unauthorized access.
    - Keep file information confidential.
    - Do not alter another user's file records.
    """)

    acknowledged_at = value(
        current_user,
        "oath_acknowledged_at",
    )

    if acknowledged_at:
        st.success(f"Oath acknowledged: {acknowledged_at}")
    elif st.checkbox("I have read and accept these responsibilities"):
        if st.button("Confirm Acknowledgement"):
            try:
                acknowledge_oath(current_user_id)
                st.success("Acknowledgement recorded.")
                st.rerun()
            except Exception as exc:
                st.error(f"Could not record acknowledgement: {exc}")


# =========================================================
# ADMIN: REGISTER USER
# =========================================================

elif selected_page == "👤 Register User":
    if not is_admin(current_user):
        st.error("Administrator access is required.")
        st.stop()

    header("👤 Register User", "Create an authorized staff account.")

    with st.form("register_user_form"):
        name = st.text_input("Full name")
        email = st.text_input("Organization email")
        department = st.text_input("Department")
        section = st.text_input("Section (optional)")
        staff_number = st.text_input("Staff number")

        role = st.selectbox(
            "Role",
            ["User", "View Only", "Admin"],
        )

        password = st.text_input(
            "Temporary password",
            type="password",
        )

        submitted = st.form_submit_button(
            "Register User",
            type="primary",
        )

    if submitted:
        if not all([
            name.strip(),
            email.strip(),
            department.strip(),
            staff_number.strip(),
            password,
        ]):
            st.error("Complete all required fields.")
        else:
            try:
                add_user(
                    name=name.strip(),
                    email=email.strip(),
                    department=department.strip(),
                    section=section.strip() or None,
                    staff_number=staff_number.strip(),
                    role=role,
                    password=password,
                )

                st.success("User registered successfully.")
                st.rerun()
            except Exception as exc:
                st.error(f"Could not register user: {exc}")

    st.markdown("### Registered Users")

    try:
        users = get_users(active_only=True)
        if users:
            safe_users = [
                {
                    "Name": value(user, "name"),
                    "Email": value(user, "email"),
                    "Department": value(user, "department"),
                    "Section": value(user, "section") or "—",
                    "Staff Number": value(user, "staff_number"),
                    "Role": value(user, "role"),
                }
                for user in users
            ]

            st.dataframe(
                pd.DataFrame(safe_users),
                use_container_width=True,
                hide_index=True,
            )
    except Exception as exc:
        st.error(f"Could not load users: {exc}")


# =========================================================
# ADMIN: APPROVALS
# =========================================================

elif selected_page == "✅ File Approvals":
    if not is_admin(current_user):
        st.error("Administrator access is required.")
        st.stop()

    header(
        "✅ File Approvals",
        "Review newly registered files before activation.",
    )

    try:
        from database import get_pending_files, approve_file

        pending = get_pending_files() or []

        if not pending:
            st.success("No files are awaiting approval.")

        for item in pending:
            with st.container(border=True):
                st.markdown(f"**{file_name(item)}**")
                st.write("File ID:", file_id(item))
                st.write("Department:", value(item, "department"))
                st.write("Section:", value(item, "section") or "—")

                col1, col2 = st.columns(2)

                with col1:
                    if st.button(
                        "Approve",
                        key=f"approve_{value(item, 'id')}",
                        type="primary",
                    ):
                        approve_file(
                            value(item, "id"),
                            current_user_id,
                        )
                        st.success("File approved.")
                        st.rerun()

                with col2:
                    st.caption("Approval actions are recorded in the audit trail.")

    except ImportError:
        st.warning(
            "Approval workflow requires get_pending_files() and "
            "approve_file() in database.py."
        )
    except Exception as exc:
        st.error(f"Could not load approvals: {exc}")


# =========================================================
# ADMIN: EXPORT TO EXCEL
# =========================================================

elif selected_page == "📤 Export to Excel":
    if not is_admin(current_user):
        st.error("Administrator access is required.")
        st.stop()

    header(
        "📤 Export to Excel",
        "Export registered file records.",
    )

    items = get_items() or []

    if items:
        df = file_dataframe(items)
        st.dataframe(df, use_container_width=True, hide_index=True)

        if st.button("Prepare Excel Export", type="primary"):
            try:
                export_result = create_excel_export(items)

                if isinstance(export_result, bytes):
                    excel_bytes = export_result
                elif hasattr(export_result, "getvalue"):
                    excel_bytes = export_result.getvalue()
                else:
                    buffer = BytesIO()
                    df.to_excel(buffer, index=False)
                    excel_bytes = buffer.getvalue()

                st.download_button(
                    "Download Excel File",
                    data=excel_bytes,
                    file_name="digital_filing_system.xlsx",
                    mime=(
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    ),
                )
            except Exception as exc:
                st.error(f"Could not prepare export: {exc}")
    else:
        st.info("There are no records to export.")
