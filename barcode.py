import re


def generate_barcode(file_number):
    """
    Generate a unique barcode value from the file number.

    Example:
        AFA/ICT/001 -> AFA-ICT-001
    """
    barcode_value = file_number.strip().upper()
    barcode_value = re.sub(r"[\s/]+", "-", barcode_value)
    barcode_value = re.sub(r"[^A-Z0-9-]", "", barcode_value)

    return barcode_value
