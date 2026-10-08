import streamlit as st

from database import (
    initialize_database,
    add_user,
    authenticate_user,
    create_first_admin,
    has_users,
    acknowledge_oath,
    add_item,
    get_items,
    find_item,
    issue_item,
    return_item,
    get_movements,
    get_notifications,
)

from export import create_excel_export

from barcode import create_barcode_image


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
# CUSTOM UI
# =========================================================

st.markdown(
    """
    <style>

    .stApp {
        background-color: #f6f8fb;
    }

    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
        max-width: 1400px;
    }

    /* SIDEBAR */

    section[data-testid="stSidebar"] {
        background-color: #111827;
    }

    section[data-testid="stSidebar"] * {
        color: white;
    }

    section[data-testid="stSidebar"] .stRadio label {
        color: #e5e7eb;
    }

    /* HEADINGS */

    h1 {
        font-weight: 700;
        color: #111827;
    }

    h2,
    h3 {
        color: #1f2937;
    }

    /* METRIC CARDS */

    div[data-testid="stMetric"] {
        background-color: white;
        border: 1px solid #e5e7eb;
        border-radius: 14px;
        padding: 18px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
    }

    div[data-testid="stMetricLabel"] {
        font-weight: 600;
    }

    /* BUTTONS */

    .stButton > button {
        border-radius: 9px;
        font-weight: 600;
        min-height: 42px;
    }

    /* INPUTS */

    input,
    textarea {
        border-radius: 8px !important;
    }

    /* CARDS */

    .custom-card {
        background: white;
        padding: 24px;
        border-radius: 14px;
        border: 1px solid #e5e7eb;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
        margin-bottom: 20px;
    }

    .scan-card {
        background: white;
        padding: 35px;
        border-radius: 16px;
        border: 2px dashed #9ca3af;
        text-align: center;
        margin-bottom: 25px;
    }

    .barcode-card {
        background: white;
        padding: 25px;
        border-radius: 14px;
        border: 1px solid #e5e7eb;
        text-align: center;
    }

    .status-available {
        color: #15803d;
        font-weight: 700;
    }

    .status-out {
        color: #dc2626;
        font-weight: 700;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# DATABASE
# =========================================================

initialize_database()


# =========================================================
# SESSION STATE
# =========================================================

if "logged_in_user" not in st.session_state:
    st.session_state.logged_in_user = None

if "scanned_item" not in st.session_state:
    st.session_state.scanned_item = None


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def get_role():
    user = st.session_state.logged_in_user

    if user:
        return user["role"]

    return None


def is_admin():
    return get_role() == "Admin"


def is_view_only():
    return get_role() == "View Only"


def clear_scanned_item():
    st.session_state.scanned_item = None


# =========================================================
# SIDEBAR BRANDING
# =========================================================

st.sidebar.markdown(
    """
    <div style="
        text-align:center;
        padding:15px 5px 25px 5px;
    ">
        <div style="font-size:42px;">📁</div>

        <div style="
            font-size:20px;
            font-weight:700;
            color:white;
        ">
            DIGITAL FILING SYSTEM
        </div>

        <div style="
            font-size:12px;
            color:#9ca3af;
            margin-top:5px;
        ">
            Physical File Tracking & Accountability
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# FIRST ADMINISTRATOR SETUP
# =========================================================

if not has_users():

    st.title("📁 Digital Filing System")

    st.subheader("Create First Administrator")

    st.info(
        "No users have been registered yet. "
        "Create the first administrator account to begin."
    )

    with st.form("first_admin_form"):

        admin_name = st.text_input(
            "Full Name",
            placeholder="Enter full name",
        )

        admin_email = st.text_input(
            "Organization Email",
            placeholder="name@organization.org",
        )

        admin_department = st.text_input(
            "Department",
            placeholder="Department",
        )

        admin_section = st.text_input(
            "Section (Optional)",
            placeholder="Section",
        )

        admin_staff_number = st.text_input(
            "Staff Number",
            placeholder="Staff number",
        )

        admin_password = st.text_input(
            "Password",
            type="password",
            placeholder="Minimum 8 characters",
        )

        admin_confirm_password = st.text_input(
            "Confirm Password",
            type="password",
        )

        create_admin = st.form_submit_button(
            "Create Administrator",
            use_container_width=True,
        )

    if create_admin:

        if not admin_name.strip():

            st.error(
                "Please enter the administrator's name."
            )

        elif not admin_email.strip():

            st.error(
                "Please enter the organization email."
            )

        elif not admin_department.strip():

            st.error(
                "Please enter the department."
            )

        elif not admin_staff_number.strip():

            st.error(
                "Please enter the staff number."
            )

        elif not admin_password:

            st.error(
                "Please create a password."
            )

        elif len(admin_password) < 8:

            st.error(
                "Password must contain at least 8 characters."
            )

        elif admin_password != admin_confirm_password:

            st.error(
                "The passwords do not match."
            )

        else:

            success, message = create_first_admin(
                admin_name.strip(),
                admin_email.strip(),
                admin_department.strip(),
                admin_section.strip(),
                admin_staff_number.strip(),
                admin_password,
            )

            if success:

                st.success(message)

                st.info(
                    "You can now log in using your "
                    "staff number and password."
                )

                st.rerun()

            else:

                st.error(message)

    st.stop()


# =========================================================
# LOGIN
# =========================================================

if st.session_state.logged_in_user is None:

    st.markdown(
        """
        <div style="
            text-align:center;
            padding:30px 0 15px 0;
        ">

            <div style="font-size:65px;">📁</div>

            <h1>Digital Filing System</h1>

            <p style="color:#6b7280;">
                Physical File Tracking & Accountability
            </p>

        </div>
        """,
        unsafe_allow_html=True,
    )

    login_col1, login_col2, login_col3 = st.columns(
        [1, 2, 1]
    )

    with login_col2:

        st.markdown(
            '<div class="custom-card">',
            unsafe_allow_html=True,
        )

        st.subheader("🔐 Sign In")

        st.write(
            "Enter your staff number and password "
            "to access the system."
        )

        with st.form("login_form"):

            staff_number = st.text_input(
                "Staff Number",
                placeholder="Enter your staff number",
            )

            password = st.text_input(
                "Password",
                type="password",
                placeholder="Enter your password",
            )

            login_button = st.form_submit_button(
                "🔐 Login",
                use_container_width=True,
            )

        st.markdown(
            "</div>",
            unsafe_allow_html=True,
        )

    if login_button:

        if not staff_number.strip() or not password:

            st.error(
                "Please enter your staff number and password."
            )

        else:

            user = authenticate_user(
                staff_number.strip(),
                password,
            )

            if user:

                st.session_state.logged_in_user = user

                st.rerun()

            else:

                st.error(
                    "Invalid staff number or password."
                )

    st.stop()


# =========================================================
# CURRENT USER
# =========================================================

current_user = st.session_state.logged_in_user


# =========================================================
# SIDEBAR USER INFORMATION
# =========================================================

st.sidebar.markdown("---")

st.sidebar.markdown(
    f"""
    <div style="
        background:#1f2937;
        padding:15px;
        border-radius:10px;
        margin-bottom:15px;
    ">

        <div style="
            font-size:12px;
            color:#9ca3af;
        ">
            SIGNED IN AS
        </div>

        <div style="
            font-size:16px;
            font-weight:700;
            margin-top:5px;
        ">
            {current_user['name']}
        </div>

        <div style="
            font-size:12px;
            color:#d1d5db;
            margin-top:4px;
        ">
            {current_user['staff_number']}
        </div>

        <div style="
            font-size:12px;
            color:#93c5fd;
            margin-top:6px;
        ">
            {current_user['role']}
        </div>

    </div>
    """,
    unsafe_allow_html=True,
)


if st.sidebar.button(
    "🚪 Logout",
    use_container_width=True,
):

    st.session_state.logged_in_user = None
    st.session_state.scanned_item = None

    st.rerun()


# =========================================================
# NAVIGATION
# =========================================================

menu = [
    "🏠 Dashboard",
    "📷 Scan / Issue / Return File",
    "🔎 Search Files",
    "📋 Movement History",
    "🔔 Sona Notifications",
    "📜 Oath & Responsibilities",
    "📊 Export to Excel",
]

if is_admin():

    menu.insert(
        1,
        "👤 Register User",
    )

    menu.insert(
        2,
        "📁 Register File",
    )


page = st.sidebar.radio(
    "Navigation",
    menu,
)


# =========================================================
# DASHBOARD
# =========================================================

if page == "🏠 Dashboard":

    st.title("📁 Dashboard")

    st.write(
        f"Welcome back, **{current_user['name']}**."
    )

    st.caption(
        f"Role: {current_user['role']}  |  "
        f"Staff Number: {current_user['staff_number']}"
    )

    st.divider()

    items = get_items()

    total_files = len(items)

    available_files = len([
        item
        for item in items
        if item["status"] == "AVAILABLE"
    ])

    files_out = len([
        item
        for item in items
        if item["status"] == "BORROWED"
    ])

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "📁 Total Files",
        total_files,
    )

    col2.metric(
        "🟢 Available Files",
        available_files,
    )

    col3.metric(
        "🔴 Files Out",
        files_out,
    )

    st.divider()

    st.subheader("⚡ Quick Actions")

    action1, action2, action3 = st.columns(3)

    with action1:

        if st.button(
            "📷 Scan File",
            use_container_width=True,
        ):

            st.info(
                "Select 'Scan / Issue / Return File' "
                "from the sidebar."
            )

    with action2:

        if is_admin():

            if st.button(
                "📁 Register File",
                use_container_width=True,
            ):

                st.info(
                    "Select 'Register File' "
                    "from the sidebar."
                )

    with action3:

        if st.button(
            "🔎 Search Files",
            use_container_width=True,
        ):

            st.info(
                "Select 'Search Files' "
                "from the sidebar."
            )

    st.divider()

    st.subheader("🔴 Currently Out")

    files_out_list = [
        item
        for item in items
        if item["status"] == "BORROWED"
    ]

    if files_out_list:

        for item in files_out_list:

            with st.container():

                st.markdown(
                    '<div class="custom-card">',
                    unsafe_allow_html=True,
                )

                col1, col2, col3 = st.columns(
                    [2, 1, 1]
                )

                with col1:

                    st.markdown(
                        f"### 📁 {item['title']}"
                    )

                    st.caption(
                        f"File ID: {item['item_id']}"
                    )

                with col2:

                    st.write("**Current Holder**")

                    st.write(
                        item["current_holder"]
                        or "Unknown"
                    )

                with col3:

                    st.write("**Section**")

                    st.write(
                        item["section"]
                        or "Not specified"
                    )

                st.markdown(
                    "</div>",
                    unsafe_allow_html=True,
                )

    else:

        st.success(
            "🟢 No files are currently out."
        )


