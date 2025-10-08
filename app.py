import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Τιμολόγηση Αντλιών", page_icon="💧", layout="centered")
st.title("💧 App Τιμολόγησης Αντλιών (τιμές με ΦΠΑ)")

st.markdown(
    "Ανέβασε το **Excel** με τις αντλίες. Αν οι επικεφαλίδες δεν εντοπιστούν αυτόματα, "
    "διάλεξε **φύλλο** και **γραμμή επικεφαλίδων** από την προεπισκόπηση."
)

# -----------------------------
# Βοηθοί
# -----------------------------
CANDIDATES = {
    "brand": ["Μάρκα", "Μαρκα", "Brand"],
    "erp": ["Κωδικός ERP", "Κωδ. ERP", "ERP"],
    "model": ["Μοντέλο", "Model", "Μοντελο"],
    "power": ["Ισχύς", "kW", "ΙΣΧΥΣ"],
    "retail_cash": ["Ιδιώτης Μετρητοίς", "Λιανική Μετρητοίς", "Retail"],
    "pro_program": ["Υδραυλικοί - Μηχανικοί Προγράμματα", "Επαγγελματίες Προγράμματα", "Program"],
    "comm_invoice": ["Προμήθεια με παροχής με ΦΠΑ", "Προμήθεια παροχής (με ΦΠΑ)"],
    "comm_hand": ["Προμήθεια χέρι", "Προμήθεια στο χέρι"],
}

REQUIRED_KEYS = ["erp", "model", "retail_cash", "pro_program"]


def suggest_match(cols, candidates):
    low = {str(c).strip().lower(): c for c in cols}
    # exact
    for cand in candidates:
        k = cand.lower().strip()
        if k in low:
            return low[k]
    # contains
    for c in cols:
        for cand in candidates:
            if cand.lower().strip() in str(c).lower():
                return c
    return None

# -----------------------------
# 1) Ανέβασμα Excel & επιλογή φύλλου/κεφαλίδων
# -----------------------------
uploaded = st.file_uploader("📄 Ανέβασε Excel (.xlsx)", type=["xlsx"])
if not uploaded:
    st.info("Ανέβασε το αρχείο σου (π.χ. «Τιμοκαταλογος αντλίες Clean.xlsx»).")
    st.stop()

xls = pd.ExcelFile(uploaded)
sheet = st.selectbox("Φύλλο εργασίας", xls.sheet_names)
raw = pd.read_excel(xls, sheet_name=sheet, header=None)

st.markdown("**Προεπισκόπηση (πρώτες 20 σειρές, χωρίς κεφαλίδες):**")
st.dataframe(raw.head(20), use_container_width=True)

header_row_display = st.number_input(
    "Διάλεξε γραμμή επικεφαλίδων (1 = πρώτη γραμμή του φύλλου)", min_value=1, max_value=len(raw), value=1, step=1
)
header_idx = int(header_row_display - 1)

try:
    df = pd.read_excel(xls, sheet_name=sheet, header=header_idx)
except Exception as e:
    st.error("Πρόβλημα ανάγνωσης με την επιλεγμένη γραμμή επικεφαλίδων.")
    st.stop()

# Καθάρισε άδειες στήλες/γραμμές
df = df.dropna(how="all", axis=1).dropna(how="all", axis=0)

st.markdown("**Επικεφαλίδες που θα χρησιμοποιηθούν:**")
st.write(list(df.columns))

# -----------------------------
# 2) Χαρτογράφηση στηλών (αν δεν ταιριάζουν τα ονόματα)
# -----------------------------
col_options = [c for c in df.columns]
colmaps = {}

cols_left, cols_right = st.columns(2)
with cols_left:
    for key in ["erp", "model", "retail_cash", "pro_program"]:
        default = suggest_match(col_options, CANDIDATES[key])
        colmaps[key] = st.selectbox(f"Στήλη για **{key}**", options=[None]+col_options, index=(col_options.index(default)+1) if default in col_options else 0)
with cols_right:
    for key in ["brand", "power", "comm_invoice", "comm_hand"]:
        default = suggest_match(col_options, CANDIDATES[key])
        colmaps[key] = st.selectbox(f"Στήλη για {key}", options=[None]+col_options, index=(col_options.index(default)+1) if default in col_options else 0)

missing = [k for k in REQUIRED_KEYS if not colmaps.get(k)]
if missing:
    st.error("Λείπουν βασικές αντιστοιχίσεις στηλών: " + ", ".join(missing))
    st.stop()

# Μετατροπές τύπων
for k in ["retail_cash", "pro_program", "comm_invoice", "comm_hand"]:
    col = colmaps.get(k)
    if col:
        df[col] = pd.to_numeric(df[col], errors="coerce")

df = df[df[colmaps["model"]].notna()].copy()

