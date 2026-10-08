from pathlib import Path
import barcode
from barcode.writer import ImageWriter


BASE_DIR = Path(__file__).resolve().parent
BARCODE_DIR = BASE_DIR / "barcodes"

BARCODE_DIR.mkdir(exist_ok=True)


def generate_barcode(item_id):
    """
    Convert the system Item ID into a scanner-friendly
    barcode value.

    Example:
    LIB-000001 -> LIB000001
    """
    return item_id.replace("-", "").upper()


def create_barcode_image(item_id):
    """
    Generate a Code 128 barcode PNG for the item.
    """

    barcode_value = generate_barcode(item_id)

    barcode_class = barcode.get_barcode_class("code128")

    barcode_object = barcode_class(
        barcode_value,
        writer=ImageWriter()
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
            "quiet_zone": 6
        }
    )

    return Path(filename)
