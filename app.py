```python
import streamlit as st

from database import (
    initialize_database,
    add_user,
    get_users,
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
    get_notifications
)

from export import create_excel_export


# ---------------------------------------------------------
# PAGE CONFIGURATION
# ---------------------------------------------------------

st.set_page_config(
    page_title="Library Book Tracking System",
    page_icon="📚",
    layout="wide"
)

initialize_database()


# ---------------------------------------------------------
# SESSION STATE
# ---------------------------------------------------------

if "logged_in_user" not in st.session_state:
    st.session_state.logged_in_user = None


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def get_role():
    user = st.session_state.logged_in_user

    if user:
        return user["role"]

    return None


def is_admin():
    return get_role() == "Admin"


def is_view_only():
    return get_role() == "View Only"


# ---------------------------------------------------------
# FIRST ADMIN SETUP / LOGIN
# ---------------------------------------------------------

st.sidebar.title("📚 Library Tracking System")


# ---------------------------------------------------------
# FIRST ADMIN SETUP
# ---------------------------------------------------------

if not has_users():

    st.title("📚 Library Book Tracking System")

    st.header("Create First Administrator")

    st.info(
        "No users have been registered yet. "
        "Create the first administrator account to begin."
    )

    with st.form("first_admin_form"):

        admin_name = st.text_input(
            "Full Name"
        )

        admin_email = st.text_input(
            "Organization Email"
        )

        admin_department = st.text_input(
            "Department"
        )

        admin_section = st.text_input(
            "Section (Optional)"
        )

        admin_staff_number = st.text_input(
            "Staff Number"
        )

        admin_password = st.text_input(
            "Password",
            type="password"
        )

        admin_confirm_password = st.text_input(
            "Confirm Password",
            type="password"
        )

        create_admin = st.form_submit_button(
            "Create Administrator"
        )

    if create_admin:

        if not admin_name:
            st.error(
                "Please enter the administrator's name."
            )

        elif not admin_email:
            st.error(
                "Please enter the organization email."
            )

        elif not admin_department:
            st.error(
                "Please enter the department."
            )

        elif not admin_staff_number:
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
                admin_name,
                admin_email,
                admin_department,
                admin_section,
                admin_staff_number,
                admin_password
            )

            if success:

                st.success(message)

                st.info(
                    "You can now log in using your staff number and password."
                )

                st.rerun()

            else:

                st.error(message)

    st.stop()


# ---------------------------------------------------------
# LOGIN
# ---------------------------------------------------------

if st.session_state.logged_in_user is None:

    st.title("📚 Library Book Tracking System")

    st.subheader("🔐 Sign In")

    st.write(
        "Enter your staff number and password to access the system."
    )

    with st.form("login_form"):

        staff_number = st.text_input(
            "Staff Number",
            placeholder="Enter your staff number"
        )

        password = st.text_input(
            "Password",
            type="password",
            placeholder="Enter your password"
        )

        login_button = st.form_submit_button(
            "🔐 Login"
        )

    if login_button:

        if not staff_number or not password:

            st.error(
                "Please enter your staff number and password."
            )

        else:

            user = authenticate_user(
                staff_number,
                password
            )

            if user:

                st.session_state.logged_in_user = user

                st.rerun()

            else:

                st.error(
                    "Invalid staff number or password."
                )

    st.stop()


# ---------------------------------------------------------
# LOGGED-IN USER
# ---------------------------------------------------------

current_user = st.session_state.logged_in_user


st.sidebar.success(
    f"Logged in as:\n\n"
    f"{current_user['name']}\n\n"
    f"Role: {current_user['role']}"
)


if st.sidebar.button("🚪 Logout"):

    st.session_state.logged_in_user = None

    st.rerun()


# ---------------------------------------------------------
# NAVIGATION
# ---------------------------------------------------------

menu = [
    "Dashboard",
    "Scan / Issue / Return",
    "Search Items",
    "Movement History",
    "Notifications",
    "Oath & Responsibilities",
    "Export to Excel"
]


if is_admin():

    menu.insert(
        1,
        "Register User"
    )

    menu.insert(
        2,
        "Register Book / Item"
    )


page = st.sidebar.radio(
    "Navigation",
    menu
)


# ---------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------

if page == "Dashboard":

    st.title("📚 Library Book Tracking System")

    st.write(
        f"Welcome, **{current_user['name']}**."
    )

    st.caption(
        f"Role: {current_user['role']} | "
        f"Staff Number: {current_user['staff_number']}"
    )

    st.divider()

    st.write(
        "Track books/items, lending, returns and movement history."
    )

    items = get_items()

    total_items = len(items)

    available = len([
        item for item in items
        if item["status"] == "AVAILABLE"
    ])

    borrowed = len([
        item for item in items
        if item["status"] == "BORROWED"
    ])

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Total Items",
        total_items
    )

    col2.metric(
        "Available",
        available
    )

    col3.metric(
        "Borrowed",
        borrowed
    )

    st.divider()

    st.subheader("Currently Borrowed")

    borrowed_items = [
        item for item in items
        if item["status"] == "BORROWED"
    ]

    if borrowed_items:

        for item in borrowed_items:

            st.write(
                f"**{item['title']}** — "
                f"{item['current_holder']}"
            )

            st.caption(
                f"Item ID: {item['item_id']} | "
                f"Department: {item['department']} | "
                f"Section: {item['section'] or 'Not specified'}"
            )

    else:

        st.success(
            "No items are currently borrowed."
        )


# ---------------------------------------------------------
# REGISTER USER
# ---------------------------------------------------------

elif page == "Register User":

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
            "Full Name"
        )

        email = st.text_input(
            "Organization Email"
        )

        department = st.text_input(
            "Department"
        )

        section = st.text_input(
            "Section (Optional)"
        )

        staff_number = st.text_input(
            "Staff Number"
        )

        role = st.selectbox(
            "Access Role",
            [
                "User",
                "View Only",
                "Admin"
            ]
        )

        password = st.text_input(
            "Temporary Password",
            type="password"
        )

        confirm_password = st.text_input(
            "Confirm Password",
            type="password"
        )

        submitted = st.form_submit_button(
            "Register User"
        )

    if submitted:

        if (
            not name
            or not email
            or not department
            or not staff_number
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
                name,
                email,
                department,
                section,
                staff_number,
                role,
                password
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


# ---------------------------------------------------------
# REGISTER BOOK / ITEM
# ---------------------------------------------------------

elif page == "Register Book / Item":

    if not is_admin():

        st.error(
            "Only administrators can register books/items."
        )

        st.stop()

    st.title("📖 Register Book / Item")

    with st.form("regis
```
