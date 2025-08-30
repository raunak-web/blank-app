import streamlit as st
import sqlite3
from datetime import date, timedelta
from dataclasses import dataclass, asdict
import re
import uuid
import pandas as pd

# -----------------------------
# App Setup
# -----------------------------
st.set_page_config(
    page_title="Amber Palace Ayodhya – Book Your Stay",
    page_icon="🏯",
    layout="wide",
)

# Minimal brand styling
st.markdown(
    """
    <style>
      .hero {
        padding: 2.2rem 1rem; border-radius: 1.25rem; 
        background: linear-gradient(135deg,#ffd6a5, #fff3b0);
        border: 1px solid #ffecb3; box-shadow: 0 6px 24px rgba(0,0,0,0.08);
      }
      .hero h1 {margin: 0; font-size: 2.1rem}
      .subtle {color: #333; opacity: 0.85}
      .card {border: 1px solid #eee; border-radius: 1rem; padding: 1rem; height: 100%;}
      .pill {display:inline-block;padding:.25rem .6rem;border-radius:999px;background:#111;color:#fff;font-size:.75rem}
      .price {font-weight:800;font-size:1.8rem}
      .muted {color:#666}
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------
# Data & Pricing
# -----------------------------
@dataclass
class Package:
    name: str
    per_night: int  # INR
    description: str
    highlights: list

PACKAGES = {
    "Eco": Package(
        name="Eco",
        per_night=7500,
        description="Comfort essentials for smart travelers.",
        highlights=["AC Deluxe Room", "Wi‑Fi", "24/7 Front Desk", "Temple Info Helpdesk"],
    ),
    "Prime": Package(
        name="Prime",
        per_night=10000,
        description="Premium comfort with added perks.",
        highlights=["Suite Upgrade", "Breakfast Included", "Airport Pickup (One‑way)", "Priority Check‑in"],
    ),
}

ADD_ONS = {
    "Airport Pickup (One-way)": 0,
    "Temple Darshan Guide": 0,
    # "Breakfast Buffet (per guest per night)": 299,
}

TAX_RATE = 0.12  # 12% GST placeholder

# -----------------------------
# Database Utilities
# -----------------------------
DB_PATH = "amber_palace.db"

DDL = """
CREATE TABLE IF NOT EXISTS bookings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,
  ref TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  email TEXT NOT NULL,
  phone TEXT NOT NULL,
  package TEXT NOT NULL,
  check_in TEXT NOT NULL,
  check_out TEXT NOT NULL,
  nights INTEGER NOT NULL,
  guests INTEGER NOT NULL,
  addons TEXT,
  subtotal INTEGER NOT NULL,
  tax INTEGER NOT NULL,
  total INTEGER NOT NULL,
  pay_option TEXT NOT NULL,
  pay_status TEXT NOT NULL,
  notes TEXT
);
"""


def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    with get_conn() as con:
        con.execute(DDL)


init_db()

# -----------------------------
# Helpers
# -----------------------------

def valid_email(x: str) -> bool:
    return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", x or "") is not None


def valid_phone(x: str) -> bool:
    return re.match(r"^[0-9\-\+\s]{7,15}$", x or "") is not None


def nights_between(d1: date, d2: date) -> int:
    return max((d2 - d1).days, 0)


def calc_price(pkg_name: str, nights: int, guests: int, addons: list[str]):
    pkg = PACKAGES[pkg_name]
    room_cost = pkg.per_night * max(nights, 1)
    add_cost = 0
    for a in addons:
        if a == "Breakfast Buffet (per guest per night)":
            add_cost += ADD_ONS[a] * guests * max(nights, 1)
        else:
            add_cost += ADD_ONS[a]
    subtotal = room_cost + add_cost
    tax = int(round(subtotal * TAX_RATE))
    total = subtotal + tax
    return subtotal, tax, total


def create_booking(**kwargs):
    with get_conn() as con:
        cols = (
            "created_at, ref, name, email, phone, package, check_in, check_out, nights, guests, addons, subtotal, tax, total, pay_option, pay_status, notes"
        )
        q = f"INSERT INTO bookings ({cols}) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
        con.execute(
            q,
            (
                kwargs["created_at"],
                kwargs["ref"],
                kwargs["name"],
                kwargs["email"],
                kwargs["phone"],
                kwargs["package"],
                kwargs["check_in"],
                kwargs["check_out"],
                kwargs["nights"],
                kwargs["guests"],
                ", ".join(kwargs.get("addons", [])),
                kwargs["subtotal"],
                kwargs["tax"],
                kwargs["total"],
                kwargs["pay_option"],
                kwargs["pay_status"],
                kwargs.get("notes", ""),
            ),
        )
        con.commit()


def find_booking(email: str, ref: str | None = None):
    with get_conn() as con:
        if ref:
            cur = con.execute(
                "SELECT * FROM bookings WHERE email = ? AND ref = ? ORDER BY id DESC LIMIT 1",
                (email, ref),
            )
        else:
            cur = con.execute(
                "SELECT * FROM bookings WHERE email = ? ORDER BY id DESC LIMIT 1",
                (email,),
            )
        row = cur.fetchone()
        if not row:
            return None
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, row))


# -----------------------------
# UI – Hero
# -----------------------------
with st.container():
    st.markdown(
        """
        <div class="hero">
          <span class="pill">Amber Palace, Ayodhya</span>
          <h1>Book your Ayodhya getaway</h1>
          <p class="subtle">Choose Eco or Prime. Reserve now and pay later—simple, fast, and flexible.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.write("")

