import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Τιμολόγηση Αντλιών", page_icon="💧", layout="centered")
st.title("💧 App Τιμολόγησης Αντλιών (τιμές με ΦΠΑ)")

st.markdown(
    "Ανέβασε το **Excel** με τις αντλίες. Το app θα εντοπίσει αυτόματα τη γραμμή επικεφαλίδων "
    "και θα χρησιμοποιήσει τα πεδία για ιδιώτη, επαγγελματία και προμήθειες."
)

# -----------------------------
# Βοηθοί
# -----------------------------
GREEK_REQUIRED = {
    "brand": ["Μάρκα", "Μαρκα", "Μάρκα "],
    "erp": ["Κωδικός ERP", "Κωδ. ERP", "ERP", "Κωδικός  ERP"],
    "model": ["Μοντέλο", "Model", "Μοντελο"],
    "power": ["Ισχύς", "Ισχυς", "kW", "ΙΣΧΥΣ"],
    # Τιμές με ΦΠΑ
    "retail_cash": ["Ιδιώτης Μετρητοίς", "Ιδιωτης Μετρητοις", "Λιανική Μετρητοίς"],
    "pro_program": ["Υδραυλικοί - Μηχανικοί Προγράμματα", "Επαγγελματίες Προγράμματα", "Τιμή Προγράμματος"],
    # Προμήθειες (με ΦΠΑ – ποσά, όχι %)
    "comm_invoice": ["Προμήθεια με παροχής με ΦΠΑ", "Προμήθεια παροχής (με ΦΠΑ)", "Προμήθεια τιμολόγιο"],
    "comm_hand": ["Προμήθεια χέρι", "Προμήθεια στο χέρι"],
}

def find_header_row(df: pd.DataFrame) -> int | None:
    """Προσπάθησε να βρεις τη γραμμή που περιέχει 'Μοντέλο' και 'Κωδικός ERP'."""
    for i in range(min(20, len(df))):
        row_vals = df.iloc[i].astype(str).str.strip().str.lower().tolist()
        if any("μοντέλο" in v or "μοντελο" in v or "model" in v for v in row_vals) and \
           any("erp" in v for v in row_vals):
            return i
    return None

def pick_col(cols, candidates):
    """Βρες ποια από τις candidate ονομασίες υπάρχει στα cols."""
    low = {c.lower().strip(): c for c in cols}
    for cand in candidates:
        key = cand.lower().strip()
        if key in low:
            return low[key]
    # δοκίμασε contains
    for c in cols:
        for cand in candidates:
            if cand.lower().strip() in str(c).lower().strip():
                return c
    return None

def normalize_columns(df):
    """Επέστρεψε map {canonical: actual_col_name}."""
    colmap = {}
    for canon, candidates in GREEK_REQUIRED.items():
        found = pick_col(df.columns, candidates)
        colmap[canon] = found
    return colmap

def get_best_sheet_name(xls: pd.ExcelFile) -> str:
    # προτεραιότητα σε πιθανές ονομασίες
    prefs = ["Αντλίες θερμότητας", "Aντλίες θερμοτητας", "Αντλιες θερμοτητας", "Aντλίες θερμοτητας (2)"]
    for p in prefs:
        if p in xls.sheet_names:
            return p
    # αλλιώς το πρώτο
    return xls.sheet_names[0]

# -----------------------------
# Φόρτωση Excel
# -----------------------------
uploaded = st.file_uploader("📄 Ανέβασε Excel (.xlsx)", type=["xlsx"])
if not uploaded:
    st.info("Μπορείς να ανεβάσεις το αρχείο **«Τιμοκαταλογος αντλίες Clean.xlsx»** που ανέβασες εδώ στο chat.")
    st.stop()

xls = pd.ExcelFile(uploaded)
sheet_name = get_best_sheet_name(xls)
raw = pd.read_excel(xls, sheet_name=sheet_name, header=None)
hdr_row = find_header_row(raw)

if hdr_row is None:
    st.error("Δεν βρήκα γραμμή επικεφαλίδων (π.χ. με 'Μοντέλο' και 'Κωδικός ERP'). Έλεγξε το φύλλο.")
    st.stop()

df = pd.read_excel(xls, sheet_name=sheet_name, header=hdr_row)
# καθάρισε κενές στήλες / γραμμές
df = df.dropna(how="all", axis=1).dropna(how="all", axis=0)

# Φτιάξε mapping στηλών
colmap = normalize_columns(df)

missing = [k for k, v in colmap.items() if v is None and k in ["erp","model","retail_cash","pro_program"]]
if missing:
    st.error("Λείπουν βασικές στήλες στο φύλλο: " + ", ".join(missing))
    st.stop()

# Φιλτράρουμε σε ενεργά rows (να έχουν Μοντέλο και τιμές)
df = df[df[colmap["model"]].notna()].copy()
df[colmap["retail_cash"]] = pd.to_numeric(df[colmap["retail_cash"]], errors="coerce")
df[colmap["pro_program"]] = pd.to_numeric(df[colmap["pro_program"]], errors="coerce")

# -----------------------------
# Επιλογές χρήστη
# -----------------------------
colA, colB = st.columns(2)
with colA:
    customer_type = st.selectbox("Τύπος Πελάτη", ["Ιδιώτης", "Επαγγελματίας – Υδραυλικός", "Επαγγελματίας – Μηχανικός"])
    payment_method = st.selectbox("Τρόπος Πληρωμής", ["Μέσω Προγράμματος", "Μετρητοίς"])

