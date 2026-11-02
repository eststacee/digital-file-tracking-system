import io
import pandas as pd
import streamlit as st

from database import (
    initialize_database,
    add_user,
    get_users,
    get_items,
    find_item,
    authenticate_user,
    create_first_admin,
    has_users,
    acknowledge_oath,
    add_item,
    issue_item,
    return_item,
    get_movements,
    get_notifications,
    mark_notifications_read,
    modify_item,
    approve_item,
    soft_delete_item,
    get_audit_trail,
)
from barcode_utils import create_barcode_image


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
# BANKING-STYLE UI
# =========================================================
st.markdown(
    """
    <style>
    .stApp {
        background-color: #F4F7FA;
        color: #243447;
    }

    [data-testid="stSidebar"] {
        background-color: #102A43;
        border-right: 1px solid #29445F;
    }

    [data-testid="stSidebar"] * {
        color: #FFFFFF !important;
    }

    [data-testid="stSidebar"] hr {
        border-color: #456078;
    }

    .brand-title {
        font-size: 27px;
        font-weight: 800;
        color: #102A43;
        margin-bottom: 3px;
    }

    .brand-subtitle {
        color: #64748B;
        font-size: 13px;
        margin-bottom: 22px;
    }

    .section-heading {
        color: #102A43;
        font-size: 20px;
        font-weight: 750;
        margin-top: 15px;
        margin-bottom: 12px;
    }

    .metric-card {
        background: #FFFFFF;
        border: 1px solid #DCE4EC;
        border-radius: 12px;
        padding: 19px;
        min-height: 125px;
        box-shadow: 0 2px 6px rgba(16,42,67,.04);
    }

    .metric-label {
        color: #64748B;
        font-size: 13px;