# =========================================================
# REGISTER USER
# =========================================================

elif page == "👤 Register User":

    if not is_admin():

        st.error(
            "Only administrators can register users."
        )

        st.stop()

    st.title("👤 Register User")

    st.write(
        "Create an account for a staff member."
    )

    with st.form("register_user"):

        name = st.text_input(
            "Full Name",
            placeholder="Full name",
        )

        email = st.text_input(
            "Organization Email",
            placeholder="name@organization.org",
        )

        department = st.text_input(
            "Department",
            placeholder="Department",
        )

        section = st.text_input(
            "Section (Optional)",
            placeholder="Section",
        )

        staff_number = st.text_input(
            "Staff Number",
            placeholder="Staff number",
        )

        role = st.selectbox(
            "Access Role",
            [
                "User",
                "View Only",
                "Admin",
            ],
        )

        password = st.text_input(
            "Temporary Password",
            type="password",
            placeholder="Minimum 8 characters",
        )

        confirm_password = st.text_input(
            "Confirm Password",
            type="password",
        )

        submitted = st.form_submit_button(
            "👤 Register User",
            use_container_width=True,
        )

    if submitted:

        if (
            not name.strip()
            or not email.strip()
            or not department.strip()
            or not staff_number.strip()
            or not password
        ):

            st.error(
                "Please fill in all required fields."
            )

        elif len(password) < 8:

            st.error(
                "Password must contain at least 8 characters."
            )

        elif password != confirm_password:

            st.error(
                "The passwords do not match."
            )

        else:

            success, message = add_user(
                name.strip(),
                email.strip(),
                department.strip(),
                section.strip(),
                staff_number.strip(),
                role,
                password,
            )

            if success:

                st.success(message)

                st.info(
                    f"{name} can now log in using "
                    f"staff number {staff_number}."
                )

                st.rerun()

            else:

                st.error(message)


