import streamlit as st
import json
import os
import time
import google.generativeai as genai
from google.api_core import exceptions as gexc
from PIL import Image

# ---------------------------------------------------------
# KONFIGURASI
# ---------------------------------------------------------
MASTER_FILE = "master_data.json"
# Urutan model: dicoba dari atas. Kalau timeout / kuota habis / model tidak ditemukan,
# otomatis lanjut ke model berikutnya. Cek nama yang valid dengan genai.list_models().
MODEL_LIST = [
    "gemini-3.8-flash-lite",   # lebih cepat, dicoba dulu
    "gemini-3.8-flash",        # cadangan kalau lite gagal / tidak ditemukan
]
REQUEST_TIMEOUT = 90              # detik per model (jangan terlalu kecil, nanti proses yang lambat-tapi-jalan ikut gagal)
INTEGER_ITEMS = ["terong", "timun", "jeruk"]

DEFAULT_MASTER = [
    {"name": "Terong", "type": "integer"},
    {"name": "Timun", "type": "integer"},
    {"name": "Jeruk", "type": "integer"},
    {"name": "Beras", "type": "radio"},
    {"name": "Minyak Goreng", "type": "radio"},
    {"name": "Gula Pasir", "type": "radio"},
    {"name": "Telur Ayam", "type": "radio"},
    {"name": "Handglove", "type": "radio"},
]

SCAN_PROMPT = (
    "Analisis gambar-gambar yang dilampirkan ini. "
    "Pertama, validasi apakah dokumen ini adalah Surat Jalan pengiriman barang/restoran yang sah. "
    "Jika gambar ini BUKAN surat jalan (misalnya foto selfie, pemandangan, atau gambar acak), "
    "berikan respons persis teks ini: INVALID_SURAT_JALAN. "
    "Jika valid, ekstrak seluruh daftar nama barang/bahan baku beserta kuantitasnya "
    "(sebagai string apa adanya dari kertas, contoh: '2 dus', '5 kg', '10 pcs'). "
    "Keluarkan hasil DALAM FORMAT JSON MURNI berupa list of dictionary dengan keys 'name' dan 'qty'. "
    'Contoh format: [{"name": "Beras", "qty": "5 karung"}]'
)