# -----------------------------
# 3) Επιλογές χρήστη
# -----------------------------
colA, colB = st.columns(2)
with colA:
    customer_type = st.selectbox("Τύπος Πελάτη", ["Ιδιώτης", "Επαγγελματίας – Υδραυλικός", "Επαγγελματίας – Μηχανικός"])
    payment_method = st.selectbox("Τρόπος Πληρωμής", ["Μέσω Προγράμματος", "Μετρητοίς"])
with colB:
    def labelize(r):
        brand = str(r.get(colmaps.get("brand",""), "")) if colmaps.get("brand") else ""
        pwr = str(r.get(colmaps.get("power",""), "")) if colmaps.get("power") else ""
        erp = str(r.get(colmaps.get("erp",""), "")) if colmaps.get("erp") else ""
        model = str(r[colmaps["model"]])
        return f"{model} | {pwr} | ERP: {erp}" if erp else f"{model} | {pwr}"

    options = df.apply(labelize, axis=1).tolist()
    choice = st.selectbox("Μοντέλο Αντλίας", options)
    sel_idx = options.index(choice)
    row = df.iloc[sel_idx]

billing_route = None
payout_mode = None
if customer_type.startswith("Επαγγελματίας"):
    billing_route = st.radio("Τιμολόγηση για επαγγελματία", ["Τιμολόγηση στον επαγγελματία", "Τιμολόγηση στον τελικό πελάτη"], horizontal=True)
    if billing_route == "Τιμολόγηση στον τελικό πελάτη":
        payout_mode = st.radio("Απόδοση προμήθειας επαγγελματία", ["Παροχής υπηρεσιών (τιμολόγιο από επαγγελματία)", "Κράτηση ΦΠΑ & φόρου + προμήθεια στο χέρι"]) 

# -----------------------------
# 4) Υπολογισμοί (τιμές με ΦΠΑ όπως στο αρχείο)
# -----------------------------
retail_cash = float(row[colmaps["retail_cash"]]) if pd.notna(row[colmaps["retail_cash"]]) else None
pro_program = float(row[colmaps["pro_program"]]) if pd.notna(row[colmaps["pro_program"]]) else None
comm_invoice = float(row[colmaps["comm_invoice"]]) if colmaps.get("comm_invoice") and pd.notna(row[colmaps["comm_invoice"]]) else None
comm_hand = float(row[colmaps["comm_hand"]]) if colmaps.get("comm_hand") and pd.notna(row[colmaps["comm_hand"]]) else None

scenario = {}
if customer_type == "Ιδιώτης":
    base = retail_cash if payment_method == "Μετρητοίς" else (pro_program if pro_program else retail_cash)
    scenario = {"Σενάριο": "Ιδιώτης", "Ποσό τιμολόγησης (με ΦΠΑ)": round(base,2) if base is not None else None}
else:
    if billing_route == "Τιμολόγηση στον επαγγελματία":
        scenario = {"Σενάριο": "Επαγγελματίας → Τιμολόγηση στον επαγγελματία", "Ποσό τιμολόγησης (με ΦΠΑ)": round(pro_program,2) if pro_program is not None else None}
    else:
        invoice_to_end = retail_cash
        if payout_mode == "Παροχής υπηρεσιών (τιμολόγιο από επαγγελματία)":
            payout = comm_invoice
            note = "Ο επαγγελματίας εκδίδει παραστατικό (ποσό προμήθειας με ΦΠΑ)."
        else:
            payout = comm_hand
            note = "Κράτηση φόρου & ΦΠΑ σύμφωνα με πολιτική. Απόδοση καθαρού ποσού."
        scenario = {
            "Σενάριο": "Επαγγελματίας → Τιμολόγηση στον τελικό πελάτη",
            "Ποσό τιμολόγησης πελάτη (με ΦΠΑ)": round(invoice_to_end,2) if invoice_to_end is not None else None,
            "Προμήθεια επαγγελματία": round(payout,2) if payout is not None else "—",
            "Σημείωση": note,
        }

# -----------------------------
# 5) Εμφάνιση
# -----------------------------
meta = {
    "Μάρκα": row.get(colmaps.get("brand",""), ""),
    "ERP": row.get(colmaps.get("erp",""), ""),
    "Μοντέλο": row.get(colmaps.get("model",""), ""),
    "Ισχύς": row.get(colmaps.get("power",""), ""),
}
st.subheader("🧾 Επιλεγμένο προϊόν")
st.write(meta)

st.subheader("Αποτελέσματα")
st.json(scenario, expanded=True)

st.markdown("---")
st.caption("Διάλεξε σωστά τη γραμμή επικεφαλίδων και κάνε map τις στήλες αν χρειάζεται. Όλες οι τιμές θεωρούνται με ΦΠΑ (όπως στο αρχείο).")
