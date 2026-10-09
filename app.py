
import sqlite3
import streamlit as st

from barcode_utils import create_barcode_image
from database import (
    acknowledge_oath,
    add_item,
    add_user,
    authenticate_user,
    create_first_admin,
    find_item,
    get_items,
    get_movements,
    get_notifications,
    has_users,
    initialize_database,
    issue_item,
    mark_notifications_read,
    return_item,
)
from export import create_excel_export


st.set_page_config(
    page_title="Digital Filing System",
    page_icon="📁",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        margin-bottom: 0.1rem;
    }
    .sub-title {
        font-size: 1rem;
        opacity: 0.75;
        margin-bottom: 1.2rem;
    }
    .file-card {
        border: 1px solid rgba(128,128,128,.25);
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 0.8rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

initialize_database()

if "logged_in_user" not in st.session_state:
    st.session_state.logged_in_user = None
if "scanned_item" not in st.session_state:
    st.session_state.scanned_item = None


def user_is_admin():
    user = st.session_state.logged_in_user
    return bool(user and user.get("role") == "Admin")


def page_header(title, description=""):
    st.markdown(
        f'<div class="main-title">{title}</div>',
        unsafe_allow_html=True,
    )
    if description:
        st.markdown(
            f'<div class="sub-title">{description}</div>',
            unsafe_allow_html=True,
        )


# FIRST ADMIN SETUP
if not has_users():
    page_header(
        "Digital Filing System",
        "First-time administrator setup",
    )
    st.info(
        "No user account exists yet. "
        "Create the first administrator to continue."
    )

    with st.form("first_admin_form"):
        name = st.text_input("Full Name")
        email = st.text_input("Organization Email")
        department = st.text_input("Department")
        section = st.text_input("Section (Optional)")
        staff_number = st.text_input("Staff Number")
        password = st.text_input("Password", type="password")
        confirm_password = st.text_input(
            "Confirm Password",
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
            st.error("Please complete all required fields.")
        elif password != confirm_password:
            st.error("Passwords do not match.")
        elif len(password) < 8:
            st.error("Password must be at least 8 characters long.")
        else:
            try:
                create_first_admin(
                    name=name,
                    email=email,
                    department=department,
                    section=section,
                    staff_number=staff_number,
                    password=password,
                )
                st.success(
                    "Administrator created. You can now log in."
                )
                st.rerun()
            except sqlite3.IntegrityError:
                st.error(
                    "That email or staff number is already in use."
                )
            except Exception as exc:
                st.error(str(exc))

    st.stop()


# LOGIN
if st.session_state.logged_in_user is None:
    page_header(
        "Digital Filing System",
        "Physical File Tracking & Accountability",
    )

    left, right = st.columns(2)

    with left:
        st.subheader("Sign In")

        with st.form("login_form"):
            staff_number = st.text_input("Staff Number")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button(
                "Sign In",
                type="primary",
                use_container_width=True,
            )

        if submitted:
            user = authenticate_user(staff_number, password)

            if user:
                st.session_state.logged_in_user = user
                st.session_state.scanned_item = None
                st.rerun()
            else:
                st.error("Invalid staff number or password.")

    with right:
        st.info(
            "Sign in using your staff number and password. "
            "View Only users can search and view file information "
            "but cannot issue or return files."
        )

    st.stop()


current_user = st.session_state.logged_in_user


# SIDEBAR
st.sidebar.markdown("# 📁 DIGITAL FILING SYSTEM")
st.sidebar.caption("Physical File Tracking & Accountability")
st.sidebar.divider()
st.sidebar.write(f"**{current_user['name']}**")
st.sidebar.caption(
    f"{current_user['role']} · {current_user['staff_number']}"
)

pages = [
    "📊 Dashboard",
    "📷 Scan / Issue / Return File",
    "🔎 Search Files",
    "🕒 Movement History",
    "🔔 Sona Notifications",
    "📜 Oath & Responsibilities",
]

if user_is_admin():
    pages += [
        "👤 Register User",
        "📁 Register File",
        "📤 Export to Excel",
    ]
else:
    pages += ["📤 Export to Excel"]

page = st.sidebar.radio("Navigation", pages)

if st.sidebar.button("Log Out", use_container_width=True):
    st.session_state.logged_in_user = None
    st.session_state.scanned_item = None
    st.rerun()


# DASHBOARD
if page == "📊 Dashboard":
    page_header(
        "Dashboard",
        "Overview of files, accountability and activity",
    )

    items = get_items()
    total = len(items)
    available = sum(
        1 for item in items if item["status"] == "AVAILABLE"
    )
    out_count = total - available

    c1, c2, c3 = st.columns(3)
    c1.metric("Total Files", total)
    c2.metric("Available", available)
    c3.metric("Files Out", out_count)

    st.subheader("Files Currently Out")
    out_items = [
        item for item in items if item["status"] == "OUT"
    ]

    if out_items:
        for item in out_items:
            with st.container(border=True):
                a, b, c = st.columns([2, 2, 1])
                a.write(
                    f"**{item['file_id']} — {item['file_name']}**"
                )
                b.write(
                    f"Holder: "
                    f"{item.get('current_holder_name') or 'Unknown'}"
                )
                c.write(item["status"])
    else:
        st.success("No files are currently out.")


# SCAN / ISSUE / RETURN
elif page == "📷 Scan / Issue / Return File":
    page_header(
        "Scan / Issue / Return File",
        "Scan or type a File ID/barcode to verify and track the file.",
    )

    scanned_value = st.text_input(
        "Scan Barcode",
        placeholder="Place cursor here and scan the physical barcode",
        key="barcode_input",
    )

    search_clicked = st.button("Find File", type="primary")

    if search_clicked:
        item = find_item(scanned_value)

        if item:
            st.session_state.scanned_item = item
        else:
            st.session_state.scanned_item = None
            st.error("No file was found for that barcode/File ID.")

    item = st.session_state.scanned_item

    if item:
        with st.container(border=True):
            st.subheader("File Details")

            a, b, c = st.columns(3)
            a.write(f"**File ID:** {item['file_id']}")
            b.write(f"**File Name:** {item['file_name']}")
            c.write(f"**Status:** {item['status']}")

            a.write(f"**Department:** {item['department']}")
            b.write(f"**Section:** {item.get('section') or '—'}")
            c.write(f"**Barcode:** {item['barcode']}")

            if item["status"] == "OUT":
                st.warning(
                    "Currently held by: "
                    f"{item.get('current_holder_name') or 'Unknown'}"
                )

        if current_user.get("role") == "View Only":
            st.info(
                "View Only access: you can view file records "
                "but cannot issue or return files."
            )
        else:
            remarks = st.text_area(
                "Remarks (Optional)",
                key="movement_remarks",
            )

            col1, col2 = st.columns(2)

            with col1:
                if item["status"] == "AVAILABLE":
                    if st.button(
                        "Issue File",
                        type="primary",
                        use_container_width=True,
                    ):
                        try:
                            issue_item(
                                item["id"],
                                current_user["id"],
                                remarks,
                            )
                            st.success(
                                f"{item['file_id']} has been issued "
                                f"to {current_user['name']}."
                            )
                            st.session_state.scanned_item = find_item(
                                item["file_id"]
                            )
                            st.rerun()
                        except Exception as exc:
                            st.error(str(exc))

            with col2:
                if item["status"] == "OUT":
                    holder_id = item.get("current_holder_id")

                    if (
                        holder_id is not None
                        and int(holder_id) == int(current_user["id"])
                    ):
                        if st.button(
                            "Return File",
                            use_container_width=True,
                        ):
                            try:
                                return_item(
                                    item["id"],
                                    current_user["id"],
                                    remarks,
                                )
                                st.success(
                                    f"{item['file_id']} has been returned."
                                )
                                st.session_state.scanned_item = find_item(
                                    item["file_id"]
                                )
                                st.rerun()
                            except Exception as exc:
                                st.error(str(exc))
                    else:
                        st.info(
                            "Only the current holder can return this file."
                        )


# SEARCH FILES
elif page == "🔎 Search Files":
    page_header(
        "Search Files",
        "Find a file using its File ID or barcode.",
    )

    query = st.text_input("Search File ID / Barcode")

    if st.button("Search", type="primary"):
        item = find_item(query)

        if item:
            st.session_state.scanned_item = item
            st.success("File found.")

            st.dataframe(
                [{
                    "File ID": item["file_id"],
                    "File Name": item["file_name"],
                    "Department": item["department"],
                    "Section": item.get("section") or "",
                    "Barcode": item["barcode"],
                    "Status": item["status"],
                    "Current Holder": (
                        item.get("current_holder_name") or ""
                    ),
                }],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.warning("No matching file found.")

    st.subheader("All Files")
    all_items = get_items()

    st.dataframe(
        [
            {
                "File ID": item["file_id"],
                "File Name": item["file_name"],
                "Department": item["department"],
                "Section": item.get("section") or "",
                "Barcode": item["barcode"],
                "Status": item["status"],
                "Current Holder": (
                    item.get("current_holder_name") or ""
                ),
            }
            for item in all_items
        ],
        use_container_width=True,
        hide_index=True,
    )


# MOVEMENT HISTORY
elif page == "🕒 Movement History":
    page_header(
        "Movement History",
        "Audit trail of file issues and returns.",
    )

    movements = get_movements()

    st.dataframe(
        [
            {
                "File ID": m["system_file_id"],
                "File Name": m["file_name"],
                "User": m["user_name"],
                "Staff Number": m["staff_number"],
                "Action": m["action"],
                "Movement Time": m["movement_time"],
                "Remarks": m["remarks"] or "",
            }
            for m in movements
        ],
        use_container_width=True,
        hide_index=True,
    )


# SONA NOTIFICATIONS
elif page == "🔔 Sona Notifications":
    page_header(
        "Sona Notifications",
        "System alerts and file-accountability updates.",
    )

    notifications = get_notifications(
        current_user["id"],
        include_read=True,
    )
    unread = [
        n for n in notifications if not n["is_read"]
    ]

    c1, c2 = st.columns(2)
    c1.metric("Notifications", len(notifications))
    c2.metric("Unread", len(unread))

    if st.button("Mark All as Read"):
        mark_notifications_read(current_user["id"])
        st.success("Notifications marked as read.")
        st.rerun()

    if not notifications:
        st.info("No notifications yet.")
    else:
        for notification in notifications:
            label = (
                "🔵 UNREAD"
                if not notification["is_read"]
                else "✓ Read"
            )

            with st.container(border=True):
                st.write(
                    f"**{notification['title']}** · {label}"
                )
                st.write(notification["message"])
                st.caption(
                    f"{notification['notification_type']} · "
                    f"{notification['created_at']}"
                )


# OATH & RESPONSIBILITIES
elif page == "📜 Oath & Responsibilities":
    page_header(
        "Oath & Responsibilities",
        "Accountability rules for physical file custody.",
    )

    st.subheader(
        "Staff / Credit or Administration Responsibilities"
    )
    st.markdown(
        """
        - Confirm the physical file and barcode before issuing it.
        - Record every issue and return through the system.
        - Keep the movement history accurate and complete.
        - Report missing, damaged or wrongly issued files immediately.
        """
    )

    st.subheader("User Responsibilities")
    st.markdown(
        """
        - Accept responsibility for files issued under your account.
        - Keep issued files secure and in good condition.
        - Return files promptly after use.
        - Do not hand an issued file to another person without authorization.
        - Report any loss, damage or discrepancy immediately.
        """
    )

    acknowledged_at = current_user.get("oath_acknowledged_at")

    if acknowledged_at:
        st.success(f"Oath acknowledged on {acknowledged_at}.")
    elif st.button(
        "I Acknowledge My Responsibilities",
        type="primary",
    ):
        timestamp = acknowledge_oath(current_user["id"])
        st.session_state.logged_in_user[
            "oath_acknowledged_at"
        ] = timestamp
        st.success("Your acknowledgement has been recorded.")
        st.rerun()


# REGISTER USER — ADMIN ONLY
elif page == "👤 Register User":
    if not user_is_admin():
        st.error("Admin access is required.")
        st.stop()

    page_header(
        "Register User",
        "Create a new organization account.",
    )

    with st.form("register_user_form"):
        name = st.text_input("Full Name")
        email = st.text_input("Organization Email")
        department = st.text_input("Department")
        section = st.text_input("Section (Optional)")
        staff_number = st.text_input("Staff Number")
        role = st.selectbox(
            "Role",
            ["User", "View Only", "Admin"],
        )
        password = st.text_input("Password", type="password")
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
        if not all([
            name.strip(),
            email.strip(),
            department.strip(),
            staff_number.strip(),
            password,
        ]):
            st.error("Please complete all required fields.")
        elif password != confirm_password:
            st.error("Passwords do not match.")
        elif len(password) < 8:
            st.error("Password must be at least 8 characters long.")
        else:
            try:
                add_user(
                    name,
                    email,
                    department,
                    section,
                    staff_number,
                    role,
                    password,
                )
                st.success(
                    f"User {name.strip()} registered successfully."
                )
            except Exception as exc:
                st.error(str(exc))


# REGISTER FILE — ADMIN ONLY
elif page == "📁 Register File":
    if not user_is_admin():
        st.error("Admin access is required.")
        st.stop()

    page_header(
        "Register File",
        "Register a physical file and automatically generate its File ID/barcode.",
    )

    with st.form("register_file_form"):
        file_name = st.text_input("File Name")
        department = st.text_input("Department")
        section = st.text_input("Section (Optional)")
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
                file_id = add_item(
                    file_name,
                    department,
                    section,
                )
                image_path = create_barcode_image(file_id)

                st.success("File registered successfully.")
                st.write(f"**Generated File ID:** {file_id}")
                st.image(
                    image_path,
                    caption=f"Barcode: {file_id}",
                    width=500,
                )

                with open(image_path, "rb") as barcode_file:
                    st.download_button(
                        "Download Barcode PNG",
                        data=barcode_file.read(),
                        file_name=f"{file_id}.png",
                        mime="image/png",
                        use_container_width=True,
                    )
            except Exception as exc:
                st.error(str(exc))


# EXPORT TO EXCEL — ADMIN ONLY
elif page == "📤 Export to Excel":
    if not user_is_admin():
        st.info("Excel export is restricted to administrators.")
    else:
        page_header(
            "Export to Excel",
            "Download the file register, movement history, users and notifications.",
        )

        if st.button("Create Excel Export", type="primary"):
            try:
                workbook = create_excel_export()

                st.download_button(
                    "Download Filing System Excel",
                    data=workbook,
                    file_name="digital_filing_system_export.xlsx",
                    mime=(
                        "application/vnd.openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    ),
                )
            except Exception as exc:
                st.error(str(exc))