# ---------------------------------------------------------
# MASTER DATA (JSON)
# ---------------------------------------------------------
def save_master_data(data):
    with open(MASTER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def load_master_data():
    if not os.path.exists(MASTER_FILE):
        save_master_data(DEFAULT_MASTER)
    try:
        with open(MASTER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return list(DEFAULT_MASTER)


def tipe_untuk(nama):
    return "integer" if nama.strip().lower() in INTEGER_ITEMS else "radio"


if "master_data" not in st.session_state:
    st.session_state.master_data = load_master_data()


# ---------------------------------------------------------
# FUNGSI AI
# ---------------------------------------------------------
def resize_image(img, max_side=1024):
    img = img.convert("RGB")
    img.thumbnail((max_side, max_side))
    return img


FALLBACK_ERRORS = (
    gexc.ResourceExhausted,    # 429: kuota habis
    gexc.DeadlineExceeded,     # timeout
    gexc.ServiceUnavailable,   # 503: server sibuk
    gexc.InternalServerError,  # 500
    gexc.NotFound,             # 404: nama model tidak valid
)


def scan_surat_jalan(api_key, pil_images):
    """Coba tiap model di MODEL_LIST sampai ada yang berhasil.
    Return (teks_hasil, nama_model_yang_dipakai)."""
    genai.configure(api_key=api_key, transport="rest")
    last_error = None

    for model_name in MODEL_LIST:
        try:
            model = genai.GenerativeModel(
                model_name,
                generation_config={
                    "response_mime_type": "application/json",
                    "temperature": 0,
                    "max_output_tokens": 2048,
                },
            )
            resp = model.generate_content(
                pil_images + [SCAN_PROMPT],
                request_options={"timeout": REQUEST_TIMEOUT},
            )
            return (resp.text or "").strip(), model_name
        except FALLBACK_ERRORS as e:
            last_error = e
            continue

    # Semua model gagal: lempar error terakhir supaya ditangani pemanggil
    raise last_error


def cari_di_master(name):
    """Cocokkan nama dari surat jalan ke master data. Exact dulu, baru partial."""
    n = name.strip().lower()
    if not n:
        return None
    for m in st.session_state.master_data:
        if m["name"].lower() == n:
            return m
    for m in st.session_state.master_data:
        mn = m["name"].lower()
        if mn in n or n in mn:
            return m
    return None


# ---------------------------------------------------------
# KONFIGURASI HALAMAN
# ---------------------------------------------------------
st.set_page_config(page_title="Sistem Surat Jalan Restoran", page_icon="📦", layout="centered")
st.title("📦 Sistem Digitalisasi Surat Jalan Restoran")

menu = st.sidebar.selectbox("Menu Navigasi", ["Pengecekan Surat Jalan", "Kelola Master Data"])

# ---------------------------------------------------------
# MENU 1: KELOLA MASTER DATA
# ---------------------------------------------------------
if menu == "Kelola Master Data":
    st.header("⚙️ Kelola Master Data Bahan Baku")
    st.info("Bahan baku 'Terong', 'Timun', dan 'Jeruk' otomatis dikunci berjenis Integer.")

    with st.form("add_master_form"):
        st.subheader("Tambah Bahan Baku Baru")
        new_name = st.text_input("Nama Bahan Baku").strip()

        if tipe_untuk(new_name) == "integer":
            st.write("Tipe Input: **Integer** (Bahan khusus)")
        else:
            st.write("Tipe Input: **Radio Button (Lengkap / Tidak Ada)**")

        submitted = st.form_submit_button("Simpan ke Master Data")
        if submitted:
            if not new_name:
                st.error("Nama bahan baku tidak boleh kosong!")
            else:
                existing = [i["name"].lower() for i in st.session_state.master_data]
                if new_name.lower() in existing:
                    st.error(f"Gagal! Bahan baku '{new_name}' sudah ada di Master Data.")
                else:
                    st.session_state.master_data.append(
                        {"name": new_name, "type": tipe_untuk(new_name)}
                    )
                    save_master_data(st.session_state.master_data)
                    st.success(f"Berhasil menambahkan '{new_name}'!")
                    st.rerun()

    st.divider()
    st.subheader("Daftar Bahan Baku Saat Ini")

    for idx, item in enumerate(st.session_state.master_data):
        cols = st.columns([3, 2, 1])
        cols[0].write(f"**{idx + 1}. {item['name']}**")
        cols[1].write(f"Tipe: `{item['type']}`")
        if cols[2].button("Hapus", key=f"del_{idx}"):
            removed = st.session_state.master_data.pop(idx)
            save_master_data(st.session_state.master_data)
            st.success(f"Berhasil menghapus {removed['name']}")
            st.rerun()

# ---------------------------------------------------------
# MENU 2: PENGECEKAN SURAT JALAN
# ---------------------------------------------------------
elif menu == "Pengecekan Surat Jalan":
    st.header("📄 Scan & Validasi Surat Jalan")

    api_key = ""
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass

    if not api_key:
        api_key = st.text_input("🔑 Masukkan Google Gemini API Key Anda:", type="password")
        if not api_key:
            st.warning("⚠️ Masukkan API Key terlebih dahulu untuk mengaktifkan fitur scan AI Vision.")
            st.stop()

    uploaded_files = st.file_uploader(
        "Upload foto surat jalan (bisa lebih dari satu halaman)",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
    )

    if uploaded_files:
        if st.button("🔍 Proses & Scan Surat Jalan", type="primary"):
            with st.spinner("AI sedang membaca dan memvalidasi dokumen surat jalan..."):
                try:
                    t0 = time.time()
                    pil_images = [resize_image(Image.open(f)) for f in uploaded_files]
                    t_resize = time.time() - t0
                    raw_text, model_dipakai = scan_surat_jalan(api_key, pil_images)
                    t_total = time.time() - t0

                    if not raw_text or "INVALID_SURAT_JALAN" in raw_text:
                        st.error(
                            "❌ Dokumen ditolak! Foto yang di-upload bukan Surat Jalan yang valid. "
                            "Silakan upload ulang foto surat jalan yang benar."
                        )
                        st.session_state.pop("scanned_items", None)
                        st.stop()

                    # Jaga-jaga kalau model tetap membungkus dengan ```json
                    if "```" in raw_text:
                        raw_text = raw_text.split("```")[1]
                        if raw_text.startswith("json"):
                            raw_text = raw_text[4:]
                        raw_text = raw_text.strip()

                    scanned_items = json.loads(raw_text)
                    if not isinstance(scanned_items, list):
                        raise ValueError("Format hasil AI bukan list.")

                    st.session_state.scanned_items = scanned_items
                    st.success("✅ Surat jalan berhasil divalidasi dan diproses!")
                    st.caption(
                        f"Model: {model_dipakai} | Resize: {t_resize:.1f} dtk | Total: {t_total:.1f} dtk"
                    )

                except gexc.ResourceExhausted:
                    st.error("⏳ Kuota semua model habis. Tunggu 1 menit lalu coba lagi (atau besok kalau kuota harian).")
                    st.stop()
                except gexc.DeadlineExceeded:
                    st.error(f"⏱️ Semua model kelamaan merespons (lebih dari {REQUEST_TIMEOUT} detik per model). Coba lagi atau pakai foto yang lebih kecil.")
                    st.stop()
                except gexc.NotFound:
                    st.error("Nama model di MODEL_LIST tidak valid. Cek daftar model yang tersedia dengan genai.list_models().")
                    st.stop()
                except (gexc.ServiceUnavailable, gexc.InternalServerError):
                    st.error("Server Gemini sedang sibuk. Coba lagi beberapa saat.")
                    st.stop()
                except json.JSONDecodeError:
                    st.error("Hasil AI tidak bisa dibaca sebagai JSON. Coba scan ulang.")
                    st.stop()
                except Exception as e:
                    st.error(f"Terjadi kesalahan saat memproses AI Vision: {e}")
                    st.stop()

    # -----------------------------------------------------
    # HASIL SCAN & FORM PENGECEKAN
    # -----------------------------------------------------
    if st.session_state.get("scanned_items"):
        st.divider()
        st.subheader("📝 Hasil Ekstrak & Pengecekan Barang")

        unknown_items = []
        valid_items_to_check = []
        sudah_masuk = set()

        for scanned in st.session_state.scanned_items:
            if not isinstance(scanned, dict):
                continue
            name = (scanned.get("name") or "").strip()
            qty = scanned.get("qty", "-")
            if not name:
                continue

            matched = cari_di_master(name)
            if matched:
                if matched["name"].lower() in sudah_masuk:
                    continue
                sudah_masuk.add(matched["name"].lower())
                valid_items_to_check.append(
                    {"name": matched["name"], "qty": qty, "type": matched["type"]}
                )
            else:
                unknown_items.append({"name": name, "qty": qty})

        if unknown_items:
            st.warning("⚠️ Ditemukan bahan baku dari surat jalan yang **belum terdaftar** di Master Data:")

            with st.form("approval_form"):
                approved_new_items = []
                for idx, unk in enumerate(unknown_items):
                    col_a, col_b = st.columns([3, 1])
                    col_a.markdown(f"• **{unk['name']}** (Kuantitas: {unk['qty']})")
                    if col_b.checkbox("Tambahkan ke Master", value=True, key=f"app_{idx}"):
                        approved_new_items.append(unk["name"])

                if st.form_submit_button("Proses & Simpan Bahan Baru"):
                    existing = {i["name"].lower() for i in st.session_state.master_data}
                    for new_name in approved_new_items:
                        if new_name.lower() in existing:
                            continue
                        existing.add(new_name.lower())
                        st.session_state.master_data.append(
                            {"name": new_name, "type": tipe_untuk(new_name)}
                        )
                    save_master_data(st.session_state.master_data)
                    st.success("Bahan baku baru berhasil disimpan permanen ke Master Data!")
                    st.rerun()

        st.divider()
        st.markdown("### Form Pengecekan Fisik Harian")

        form_data = {}

        for i, item in enumerate(valid_items_to_check, 1):
            name = item["name"]
            qty_string = item["qty"]
            item_type = item["type"]

            cols = st.columns([2, 2, 3])
            cols[0].markdown(f"**{i}. {name}**")
            cols[1].markdown(f"*(SJ: {qty_string})*")

            if item_type == "integer" or name.lower() in INTEGER_ITEMS:
                val_int = cols[2].number_input(
                    f"Jumlah Fisik {name}",
                    min_value=0,
                    step=1,
                    key=f"int_{i}",
                    label_visibility="collapsed",
                )
                form_data[name] = {"value": val_int, "is_checked": val_int > 0}
            else:
                radio_choice = cols[2].radio(
                    f"Status {name}",
                    options=["Pilih Status...", "Lengkap", "Tidak Ada"],
                    index=0,
                    key=f"rad_{i}",
                    label_visibility="collapsed",
                )
                form_data[name] = {
                    "value": radio_choice,
                    "is_checked": radio_choice == "Lengkap",
                }

        st.divider()

        notes = st.text_area(
            "Catatan / Notes Tambahan (Opsional)",
            placeholder="Tulis catatan jika ada kendala pengiriman...",
        )

        if st.button("🖨️ Cetak / Simpan Laporan PDF", type="primary"):
            belum_dipilih = [n for n, d in form_data.items() if d["value"] == "Pilih Status..."]

            if belum_dipilih:
                st.error(
                    "🚨 Gagal Cetak! Masih ada bahan baku yang **belum dipilih** statusnya: "
                    + ", ".join(belum_dipilih)
                )
            else:
                st.success("✨ Laporan pengecekan berhasil divalidasi! Siap untuk dicetak ke PDF.")
                st.json({"items": form_data, "catatan": notes})
