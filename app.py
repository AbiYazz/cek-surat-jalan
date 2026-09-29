import streamlit as st
import json
import os
import google.generativeai as genai
from PIL import Image

# ---------------------------------------------------------
# KONFIGURASI FILE MASTER DATA (JSON)
# ---------------------------------------------------------
MASTER_FILE = "master_data.json"

DEFAULT_MASTER = [
    {"name": "Terong", "type": "integer"},
    {"name": "Timun", "type": "integer"},
    {"name": "Jeruk", "type": "integer"},
    {"name": "Beras", "type": "radio"},
    {"name": "Minyak Goreng", "type": "radio"},
    {"name": "Gula Pasir", "type": "radio"},
    {"name": "Telur Ayam", "type": "radio"},
    {"name": "Handglove", "type": "radio"}
]

def load_master_data():
    if not os.path.exists(MASTER_FILE):
        save_master_data(DEFAULT_MASTER)
    try:
        with open(MASTER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return DEFAULT_MASTER

def save_master_data(data):
    with open(MASTER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

if "master_data" not in st.session_state:
    st.session_state.master_data = load_master_data()

# ---------------------------------------------------------
# KONFIGURASI HALAMAN STREAMLIT
# ---------------------------------------------------------
st.set_page_config(page_title="Sistem Surat Jalan Restoran", page_icon="📦", layout="centered")

st.title("📦 Sistem Digitalisasi Surat Jalan Restoran")

menu = st.sidebar.selectbox("Menu Navigasi", ["Pengecekan Surat Jalan", "Kelola Master Data"])

# ---------------------------------------------------------
# TAB 1: KELOLA MASTER DATA (CRUD)
# ---------------------------------------------------------
if menu == "Kelola Master Data":
    st.header("⚙️ Kelola Master Data Bahan Baku")
    st.info("Bahan baku 'Terong', 'Timun', dan 'Jeruk' otomatis dikunci berjenis Integer.")

    with st.form("add_master_form"):
        st.subheader("Tambah Bahan Baku Baru")
        new_name = st.text_input("Nama Bahan Baku").strip()
        
        if new_name.lower() in ["terong", "timun", "jeruk"]:
            auto_type = "integer"
            st.write("Tipe Input: **Integer** (Bahan khusus)")
        else:
            auto_type = "radio"
            st.write("Tipe Input: **Radio Button (Lengkap / Tidak Ada)**")
            
        submitted = st.form_submit_button("Simpan ke Master Data")
        if submitted:
            if not new_name:
                st.error("Nama bahan baku tidak boleh kosong!")
            else:
                existing_names = [item["name"].lower() for item in st.session_state.master_data]
                if new_name.lower() in existing_names:
                    st.error(f"Gagal! Bahan baku '{new_name}' sudah ada di Master Data.")
                else:
                    st.session_state.master_data.append({"name": new_name, "type": auto_type})
                    save_master_data(st.session_state.master_data)
                    st.success(f"Berhasil menambahkan '{new_name}'!")
                    st.rerun()

    st.divider()
    st.subheader("Daftar Bahan Baku Saat Ini")
    
    for idx, item in enumerate(st.session_state.master_data):
        cols = st.columns([3, 2, 1])
        cols[0].write(f"**{idx+1}. {item['name']}**")
        cols[1].write(f"Tipe: `{item['type']}`")
        if cols[2].button("Hapus", key=f"del_{idx}"):
            removed = st.session_state.master_data.pop(idx)
            save_master_data(st.session_state.master_data)
            st.success(f"Berhasil menghapus {removed['name']}")
            st.rerun()

# ---------------------------------------------------------
# TAB 2: PENGECEKAN SURAT JALAN (AI VISION + MULTI-UPLOAD)
# ---------------------------------------------------------
elif menu == "Pengecekan Surat Jalan":
    st.header("📄 Scan & Validasi Surat Jalan")
    
    # Ambil API Key dari Streamlit Secrets secara otomatis
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
    except:
        api_key = ""
    
    if not api_key:
        st.error("❌ GEMINI_API_KEY belum diatur di Streamlit Secrets! Harap masukkan API key di bagian Settings -> Secrets aplikasi Streamlit Cloud Anda.")
        st.stop()

    uploaded_files = st.file_uploader(
        "Upload foto surat jalan (bisa lebih dari satu halaman)", 
        type=["jpg", "jpeg", "png"], 
        accept_multiple_files=True
    )

    if uploaded_files:
        genai.configure(api_key=api_key)
        
        # Tombol aksi scan
        if st.button("🔍 Proses & Scan Surat Jalan", type="primary"):
            with st.spinner("AI sedang membaca dan memvalidasi dokumen surat jalan..."):
                try:
                    pil_images = [Image.open(f) for f in uploaded_files]
                    
                    prompt = (
                        "Analisis gambar-gambar yang dilampirkan ini. "
                        "Pertama, validasi apakah dokumen ini adalah Surat Jalan pengiriman barang/restoran yang sah. "
                        "Jika gambar ini BUKAN surat jalan (misalnya foto selfie, pemandangan, atau gambar acak), "
                        "berikan respons persis teks ini: INVALID_SURAT_JALAN. "
                        "Jika valid, ekstrak seluruh daftar nama barang/bahan baku beserta kuantitasnya (sebagai string apa adanya dari kertas, contoh: '2 dus', '5 kg', '10 pcs'). "
                        "Keluarkan hasil DALAM FORMAT JSON MURNI berupa list of dictionary dengan keys 'name' dan 'qty'. Contoh format: "
                        '[{"name": "Beras", "qty": "5 karung"}]'
                    )
                    
                    model = genai.GenerativeModel('gemini-2.5-flash')
                    content_payload = pil_images + [prompt]
                    response = model.generate_content(content_payload)
                    raw_text = response.text.strip()
                    
                    if "INVALID_SURAT_JALAN" in raw_text or not raw_text:
                        st.error("❌ Dokumen ditolak! Foto yang di-upload bukan merupakan Surat Jalan yang valid. Silakan upload ulang foto surat jalan yang benar.")
                        # Hapus session state sebelumnya jika ada
                        if "scanned_items" in st.session_state:
                            del st.session_state.scanned_items
                        st.stop()
                    
                    # Bersihkan markdown json jika terbawa
                    if "```json" in raw_text:
                        raw_text = raw_text.split("```json")[1].split("```")[0].strip()
                    elif "```" in raw_text:
                        raw_text = raw_text.split("```")[1].split("```")[0].strip()
                        
                    scanned_items = json.loads(raw_text)
                    st.session_state.scanned_items = scanned_items
                    st.success("✅ Surat jalan berhasil divalidasi dan diproses!")
                    
                except Exception as e:
                    st.error(f"Terjadi kesalahan saat memproses AI Vision: {e}")
                    st.stop()

    # Tampilkan form jika hasil scan sudah tersimpan di session
    if "scanned_items" in st.session_state and st.session_state.scanned_items:
        st.divider()
        st.subheader("📝 Hasil Ekstrak & Pengecekan Barang")
        
        unknown_items = []
        valid_items_to_check = []
        
        for scanned in st.session_state.scanned_items:
            name = scanned.get("name")
            qty = scanned.get("qty", "-")
            matched = None
            for m in st.session_state.master_data:
                if m["name"].lower() in name.lower() or name.lower() in m["name"].lower():
                    matched = m
                    break
            
            if matched:
                valid_items_to_check.append({"name": matched["name"], "qty": qty, "type": matched["type"]})
            else:
                unknown_items.append({"name": name, "qty": qty})
                
        if unknown_items:
            st.warning("⚠️ Ditemukan bahan baku dari surat jalan yang **belum terdaftar** di Master Data:")
            
            with st.form("approval_form"):
                approved_new_items = []
                for idx, unk in enumerate(unknown_items):
                    col_a, col_b = st.columns([3, 1])
                    col_a.markdown(f"• **{unk['name']}** (Kuantitas: {unk['qty']})")
                    is_approved = col_b.checkbox("Tambahkan ke Master", value=True, key=f"app_{idx}")
                    if is_approved:
                        approved_new_items.append(unk['name'])
                
                submit_approval = st.form_submit_button("Proses & Simpan Bahan Baku Baru")
                if submit_approval:
                    for new_item_name in approved_new_items:
                        t = "integer" if new_item_name.lower() in ["terong", "timun", "jeruk"] else "radio"
                        st.session_state.master_data.append({"name": new_item_name, "type": t})
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
            
            if item_type == "integer" or name.lower() in ["terong", "timun", "jeruk"]:
                val_int = cols[2].number_input(
                    f"Jumlah Fisik {name}", 
                    min_value=0, 
                    step=1, 
                    key=f"int_{i}",
                    label_visibility="collapsed"
                )
                form_data[name] = {"value": val_int, "is_checked": val_int > 0}
            else:
                radio_choice = cols[2].radio(
                    f"Status {name}",
                    options=["Pilih Status...", "Lengkap", "Tidak Ada"],
                    index=0,
                    key=f"rad_{i}",
                    label_visibility="collapsed"
                )
                form_data[name] = {
                    "value": radio_choice, 
                    "is_checked": (radio_choice == "Lengkap")
                }

        st.divider()
        
        notes = st.text_area("Catatan / Notes Tambahan (Opsional)", placeholder="Tulis catatan jika ada kendala pengiriman...")

        if st.button("🖨️ Cetak / Simpan Laporan PDF", type="primary"):
            error_found = False
            for name, data in form_data.items():
                if data["value"] == "Pilih Status...":
                    error_found = True
                    break

            if error_found:
                st.error("🚨 Gagal Cetak! Masih ada bahan baku berstatus Radio Button yang **belum dipilih** (Lengkap / Tidak Ada). Harap lengkapi semua pilihan di atas!")
            else:
                st.success("✨ Laporan pengecekan berhasil divalidasi! Siap untuk dicetak ke PDF.")
                st.json(form_data)
