import pandas as pd
from io import BytesIO


def create_excel_file(files, movements, users):
    """Create an Excel workbook containing system records."""

    files_data = [dict(row) for row in files]
    movements_data = [dict(row) for row in movements]
    users_data = [dict(row) for row in users]

    files_df = pd.DataFrame(files_data)
    movements_df = pd.DataFrame(movements_data)
    users_df = pd.DataFrame(users_data)

    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        files_df.to_excel(
            writer,
            sheet_name="File Register",
            index=False,
        )

        movements_df.to_excel(
            writer,
            sheet_name="Movement History",
            index=False,
        )

        users_df.to_excel(
            writer,
            sheet_name="Users",
            index=False,
        )

    output.seek(0)
    return output
