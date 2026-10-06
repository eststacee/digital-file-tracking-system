def generate_barcode(item_id):
    """
    Converts an item ID such as LIB-000001
    into a scanner-friendly barcode value.
    """
    return item_id.replace("-", "").upper()