# -----------------------------
# Packages Grid
# -----------------------------
col1, col2 = st.columns(2, gap="large")

for col, key in zip((col1, col2), ("Eco", "Prime")):
    pkg = PACKAGES[key]
    with col:
        with st.container(border=True):
            st.markdown(f"### {pkg.name}")
            st.markdown(f"<div class='price'>₹{pkg.per_night:,} <span class='muted'>/ night</span></div>", unsafe_allow_html=True)
            st.caption(pkg.description)
            for h in pkg.highlights:
                st.write("• ", h)
            st.button(
                f"Select {pkg.name}",
                key=f"select_{pkg.name}",
                use_container_width=True,
                type="primary" if pkg.name == "Prime" else "secondary",
                on_click=lambda k=pkg.name: st.session_state.update(selected_package=k),
            )

# Ensure default selection
if "selected_package" not in st.session_state:
    st.session_state.selected_package = "Eco"

st.divider()

# -----------------------------
# Booking Tabs
# -----------------------------
book_tab, find_tab, admin_tab = st.tabs(["Book Now", "Find My Booking", "Admin"])

with book_tab:
    st.subheader("Reserve your package")

    today = date.today()
    default_in = today + timedelta(days=1)
    default_out = default_in + timedelta(days=1)

    with st.form("booking_form", clear_on_submit=False):
        left, right = st.columns(2)
        with left:
            name = st.text_input("Full Name *")
            email = st.text_input("Email *")
            phone = st.text_input("Phone *")
            package = st.selectbox(
                "Choose Package *",
                list(PACKAGES.keys()),
                index=list(PACKAGES.keys()).index(st.session_state.selected_package),
            )
            guests = st.number_input("Guests *", min_value=1, max_value=8, value=2, step=1)
        with right:
            check_in = st.date_input("Check‑in *", value=default_in, min_value=today)
            check_out = st.date_input("Check‑out *", value=default_out, min_value=default_in + timedelta(days=1))
            addons = st.multiselect("Add‑ons (optional)", list(ADD_ONS.keys()))
            pay_option = st.radio(
                "Payment Option *",
                ["Pay Later (reserve now)", "Mark as Paid (test)"],
                index=0,
            )
            notes = st.text_area("Special Requests (optional)")

        # Live price preview
        nights = nights_between(check_in, check_out)
        if nights <= 0:
            st.warning("Check‑out must be after check‑in.")
        subtotal, tax, total = calc_price(package, nights or 1, guests, addons)

        with st.expander("Price details", expanded=True):
            st.write(f"Nights: **{max(nights,1)}** @ ₹{PACKAGES[package].per_night:,}/night")
            if addons:
                st.write("Add‑ons:")
                for a in addons:
                    if a == "Breakfast Buffet (per guest per night)":
                        st.write(f"• {a}: ₹{ADD_ONS[a]:,} × {guests} guests × {max(nights,1)} nights")
                    else:
                        st.write(f"• {a}: ₹{ADD_ONS[a]:,}")
            st.write(f"Subtotal: **₹{subtotal:,}**")
            st.write(f"Tax (12%): **₹{tax:,}**")
            st.write(f"Total: **₹{total:,}**")

        agree = st.checkbox("I agree to the hotel policies and pay‑later terms (hold valid 24 hours). *")
        submitted = st.form_submit_button("Confirm Reservation", type="primary")

    if submitted:
        errors = []
        if not name.strip():
            errors.append("Name is required.")
        if not valid_email(email):
            errors.append("A valid email is required.")
        if not valid_phone(phone):
            errors.append("A valid phone is required.")
        if nights <= 0:
            errors.append("Check‑out must be after check‑in.")
        if not agree:
            errors.append("You must accept the terms.")

        if errors:
            st.error("\n".join(errors))
        else:
            ref = f"AP-{today.strftime('%y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
            pay_status = "Pay Later" if pay_option.startswith("Pay Later") else "Paid"

            record = dict(
                created_at=str(pd.Timestamp.now(tz="Asia/Kolkata")),
                ref=ref,
                name=name.strip(),
                email=email.strip().lower(),
                phone=phone.strip(),
                package=package,
                check_in=str(check_in),
                check_out=str(check_out),
                nights=max(nights, 1),
                guests=int(guests),
                addons=addons,
                subtotal=int(subtotal),
                tax=int(tax),
                total=int(total),
                pay_option="Pay Later" if pay_option.startswith("Pay Later") else "Paid (test)",
                pay_status=pay_status,
                notes=notes.strip(),
            )
            try:
                create_booking(**record)
                st.success("Reservation confirmed! Your reference is " + ref)
                with st.container(border=True):
                    st.markdown(f"**Guest:** {record['name']}  ")
                    st.markdown(f"**Package:** {record['package']}  ")
                    st.markdown(f"**Dates:** {record['check_in']} → {record['check_out']}  ")
                    st.markdown(f"**Guests:** {record['guests']}  ")
                    st.markdown(f"**Total:** ₹{record['total']:,}")
                    st.markdown(f"**Payment:** {record['pay_status']}")
                    if record['pay_status'] == 'Pay Later':
                        st.info("Your room is held for 24 hours. Complete payment at check‑in or via our desk to secure beyond the hold.")
                st.toast("Saved to reservations.")
            except Exception as e:
                st.error(f"Could not save booking: {e}")

