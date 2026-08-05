import cv2
import numpy as np
import base64
import logging
import requests
from app.config import settings

logger = logging.getLogger(__name__)


def _call_llm_vision(prompt: str, img_base64: str, num_predict: int = 100) -> str:
    """Helper: panggil Ollama Vision dan kembalikan teks responsnya."""
    payload = {
        "model": settings.VISION_MODEL_NAME,
        "prompt": prompt,
        "images": [img_base64],
        "stream": False,
        "options": {"temperature": 0.0, "num_predict": num_predict}
    }
    try:
        response = requests.post(
            f"{settings.OLLAMA_BASE_URL}/api/generate",
            json=payload,
            timeout=settings.VISION_TIMEOUT
        )
        response.raise_for_status()
        text = response.json().get("response", "").strip()
        return text.replace("`", "").replace('"', "").strip()
    except Exception as e:
        logger.error(f"LLM Vision call failed: {e}")
        return ""


def _discover_column_headers(img: np.ndarray, header_y1: int, header_y2: int,
                              column_x_ranges: list) -> dict:
    """
    Untuk setiap rentang kolom X yang terdeteksi, potong area headernya dan
    panggil LLM untuk membaca nama jabatan/kolomnya secara bebas (tanpa daftar hardcoded).
    Mengembalikan {x_center: nama_kolom}.
    """
    columns_map = {}
    prompt = (
        "Ini adalah potongan gambar vertikal dari judul kolom tabel SOP. "
        "Dalam gambar ini, mungkin terdapat kata umum seperti 'Pelaksana' di bagian paling atas. ABAIKAN kata 'Pelaksana' tersebut. "
        "Tugas Anda adalah membaca nama jabatan/unit kerja spesifik yang tertulis DI BAWAH kata 'Pelaksana' "
        "(misalnya: Sekretaris, Kasubbag Umum, Pengelola Kepegawaian, Pegawai yang bersangkutan, dll). "
        "Jika teksnya buram, tebaklah nama jabatan yang paling masuk akal. "
        "Jawab HANYA dengan nama jabatan tersebut, tanpa penjelasan tambahan."
    )
    for x_center, x1, x2 in column_x_ranges:
        crop = img[header_y1:header_y2, x1:x2]
        if crop.size == 0 or (header_y2 - header_y1) < 30:
            continue
        crop_upscaled = cv2.resize(crop, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
        _, buf = cv2.imencode(".png", crop_upscaled)
        crop_b64 = base64.b64encode(buf).decode("utf-8")
        title = _call_llm_vision(prompt, crop_b64, num_predict=60)
        if title:
            columns_map[x_center] = title
            logger.info(f"Auto-Header OCR X={x_center}: '{title}'")
    return columns_map


def extract_pelaksana_mapping(img_base64: str, header_y_hint: float = None) -> str:
    """
    Memindai gambar SOP, mendeteksi kotak flowchart, membaca nama kolom header
    secara OTOMATIS (tanpa daftar hardcoded), lalu menghasilkan cheat sheet urutan pelaksana.
    """
    try:
        img_data = base64.b64decode(img_base64)
        np_arr = np.frombuffer(img_data, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if img is None:
            return ""

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        thresh = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2
        )

        contours, _ = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        # --- Tahap 1: Temukan semua kotak flowchart ---
        # Flowchart SOP: berada di kolom tengah (Pelaksana).
        img_w = img.shape[1]
        x_min_allowed = int(0.15 * img_w)  # Lewati kolom No & Uraian
        x_max_allowed = int(0.75 * img_w)  # Lewati kolom Mutu Baku (Waktu, Kelengkapan, dll)
        
        shapes = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if 300 < area < 8000:
                x, y, w, h = cv2.boundingRect(cnt)
                aspect_ratio = w / float(h)
                # Lebar flowchart bisa mencapai 130px.
                if 30 < w < 130 and 15 < h < 130 and 0.3 < aspect_ratio < 4.0:
                    if x_min_allowed < x < x_max_allowed:
                        # Filter poligon untuk mengabaikan teks
                        epsilon = 0.04 * cv2.arcLength(cnt, True)
                        approx = cv2.approxPolyDP(cnt, epsilon, True)
                        if len(approx) <= 8:
                            shapes.append((x, y, w, h))

        if not shapes or len(shapes) < 2:
            return ""

        # Urutkan dari atas ke bawah
        shapes = sorted(shapes, key=lambda s: s[1])
        
        # Kelompokkan kotak berdasarkan baris (Y)
        # Toleransi 50px: cukup untuk menggabungkan belah ketupat & kotak dalam satu baris,
        # tapi cukup ketat untuk tidak menggabung baris yang berdekatan.
        rows = []
        for s in shapes:
            added = False
            for r in rows:
                if abs(s[1] - r[0][1]) < 50:
                    r.append(s)
                    added = True
                    break
            if not added:
                rows.append([s])

        # --- Tahap 2: Tentukan area Header tabel menggunakan Garis Horizontal ---
        min_shape_y = min(s[1] for s in shapes)
        
        if header_y_hint is not None:
            header_top_y = int(header_y_hint)
            header_bottom_y = int(header_y_hint + 120)
        else:
            # Fallback cerdas: Cari garis horizontal aktual dari tabel!
            # Garis horizontal tabel pasti panjang (minimal 1/4 lebar halaman)
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (img_w // 4, 1))
            lines_mask = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=2)
            cnts_lines, _ = cv2.findContours(lines_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            y_lines = sorted([cv2.boundingRect(c)[1] for c in cnts_lines])
            valid_lines = [y for y in y_lines if y < min_shape_y - 10]
            
            if len(valid_lines) >= 2:
                # Ambil area di antara dua garis horizontal terakhir sebelum flowchart pertama
                header_top_y = valid_lines[-2]
                header_bottom_y = valid_lines[-1]
            elif len(valid_lines) == 1:
                header_bottom_y = valid_lines[0]
                header_top_y = max(0, header_bottom_y - 120)
            else:
                # Jika tidak ada garis terdeteksi sama sekali, ambil 250px ke atas
                header_bottom_y = max(0, min_shape_y - 10)
                header_top_y = max(0, header_bottom_y - 250)

        # --- Tahap 3: Kelompokkan kotak per kolom X, lakukan OCR sekali per kolom ---
        # cluster threshold: kotak dalam radius 50px horizontal = satu kolom
        column_clusters = {}  # {x_center_repr: [x_values]}

        def find_cluster(x_center):
            for cx in column_clusters:
                if abs(cx - x_center) < 50:
                    return cx
            return None

        for x, y, w, h in shapes:
            xc = x + w // 2
            cx = find_cluster(xc)
            if cx is None:
                # Perlebar crop X (kiri-kanan) sejauh 70px dari pusat agar teks panjang (Kasubbag Umum) tidak terpotong
                column_clusters[xc] = (max(0, xc - 70), min(img.shape[1], xc + 70))

        # Bangun daftar rentang kolom untuk di-OCR
        col_ranges = [(xc, x1, x2) for xc, (x1, x2) in column_clusters.items()]

        # --- Tahap 4: OCR header kolom secara OTOMATIS ---
        columns_map = _discover_column_headers(img, header_top_y, header_bottom_y, col_ranges)

        # --- Tahap 5: Bangun Cheat Sheet ---
        cheat_sheet = (
            "\n=======================================================\n"
            "BOCORAN DATA SPASIAL DARI SISTEM OPENCV (AKURAT 100%):\n"
            f"Sistem mendeteksi ada {len(rows)} baris flowchart dari atas ke bawah.\n"
            "Berikut adalah nama PELAKSANA untuk masing-masing baris flowchart berdasarkan urutannya:\n"
        )

        for i, row_shapes in enumerate(rows):
            row_shapes = sorted(row_shapes, key=lambda s: s[0]) # urut kiri ke kanan
            pelaksana_list = []
            for (x, y, w, h) in row_shapes:
                xc = x + w // 2
                cx = find_cluster(xc)
                pelaksana = columns_map.get(cx, "Tidak Terdeteksi") if cx is not None else "Tidak Terdeteksi"
                if pelaksana not in pelaksana_list:
                    pelaksana_list.append(pelaksana)
            
            pelaksana_str = ", ".join(pelaksana_list)
            cheat_sheet += f"- Baris Flowchart ke-{i+1}: {pelaksana_str}\n"

        cheat_sheet += (
            "TUGAS ANDA: Gunakan bocoran di atas secara berurutan untuk mengisi kolom Pelaksana!\n"
            "Jika ada lebih dari satu pelaksana di satu baris (dipisah koma), cantumkan semuanya.\n"
            "=======================================================\n"
        )

        print(cheat_sheet)  # Debug
        return cheat_sheet

    except Exception as e:
        logger.error(f"extract_pelaksana_mapping error: {e}")
        return ""
