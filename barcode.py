from pathlib import Path

import barcode
from barcode.writer import ImageWriter


# =========================================================
# BARCODE DIRECTORY
# =========================================================

BASE_DIR = Path(__file__).resolve().parent

BARCODE_DIR = BASE_DIR / "barcodes"

BARCODE_DIR.mkdir(
    exist_ok=True
)


# =========================================================
# BARCODE VALUE
# =========================================================

def generate_barcode(item_id):
    """
    Converts the system-generated Item ID into
    a scanner-friendly barcode value.

    Example:

    LIB-000001

    becomes:

    LIB000001
    """

    return (
        item_id
        .replace("-", "")
        .replace(" ", "")
        .upper()
    )


# =========================================================
# CREATE BARCODE IMAGE
# =========================================================

def create_barcode_image(item_id):
    """
    Creates a Code 128 barcode PNG.

    The generated file is saved inside:

        barcodes/

    Example:

        barcodes/LIB-000001.png
    """

    barcode_value = generate_barcode(
        item_id
    )

    barcode_class = barcode.get_barcode_class(
        "code128"
    )

    barcode_object = barcode_class(
        barcode_value,
        writer=ImageWriter(),
    )

    output_path = BARCODE_DIR / item_id

    filename = barcode_object.save(
        str(output_path),
        options={
            "write_text": True,
            "module_width": 0.35,
            "module_height": 18,
            "font_size": 10,
            "text_distance": 5,
            "quiet_zone": 6,
        },
    )

    return Path(filename)
