import streamlit as st

from database import (
    initialize_database,
    add_user,
    get_users,
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
# LOGIN / USER SELECTION
# ---------------------------------------------------------

st.sidebar.title("📚 Library Tracking System")

users = get_users()

if not users:
    st.sidebar.info(
        "No users have been registered yet. "
        "An administrator should register the first user."
    )
else:

    user_options = {
        f'{user["name"]} ({user["staff_number"]})': user
        for user in users
    }

    selected_user_name = st.sidebar.selectbox(
        "Current User",
        list(user_options.keys())
    )

    st.session_state.logged_in_user = user_options[
        selected_user_name
    ]


current_user = st.session_state.logged_in_user


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
    menu.insert(1, "Register User")
    menu.insert(2, "Register Book / Item")

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
        st.success("No items are currently borrowed.")


# ---------------------------------------------------------
# REGISTER USER
# ---------------------------------------------------------

elif page == "Register User":

    if not is_admin():
        st.error("Only administrators can register users.")
        st.stop()

    st.title("👤 Register User")

    with st.form("register_user"):

        name = st.text_input("Full Name")

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

        submitted = st.form_submit_button(
            "Register User"
        )

    if submitted:

        if not name or not email or not department or not staff_number:
            st.error(
                "Please fill in all required fields."
            )

        else:

            success, message = add_user(
                name,
                email,
                department,
                section,
                staff_number,
                role
            )

            if success:
                st.success(message)
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

    with st.form("register_item"):

        title = st.text_input(
            "Book / Item Title"
        )

        department = st.text_input(
            "Department"
        )

        section = st.text_input(
            "Section (Optional)"
        )

        submitted = st.form_submit_button(
            "Register Book / Item"
        )

    if submitted:

        if not title or not department:
            st.error(
                "Title and Department are required."
            )

        else:

            success, result = add_item(
                title,
                department,
                section
            )

            if success:

                st.success(
                    "Book/item registered successfully."
                )

                st.info(
                    f"Item ID: {result['item_id']}"
                )

                st.info(
                    f"Barcode: {result['barcode']}"
                )

                st.warning(
                    "Print or attach this barcode to the physical item."
                )

            else:
                st.error(result)


# ---------------------------------------------------------
# SCAN / ISSUE / RETURN
# ---------------------------------------------------------

elif page == "Scan / Issue / Return":

    st.title("📷 Scan / Issue / Return")

    if is_view_only():
        st.info(
            "You have View Only access. "
            "You can search and view item information, "
            "but you cannot issue or return items."
        )

    st.write(
        "Scan the barcode using a USB barcode scanner "
        "or type the barcode manually."
    )

    barcode = st.text_input(
        "Scan Barcode",
        placeholder="Place cursor here and scan..."
    )

    if barcode:

        item = find_item(barcode)

        if not item:

            st.error(
                "No item was found with that barcode."
            )

        else:

            st.subheader(
                f"📖 {item['title']}"
            )

            col1, col2 = st.columns(2)

            with col1:

                st.write(
                    f"**Item ID:** {item['item_id']}"
                )

                st.write(
                    f"**Department:** {item['department']}"
                )

                st.write(
                    f"**Section:** "
                    f"{item['section'] or 'Not specified'}"
                )

            with col2:

                st.write(
                    f"**Barcode:** {item['barcode']}"
                )

                st.write(
                    f"**Status:** {item['status']}"
                )

                if item["current_holder"]:
                    st.write(
                        f"**Current Borrower:** "
                        f"{item['current_holder']}"
                    )

            st.divider()

            if not is_view_only():

                remarks = st.text_area(
                    "Remarks (Optional)"
                )

                if item["status"] == "AVAILABLE":

                    st.success(
                        "This item is available."
                    )

                    if current_user["role"] in [
                        "Admin",
                        "User"
                    ]:

                        if st.button(
                            "📤 ISSUE ITEM"
                        ):

                            success, message = issue_item(
                                item["id"],
                                current_user["id"],
                                remarks
                            )

                            if success:
                                st.success(message)
                                st.rerun()
                            else:
                                st.error(message)

                else:

                    st.warning(
                        f"This item is currently borrowed "
                        f"by {item['current_holder']}."
                    )

                    if item["current_holder_id"] == current_user["id"]:

                        if st.button(
                            "📥 RETURN ITEM"
                        ):

                            success, message = return_item(
                                item["id"],
                                current_user["id"],
                                remarks
                            )

                            if success:
                                st.success(message)
                                st.rerun()
                            else:
                                st.error(message)

                    elif is_admin():

                        st.info(
                            "An administrator can view the "
                            "record, but the current borrower "
                            "should normally return the item."
                        )


# ---------------------------------------------------------
# SEARCH
# ---------------------------------------------------------

elif page == "Search Items":

    st.title("🔎 Search Books / Items")

    search = st.text_input(
        "Search by Item ID, Barcode or Title"
    )

    if search:

        item = find_item(search)

        if item:

            st.success("Item found.")

            st.write(
                f"**Title:** {item['title']}"
            )

            st.write(
                f"**Item ID:** {item['item_id']}"
            )

            st.write(
                f"**Barcode:** {item['barcode']}"
            )

            st.write(
                f"**Department:** {item['department']}"
            )

            st.write(
                f"**Section:** "
                f"{item['section'] or 'Not specified'}"
            )

            st.write(
                f"**Status:** {item['status']}"
            )

            if item["current_holder"]:
                st.write(
                    f"**Current Borrower:** "
                    f"{item['current_holder']}"
                )

        else:

            st.warning(
                "No matching item was found."
            )


# ---------------------------------------------------------
# MOVEMENT HISTORY
# ---------------------------------------------------------

elif page == "Movement History":

    st.title("📋 Movement History")

    movements = get_movements()

    if movements:

        st.dataframe(
            movements,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.info(
            "No movement history is available yet."
        )


# ---------------------------------------------------------
# NOTIFICATIONS
# ---------------------------------------------------------

elif page == "Notifications":

    st.title("🔔 Notifications")

    user_id = None

    if current_user:
        user_id = current_user["id"]

    notifications = get_notifications(user_id)

    if notifications:

        for notification in notifications:

            if notification["notification_type"] == "WARNING":
                st.warning(
                    f"**{notification['title']}**\n\n"
                    f"{notification['message']}"
                )

            elif notification["notification_type"] == "SUCCESS":
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
            "No notifications at the moment."
        )


# ---------------------------------------------------------
# OATH
# ---------------------------------------------------------

elif page == "Oath & Responsibilities":

    st.title("📜 Oath & Responsibilities")

    st.subheader(
        "Responsibilities of Credit / System Administrators"
    )

    st.markdown("""
    - Maintain accurate records of books/items.
    - Ensure every item is properly registered.
    - Ensure barcode scanning is performed during issue and return.
    - Maintain accurate movement and accountability records.
    - Manage user access appropriately.
    - Protect organizational information.
    - Report discrepancies or unauthorized activity.
    - Ensure system records are kept up to date.
    """)

    st.subheader(
        "Responsibilities of System Users"
    )

    st.markdown("""
    - Provide accurate personal and staff information.
    - Use only their authorized account/access.
    - Scan every item before taking it.
    - Return borrowed items promptly.
    - Do not transfer borrowed items to another person without authorization.
    - Report lost or damaged items immediately.
    - Report incorrect system records.
    - Protect their system access credentials.
    """)

    st.divider()

    st.subheader("User Acknowledgement")

    st.write(
        "I acknowledge that I have read and understood "
        "the responsibilities governing the use of this system "
        "and agree to comply with them."
    )

    if current_user:

        if current_user["oath_acknowledged"]:

            st.success(
                f"Oath acknowledged on "
                f"{current_user['oath_date']}"
            )

        else:

            if st.button(
                "I Acknowledge and Accept"
            ):

                acknowledge_oath(
                    current_user["id"]
                )

                st.success(
                    "Your acknowledgement has been recorded."
                )

                st.rerun()


# ---------------------------------------------------------
# EXPORT
# ---------------------------------------------------------

elif page == "Export to Excel":

    st.title("📊 Export to Excel")

    if not is_admin():

        st.warning(
            "Only administrators can export system records."
        )

    else:

        st.write(
            "Export the item register, movement history "
            "and user records."
        )

        if st.button(
            "Prepare Excel Report"
        ):

            excel_file = create_excel_export()

            st.download_button(
                label="⬇️ Download Excel Report",
                data=excel_file,
                file_name="library_tracking_report.xlsx",
                mime=(
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                )
            )
