import pandas as pd
from io import BytesIO

from database import get_items, get_movements, get_users


def create_excel_export():
    items = get_items()
    movements = get_movements()
    users = get_users()

    items_df = pd.DataFrame(items)
    movements_df = pd.DataFrame(movements)
    users_df = pd.DataFrame(users)

    output = BytesIO()

    with pd.ExcelWriter(
        output,
        engine="openpyxl"
    ) as writer:

        items_df.to_excel(
            writer,
            index=False,
            sheet_name="Items"
        )

        movements_df.to_excel(
            writer,
            index=False,
            sheet_name="Movement History"
        )

        users_df.to_excel(
            writer,
            index=False,
            sheet_name="Users"
        )

    output.seek(0)

    return output