# =========================================================
# REGISTER FILE
# =========================================================

elif page == "📁 Register File":

    if not is_admin():

        st.error(
            "Only administrators can register files."
        )

        st.stop()

    st.title("📁 Register File")

    st.write(
        "Register a physical file and automatically "
        "generate its unique File ID and barcode."
    )

    st.info(
        "No file number is required. The system "
        "automatically generates a unique File ID."
    )

    with st.form("register_file"):

        title = st.text_input(
            "File Name",
            placeholder="e.g. Procurement Records",
        )

        department = st.text_input(
            "Department",
            placeholder="Department",
        )

        section = st.text_input(
            "Section (Optional)",
            placeholder="Section",
        )

        submitted = st.form_submit_button(
            "📁 Register File",
            use_container_width=True,
        )

    if submitted:

        if not title.strip():

            st.error(
                "Please enter the file name."
            )

        elif not department.strip():

            st.error(
                "Please enter the department."
            )

        else:

            success, result = add_item(
                title.strip(),
                department.strip(),
                section.strip(),
            )

            if success:

                st.success(
                    "File registered successfully!"
                )

                st.subheader("Generated File ID")

                st.code(
                    result["item_id"],
                    language=None,
                )

                st.subheader("📊 Generated Barcode")

                try:

                    barcode_path = create_barcode_image(
                        result["item_id"]
                    )

                    st.image(
                        str(barcode_path),
                        caption=(
                            f"Barcode for "
                            f"{result['item_id']}"
                        ),
                        width=500,
                    )

                    with open(
                        barcode_path,
                        "rb",
                    ) as barcode_file:

                        st.download_button(
                            label="⬇️ Download Barcode",
                            data=barcode_file,
                            file_name=(
                                f"{result['item_id']}.png"
                            ),
                            mime="image/png",
                            use_container_width=True,
                        )

                    st.success(
                        "Barcode generated successfully. "
                        "Download and print it, then attach "
                        "it to the physical file."
                    )

                except Exception as error:

                    st.error(
                        "The file was registered, but the "
                        f"barcode could not be generated: {error}"
                    )

            else:

                st.error(result)


