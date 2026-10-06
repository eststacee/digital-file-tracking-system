import streamlit as st
import pandas as pd

from database import (
    initialize_database,
    add_user,
    get_users,
    add_file,
    get_files,
    find_file,
    pick_file,
    return_file,
    get_movements,
)

from barcode import generate_barcode
from export import create_excel_file


st.set_page_config(
    page_title="Digital File Tracking System",
    page_icon="📁",
    layout="wide",
)

initialize_database()

st.title("📁 Digital File Tracking System")
st.caption("Digital tracking, retrieval and accountability for physical files")

st.sidebar.title("Navigation")

page = st.sidebar.radio(
    "Select a page",
    [
        "Dashboard",
        "Register User",
        "Register File",
        "Pick / Return File",
        "Search Files",
        "Movement History",
        "Export to Excel",
    ],
)

if page == "Dashboard":
    st.header("Dashboard")

    files = get_files()
    users = get_users()

    total_files = len(files)
    available_files = sum(file["status"] == "AVAILABLE" for file in files)
    files_out = sum(file["status"] == "OUT" for file in files)
    total_users = len(users)

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Total Files", total_files)
    col2.metric("Available Files", available_files)
    col3.metric("Files Out", files_out)
    col4.metric("Registered Users", total_users)

    st.divider()
    st.subheader("Currently Out")

    current_files = [file for file in files if file["status"] == "OUT"]

    if current_files:
        current_data = [
            {
                "File Number": file["file_number"],
                "File Name": file["file_name"],
                "Department": file["department"],
                "Current Holder": file["current_holder"],
                "Holder Email": file["holder_email"],
                "Barcode": file["barcode"],
            }
            for file in current_files
        ]

        st.dataframe(
            pd.DataFrame(current_data),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.success("All files are currently available.")

elif page == "Register User":
    st.header("Register User")
    st.write("Add an authorized staff member to the filing system.")

    with st.form("register_user_form"):
        name = st.text_input("Full Name")
        email = st.text_input("Organization Email")
        department = st.text_input("Department")
        staff_number = st.text_input("Staff Number")

        submitted = st.form_submit_button("Register User")

        if submitted:
            if not all([name, email, department, staff_number]):
                st.error("Please fill in all fields.")
            else:
                success, message = add_user(
                    name=name.strip(),
                    email=email.strip().lower(),
                    department=department.strip(),
                    staff_number=staff_number.strip(),
                )

                if success:
                    st.success(message)
                else:
                    st.error(message)

    st.divider()
    st.subheader("Registered Users")

    users = get_users()

    if users:
        users_data = [
            {
                "Name": user["name"],
                "Email": user["email"],
                "Department": user["department"],
                "Staff Number": user["staff_number"],
                "Registered": user["created_at"],
            }
            for user in users
        ]

        st.dataframe(
            pd.DataFrame(users_data),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No users have been registered yet.")

elif page == "Register File":
    st.header("Register Physical File")
    st.write("Register a physical file and create its unique barcode.")

    with st.form("register_file_form"):
        file_number = st.text_input(
            "File Number",
            placeholder="Example: AFA/ICT/001",
        )
        file_name = st.text_input(
            "File Name",
            placeholder="Example: ICT Equipment Records",
        )
        department = st.text_input(
            "Department",
            placeholder="Example: ICT",
        )

        submitted = st.form_submit_button("Register File")

        if submitted:
            if not all([file_number, file_name, department]):
                st.error("Please fill in all fields.")
            else:
                barcode_value = generate_barcode(file_number)

                success, message = add_file(
                    file_number=file_number.strip().upper(),
                    file_name=file_name.strip(),
                    department=department.strip(),
                    barcode=barcode_value,
                )

                if success:
                    st.success(message)
                    st.info(f"Generated Barcode Value: **{barcode_value}**")
                else:
                    st.error(message)

    st.divider()
    st.subheader("Registered Files")

    files = get_files()

    if files:
        files_data = [
            {
                "File Number": file["file_number"],
                "File Name": file["file_name"],
                "Department": file["department"],
                "Barcode": file["barcode"],
                "Status": file["status"],
                "Current Holder": file["current_holder"] or "-",
            }
            for file in files
        ]

        st.dataframe(
            pd.DataFrame(files_data),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No files have been registered yet.")

elif page == "Pick / Return File":
    st.header("Pick / Return File")
    st.write("Enter or scan the file barcode.")

    barcode_input = st.text_input(
        "File Barcode",
        placeholder="Example: AFA-ICT-001",
    )

    if barcode_input:
        file = find_file(barcode_input.strip())

        if not file:
            st.error("No file found with that barcode.")
        else:
            st.subheader("File Information")

            col1, col2 = st.columns(2)

            with col1:
                st.write(f"**File Number:** {file['file_number']}")
                st.write(f"**File Name:** {file['file_name']}")
                st.write(f"**Department:** {file['department']}")

            with col2:
                st.write(f"**Barcode:** {file['barcode']}")

                if file["status"] == "AVAILABLE":
                    st.success("🟢 AVAILABLE")
                else:
                    st.error("🔴 OUT")
                    st.write(f"**Current Holder:** {file['current_holder']}")
                    st.write(f"**Email:** {file['holder_email']}")

            st.divider()

            users = get_users()

            if not users:
                st.warning("Please register at least one user first.")
            else:
                user_options = {
                    f"{user['name']} — {user['staff_number']} — {user['email']}": user["id"]
                    for user in users
                }

                selected_user = st.selectbox(
                    "Staff Member",
                    list(user_options.keys()),
                )

                user_id = user_options[selected_user]

                remarks = st.text_area("Remarks (optional)")

                if file["status"] == "AVAILABLE":
                    if st.button("📤 PICK FILE", type="primary"):
                        success, message = pick_file(
                            file_id=file["id"],
                            user_id=user_id,
                            remarks=remarks,
                        )

                        if success:
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)
                else:
                    if st.button("📥 RETURN FILE", type="primary"):
                        success, message = return_file(
                            file_id=file["id"],
                            user_id=user_id,
                            remarks=remarks,
                        )

                        if success:
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)

elif page == "Search Files":
    st.header("Search Files")

    search = st.text_input(
        "Search by file number, file name or barcode",
        placeholder="Example: AFA-ICT-001",
    )

    if search:
        file = find_file(search.strip())

        if file:
            st.success("File found.")

            col1, col2 = st.columns(2)

            with col1:
                st.write(f"**File Number:** {file['file_number']}")
                st.write(f"**File Name:** {file['file_name']}")
                st.write(f"**Department:** {file['department']}")

            with col2:
                st.write(f"**Barcode:** {file['barcode']}")
                st.write(f"**Status:** {file['status']}")

                if file["current_holder"]:
                    st.write(f"**Current Holder:** {file['current_holder']}")
                    st.write(f"**Email:** {file['holder_email']}")
        else:
            st.warning("No matching file found.")

elif page == "Movement History":
    st.header("File Movement History")

    movements = get_movements()

    if movements:
        movement_data = [
            {
                "File Number": movement["file_number"],
                "File Name": movement["file_name"],
                "Barcode": movement["barcode"],
                "Staff Name": movement["name"],
                "Email": movement["email"],
                "Department": movement["department"],
                "Staff Number": movement["staff_number"],
                "Action": movement["action"],
                "Date & Time": movement["movement_time"],
                "Remarks": movement["remarks"] or "",
            }
            for movement in movements
        ]

        st.dataframe(
            pd.DataFrame(movement_data),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No file movements have been recorded yet.")

elif page == "Export to Excel":
    st.header("Export Records")
    st.write("Download the filing system records as an Excel workbook.")

    files = get_files()
    movements = get_movements()
    users = get_users()

    excel_file = create_excel_file(
        files=files,
        movements=movements,
        users=users,
    )

    st.download_button(
        label="⬇️ Download Excel Report",
        data=excel_file,
        file_name="digital_file_tracking_report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
