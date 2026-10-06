# Digital File Tracking System

A Streamlit-based system for registering, tracking, issuing and returning physical books/items.

## Features

- Book/item registration
- Automatically generated Item IDs
- Barcode identification
- Optional Department Section
- Barcode scanning using USB barcode scanners
- Book/item issue tracking
- Book/item return tracking
- Current borrower tracking
- Movement/audit history
- User registration
- Admin access
- Normal user access
- View Only access
- User oath and acknowledgement
- Notifications
- Excel reporting

## Item Identification

The system does not require a manually entered file number.

Each registered item receives a unique system-generated ID.

Example:

LIB-000001

The corresponding scanner value is:

LIB000001

## User Roles

### Admin

Can:

- Register users
- Register books/items
- Issue items
- Return items
- View movement history
- View notifications
- Export reports
- Manage system records

### User

Can:

- View information
- Scan items
- Issue items
- Return items they currently hold
- View movement history

### View Only

Can:

- Search items
- View item information
- View permitted records

View Only users cannot change system records.

## Department and Section

Department is required.

Section is optional and can be left blank.

## Running in GitHub Codespaces

Open the repository in GitHub Codespaces.

Run:

```bash
pip install -r requirements.txt