# =========================================================
# SCAN / ISSUE / RETURN FILE
# =========================================================

elif page == "📷 Scan / Issue / Return File":

    st.title("📷 Scan / Issue / Return File")

    st.write(
        "Scan the barcode attached to the physical file "
        "to record its movement."
    )

    if is_view_only():

        st.info(
            "👁 View Only access: you can scan and view "
            "file information, but you cannot issue or "
            "return files."
        )

    st.markdown(
        """
        <div class="scan-card">

            <div style="font-size:55px;">📷</div>

            <h2>Scan File Barcode</h2>

            <p>
                Place your cursor in the field below and
                scan the barcode attached to the physical file.
            </p>

        </div>
        """,
        unsafe_allow_html=True,
    )

    barcode_input = st.text_input(
        "Barcode",
        placeholder="Scan barcode here...",
        label_visibility="collapsed",
    )

    if barcode_input.strip():

        item = find_item(
            barcode_input.strip()
        )

        if not item:

            st.error(
                "❌ No file was found with that barcode."
            )

            st.caption(
                "Check that the barcode is registered "
                "correctly and try again."
            )

        else:

            st.session_state.scanned_item = item

    item = st.session_state.scanned_item

    if item:

        st.divider()

        st.subheader("📁 File Information")

        info1, info2 = st.columns(2)

        with info1:

            st.markdown(
                f"### {item['title']}"
            )

            st.write(
                f"**File ID:** {item['item_id']}"
            )

            st.write(
                f"**Department:** {item['department']}"
            )

            st.write(
                f"**Section:** "
                f"{item['section'] or 'Not specified'}"
            )

        with info2:

            st.write(
                f"**Barcode:** {item['barcode']}"
            )

            if item["status"] == "AVAILABLE":

                st.markdown(
                    """
                    <p class="status-available">
                    🟢 AVAILABLE
                    </p>
                    """,
                    unsafe_allow_html=True,
                )

            else:

                st.markdown(
                    """
                    <p class="status-out">
                    🔴 FILE OUT
                    </p>
                    """,
                    unsafe_allow_html=True,
                )

            if item["current_holder"]:

                st.write(
                    f"**Current Holder:** "
                    f"{item['current_holder']}"
                )

        st.divider()

        if not is_view_only():

            remarks = st.text_area(
                "Remarks (Optional)",
                placeholder="Add any relevant remarks...",
            )

            if item["status"] == "AVAILABLE":

                st.success(
                    "This file is available."
                )

                if st.button(
                    "📤 ISSUE FILE",
                    use_container_width=True,
                ):

                    success, message = issue_item(
                        item["id"],
                        current_user["id"],
                        remarks,
                    )

                    if success:

                        st.success(message)

                        st.session_state.scanned_item = None

                        st.rerun()

                    else:

                        st.error(message)

            else:

                st.warning(
                    f"This file is currently with "
                    f"{item['current_holder']}."
                )

                if (
                    item["current_holder_id"]
                    == current_user["id"]
                ):

                    if st.button(
                        "📥 RETURN FILE",
                        use_container_width=True,
                    ):

                        success, message = return_item(
                            item["id"],
                            current_user["id"],
                            remarks,
                        )

                        if success:

                            st.success(message)

                            st.session_state.scanned_item = None

                            st.rerun()

                        else:

                            st.error(message)

                elif is_admin():

                    st.info(
                        "This file is assigned to another "
                        "user. The current holder should "
                        "normally return it."
                    )

        if st.button(
            "✖ Clear Scan",
            use_container_width=True,
        ):

            clear_scanned_item()

            st.rerun()


