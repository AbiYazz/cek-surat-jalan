import streamlit as st
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
import io

st.set_page_config(page_title="Sistem Pengecekan Surat Jalan", layout="wide")

st.title("📦 Sistem Pengecekan Barang & Surat Jalan Restoran")
st.write("Upload surat jalan untuk memulai pengecekan fisik oleh karyawan.")

# 1. Upload Foto dari Galeri / Kamera
uploaded_file = st.file_uploader("Upload Foto Surat Jalan (Gunakan foto yang dikirim sebelumnya untuk testing)", type=["jpg", "jpeg", "png"])

# Data tiruan (mock data) berdasarkan surat jalan yang kamu kirim (33 Item)
default_items = [
    "Ayam AD", "Ayam AP", "Beras", "Box TA Kecil", "Cabe Ijo", "Carbol", 
    "Ceker AC", "Ceker CM", "Cumi", "Cup Minuman", "Gula", "Jeruk", 
    "Kangkung", "Kertas Nasi", "Kertas Thermal", "KOL", "Kulit AK", 
    "Lele AL", "Mika telor", "Minyak", "Nila AN", "SABUN COLEK", 
    "Sayur Asem Kecil Pack", "Sedotan", "Selada", "Sunlight", "Tahu AT", 
    "Teh", "Tempe AT", "Terong", "Timun", "Tisue", "Wadah Sambal"
]

# Barang khusus input fisik murni
special_items = ["Terong", "Jeruk", "Timun"]

if uploaded_file is not None:
    st.image(uploaded_file, caption="Surat Jalan yang di-upload", use_container_width=True)
    st.success("Surat jalan berhasil di-scan oleh sistem! Silakan lakukan pengecekan fisik di bawah.")
    
    with st.form("form_pengecekan"):
        st.subheader("Form Pengecekan Karyawan Gudang")
        
        results = []
        
        for i, item in enumerate(default_items, 1):
            st.markdown(f"---")
            cols = st.columns([2, 2, 3])
            cols[0].write(**f"**{i}. {item}**")
            
            if item in special_items:
                # Input khusus angka fisik untuk Terong, Jeruk, Timun
                cols[1].write("*(Input Fisik Aktual)*")
                val_fisik = cols[2].number_input(f"Jumlah Fisik {item}", min_value=0.0, step=0.5, key=f"spec_{i}")
                results.append({
                    "No": i,
                    "Product Name": item,
                    "Status": "Input Fisik",
                    "Keterangan_Fisik": val_fisik
                })
            else:
                # Opsi standar untuk barang lainnya
                status = cols[1].radio(
                    "Status", 
                    ["Lengkap", "Tidak Ada", "Tidak Sesuai"], 
                    key=f"status_{i}",
                    label_visibility="collapsed"
                )
                
                val_fisik = 0.0
                if status == "Tidak Sesuai":
                    val_fisik = cols[2].number_input(f"Jumlah Aktual {item}", min_value=0.0, step=1.0, key=f"qty_{i}")
                
                results.append({
                    "No": i,
                    "Product Name": item,
                    "Status": status,
                    "Keterangan_Fisik": val_fisik
                })
                
        submitted = st.form_submit_button("Simpan & Generate PDF Laporan")
        
        if submitted:
            st.session_state['report_data'] = results
            st.success("Data berhasil direkam!")

# Jika data sudah disubmit, buat tombol download PDF
if 'report_data' in st.session_state:
    st.markdown("---")
    st.subheader("📄 Unduh Laporan PDF untuk Kasir")
    
    def generate_pdf(data):
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        elements = []
        
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'TitleStyle',
            parent=styles['Heading1'],
            fontSize=16,
            alignment=1, # Center
            spaceAfter=20
        )
        
        elements.append(Paragraph("<b>LAPORAN PENGECEKAN BARANG SURAT JALAN</b>", title_style))
        elements.append(Paragraph("Restoran Ayam Goreng Cabe Ijo Sawangan", styles['Normal']))
        elements.append(Spacer(1, 15))
        
        table_data = [["No", "Nama Produk", "Status / Keterangan Fisik"]]
        row_styles = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ]
        
        for idx, row in enumerate(data, start=1):
            status_text = row['Status']
            if row['Status'] == "Input Fisik":
                status_text = f"Fisik Aktual: {row['Keterangan_Fisik']}"
            elif row['Status'] == "Tidak Sesuai":
                status_text = f"Tidak Sesuai (Fisik: {row['Keterangan_Fisik']})"
                # Berikan warna latar belakang merah muda/kuning jika bermasalah (selisih / tidak ada)
                row_styles.append(('BACKGROUND', (0, idx), (-1, idx), colors.HexColor("#ffcccc")))
            elif row['Status'] == "Tidak Ada":
                status_text = "TIDAK ADA / KOSONG"
                row_styles.append(('BACKGROUND', (0, idx), (-1, idx), colors.HexColor("#ff9999")))
                
            table_data.append([str(row['No']), row['Product Name'], status_text])
            
        t = Table(table_data, colWidths=[30, 250, 270])
        t.setStyle(TableStyle(row_styles))
        elements.append(t)
        
        doc.build(elements)
        buffer.seek(0)
        return buffer

    pdf_file = generate_pdf(st.session_state['report_data'])
    
    st.download_button(
        label="📥 Download PDF Laporan Pengecekan",
        data=pdf_file,
        file_name="Laporan_Pengecekan_SuratJalan.pdf",
        mime="application/pdf"
                                 )