with find_tab:
    st.subheader("Look up your reservation")
    email_q = st.text_input("Email used in booking")
    ref_q = st.text_input("Reference (optional)")
    if st.button("Find", type="primary"):
        if not valid_email(email_q):
            st.error("Enter a valid email.")
        else:
            res = find_booking(email_q.strip().lower(), ref_q.strip() or None)
            if not res:
                st.warning("No booking found for that email/reference.")
            else:
                with st.container(border=True):
                    st.markdown(f"**Reference:** {res['ref']}")
                    st.markdown(f"**Name:** {res['name']}")
                    st.markdown(f"**Package:** {res['package']}")
                    st.markdown(f"**Dates:** {res['check_in']} → {res['check_out']}  ({res['nights']} night(s))")
                    st.markdown(f"**Guests:** {res['guests']}")
                    st.markdown(f"**Total:** ₹{res['total']:,}")
                    st.markdown(f"**Payment:** {res['pay_status']}")
                    if res.get('addons'):
                        st.markdown(f"**Add‑ons:** {res['addons']}")
                    if res.get('notes'):
                        st.markdown(f"**Notes:** {res['notes']}")

with admin_tab:
    st.subheader("Admin: Reservations")
    admin_pass = st.text_input("Password", type="password")
    if st.button("Load Reservations"):
        if admin_pass != "admin123":
            st.error("Wrong password.")
        else:
            with get_conn() as con:
                try:
                    df = pd.read_sql("SELECT * FROM bookings ORDER BY id DESC", con)
                except Exception:
                    df = pd.DataFrame()
            if df.empty:
                st.info("No reservations yet.")
            else:
                st.dataframe(df, use_container_width=True)
                csv = df.to_csv(index=False).encode()
                st.download_button("Download CSV", csv, file_name="amber_palace_bookings.csv", mime="text/csv")

# Footer
st.markdown("---")
st.caption("© Amber Palace, Ayodhya · Demo booking portal built with Streamlit. Pay‑Later holds are illustrative; connect your preferred payment gateway for real payments.")