# =========================================================
# SEARCH FILES
# =========================================================

elif page == "🔎 Search Files":

    st.title("🔎 Search Files")

    st.write(
        "Search using a File ID, barcode or file name."
    )

    search = st.text_input(
        "Search",
        placeholder="Enter file name, File ID or barcode...",
    )

    if search.strip():

        item = find_item(
            search.strip()
        )

        if item:

            st.success(
                "✅ File found."
            )

            col1, col2 = st.columns(2)

            with col1:

                st.markdown(
                    f"### 📁 {item['title']}"
                )

                st.write(
                    f"**File ID:** {item['item_id']}"
                )

                st.write(
                    f"**Barcode:** {item['barcode']}"
                )

                st.write(
                    f"**Department:** "
                    f"{item['department']}"
                )

            with col2:

                st.write(
                    f"**Section:** "
                    f"{item['section'] or 'Not specified'}"
                )

                if item["status"] == "AVAILABLE":

                    st.success(
                        "🟢 AVAILABLE"
                    )

                else:

                    st.error(
                        "🔴 FILE OUT"
                    )

                    st.write(
                        f"**Current Holder:** "
                        f"{item['current_holder']}"
                    )

        else:

            st.warning(
                "No matching file was found."
            )


# =========================================================
# MOVEMENT HISTORY
# =========================================================