with colB:
    # εμφάνιση σαν "Μοντέλο – Ισχύς – ERP"
    def labelize(row):
        brand = str(row.get(colmap.get("brand",""), "")) if colmap.get("brand") else ""
        pwr = str(row.get(colmap.get("power",""), "")) if colmap.get("power") else ""
        return f"{row[colmap['model']]} | {pwr} | ERP: {row[colmap['erp']]}" if colmap["erp"] else f"{row[colmap['model']]} | {pwr}"

    options = df.apply(labelize, axis=1).tolist()
    choice = st.selectbox("Μοντέλο Αντλίας", options)
    sel_idx = options.index(choice)
    row = df.iloc[sel_idx]

# Αν ο πελάτης είναι επαγγελματίας, επίλεξε route
billing_route = None
payout_mode = None
if customer_type.startswith("Επαγγελματίας"):
    billing_route = st.radio(
        "Τιμολόγηση για επαγγελματία",
        ["Τιμολόγηση στον επαγγελματία", "Τιμολόγηση στον τελικό πελάτη"],
        horizontal=True
    )
    if billing_route == "Τιμολόγηση στον τελικό πελάτη":
        payout_mode = st.radio(
            "Απόδοση προμήθειας επαγγελματία",
            ["Παροχής υπηρεσιών (τιμολόγιο από επαγγελματία)", "Κράτηση ΦΠΑ & φόρου + προμήθεια στο χέρι"],
            horizontal=False
        )

# -----------------------------
# Υπολογισμοί (όλα με ΦΠΑ)
# -----------------------------
retail_cash = float(row[colmap["retail_cash"]]) if pd.notna(row[colmap["retail_cash"]]) else None
pro_program = float(row[colmap["pro_program"]]) if pd.notna(row[colmap["pro_program"]]) else None

# Παροχές/προμήθειες αν υπάρχουν (ποσά με ΦΠΑ)
comm_invoice = None
comm_hand = None
if colmap.get("comm_invoice") and colmap["comm_invoice"] in df.columns:
    val = row[colmap["comm_invoice"]]
    comm_invoice = float(val) if pd.notna(val) else None

if colmap.get("comm_hand") and colmap["comm_hand"] in df.columns:
    val = row[colmap["comm_hand"]]
    comm_hand = float(val) if pd.notna(val) else None

# Βασική τιμή χρέωσης ανά σενάριο
scenario = {}
if customer_type == "Ιδιώτης":
    # ο ιδιώτης πληρώνει λιανική μετρητοίς ή, αν ζητηθεί, μπορείς να θεωρήσεις ότι πρόγραμμα=pro_program
    base_price = retail_cash if payment_method == "Μετρητοίς" else (pro_program if pro_program else retail_cash)
    scenario = {
        "Σενάριο": "Ιδιώτης",
        "Ποσό τιμολόγησης (με ΦΠΑ)": round(base_price, 2) if base_price is not None else None,
        "Σημείωση": "Όλες οι τιμές περιλαμβάνουν ΦΠΑ."
    }
else:
    # Επαγγελματίας
    if billing_route == "Τιμολόγηση στον επαγγελματία":
        # Τον τιμολογείς εσύ – χρησιμοποίησε την τιμή προγράμματος (με ΦΠΑ όπως δίνεται στο αρχείο)
        scenario = {
            "Σενάριο": "Επαγγελματίας → Τιμολόγηση στον επαγγελματία",
            "Ποσό τιμολόγησης (με ΦΠΑ)": round(pro_program, 2) if pro_program is not None else None,
            "Σημείωση": "Τιμή προγράμματος (με ΦΠΑ)."
        }
    else:
        # Τιμολόγηση στον τελικό πελάτη: λιανική με ΦΠΑ
        invoice_to_end = retail_cash
        payout_note = ""
        payout_amount = None
        if payout_mode == "Παροχής υπηρεσιών (τιμολόγιο από επαγγελματία)":
            payout_amount = comm_invoice  # ήδη με ΦΠΑ
            payout_note = "Ο επαγγελματίας εκδίδει παραστατικό (ποσό προμήθειας με ΦΠΑ)."
        else:
            payout_amount = comm_hand  # καθαρό στο χέρι (όπως δίνεται)
            payout_note = "Κράτηση ΦΠΑ & φόρου κατά τα οριζόμενα, απόδοση καθαρού ποσού στο χέρι."

        scenario = {
            "Σενάριο": "Επαγγελματίας → Τιμολόγηση στον τελικό πελάτη",
            "Ποσό τιμολόγησης πελάτη (με ΦΠΑ)": round(invoice_to_end, 2) if invoice_to_end is not None else None,
            "Προμήθεια επαγγελματία": round(payout_amount, 2) if payout_amount is not None else "—",
            "Σημείωση": payout_note
        }

# -----------------------------
# Εμφάνιση
# -----------------------------
st.subheader("🧾 Αποτελέσματα")
meta = {
    "Μάρκα": row.get(colmap.get("brand",""), ""),
    "ERP": row.get(colmap.get("erp",""), ""),
    "Μοντέλο": row.get(colmap.get("model",""), ""),
    "Ισχύς": row.get(colmap.get("power",""), ""),
}
st.write(meta)
st.json(scenario, expanded=True)

st.markdown("---")
st.caption("Χρησιμοποιούνται οι στήλες: «Ιδιώτης Μετρητοίς», «Υδραυλικοί - Μηχανικοί Προγράμματα», «Προμήθεια με παροχής με ΦΠΑ», «Προμήθεια χέρι» (εφόσον υπάρχουν). Όλες οι τιμές θεωρούνται με ΦΠΑ, όπως μου επιβεβαίωσες.")