elif page == "📋 Movement History":

    st.title("📋 File Movement History")

    st.write(
        "Complete record of file issues and returns."
    )

    movements = get_movements()

    if movements:

        st.dataframe(
            movements,
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.info(
            "No file movement history is available yet."
        )


# =========================================================
# SONA NOTIFICATIONS
# =========================================================

elif page == "🔔 Sona Notifications":

    st.title("🔔 Sona Notifications")

    st.write(
        "View alerts, notifications and important "
        "system updates."
    )

    notifications = get_notifications(
        current_user["id"]
    )

    if notifications:

        for notification in notifications:

            notification_type = (
                notification["notification_type"]
            )

            if notification_type == "WARNING":

                st.warning(
                    f"**{notification['title']}**\n\n"
                    f"{notification['message']}"
                )

            elif notification_type == "SUCCESS":

                st.success(
                    f"**{notification['title']}**\n\n"
                    f"{notification['message']}"
                )

            else:

                st.info(
                    f"**{notification['title']}**\n\n"
                    f"{notification['message']}"
                )

    else:

        st.info(
            "🔔 No notifications at the moment."
        )


# =========================================================
# OATH & RESPONSIBILITIES
# =========================================================

elif page == "📜 Oath & Responsibilities":

    st.title("📜 Oath & Responsibilities")

    st.info(
        "All users are expected to understand and "
        "follow these responsibilities when using "
        "the Digital Filing System."
    )

    st.subheader(
        "Responsibilities of Filing / System Administrators"
    )

    st.markdown(
        """
        - Maintain accurate records of physical files.
        - Ensure every file is properly registered.
        - Ensure every file has the correct barcode.
        - Ensure barcode scanning is performed during issue and return.
        - Maintain accurate movement and accountability records.
        - Manage user access appropriately.
        - Protect organizational information.
        - Report discrepancies or unauthorized activity.
        - Ensure system records are kept up to date.
        """
    )

    st.divider()

    st.subheader(
        "Responsibilities of System Users"
    )

    st.markdown(
        """
        - Provide accurate personal and staff information.
        - Use only their authorized account/access.
        - Scan every file before taking it.
        - Return borrowed files promptly.
        - Do not transfer files to another person without authorization.
        - Report lost or damaged files immediately.
        - Report incorrect system records.
        - Protect their system access credentials.
        """
    )

    st.divider()

    st.subheader(
        "✍️ User Acknowledgement"
    )

    st.write(
        "I acknowledge that I have read and understood "
        "the responsibilities governing the use of this "
        "system and agree to comply with them."
    )

    if current_user["oath_acknowledged"]:

        st.success(
            f"✅ Oath acknowledged on "
            f"{current_user['oath_date']}"
        )

    else:

        if st.button(
            "✍️ I Acknowledge and Accept",
            use_container_width=True,
        ):

            acknowledge_oath(
                current_user["id"]
            )

            st.success(
                "Your acknowledgement has been recorded."
            )

            st.rerun()


# =========================================================
# EXPORT TO EXCEL
# =========================================================

elif page == "📊 Export to Excel":

    st.title("📊 Export Reports")

    if not is_admin():

        st.warning(
            "Only administrators can export system records."
        )

    else:

        st.write(
            "Export the file register, movement history "
            "and user records."
        )

        if st.button(
            "📊 Prepare Excel Report",
            use_container_width=True,
        ):

            excel_file = create_excel_export()

            st.download_button(
                label="⬇️ Download Excel Report",
                data=excel_file,
                file_name="digital_filing_system_report.xlsx",
                mime=(
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                ),
                use_container_width=True,
            )
