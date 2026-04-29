import cv2
import numpy as np
import fitz  # PyMuPDF
import os

def process_pdf_to_tables(input_pdf, output_pdf):
    # 1. เปิดไฟล์ PDF
    doc = fitz.open(input_pdf)
    processed_images = []
    
    print(f"กำลังเริ่มประมวลผลทั้งหมด {len(doc)} หน้า...")

    for page_num in range(len(doc)):
        # 2. แปลงหน้า PDF เป็นรูปภาพ (Pixmap)
        page = doc.load_page(page_num)
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2)) # เพิ่มความละเอียด 2เท่า (DPI)
        
        # แปลง Pixmap เป็น OpenCV format (numpy array)
        img_data = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, 3)
        img = cv2.cvtColor(img_data, cv2.COLOR_RGB2BGR)
        
        # --- เริ่ม Logic OpenCV สำหรับแต่ละหน้า ---
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
        
        # Crop ส่วนบนทิ้ง 35% (กำจัดกล่องเลขแบบฟอร์มที่มุมขวาบน)
        crop_y_start = int(h * 0.35)
        cropped_img = img[crop_y_start:h, 0:w]
        cropped_gray = gray[crop_y_start:h, 0:w]
        
        # หาตารางที่ใหญ่ที่สุด
        _, thresh = cv2.threshold(cropped_gray, 150, 255, cv2.THRESH_BINARY_INV)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if contours:
            # เลือก Contour ที่พื้นที่ใหญ่ที่สุด
            largest_cnt = max(contours, key=cv2.contourArea)
            x, y, table_w, table_h = cv2.boundingRect(largest_cnt)
            
            # ตัดเฉพาะส่วนตาราง
            final_table = cropped_img[y:y+table_h, x:x+table_w]
            
            # เก็บรูปภาพไว้ใน List (แปลงกลับเป็น RGB สำหรับ PDF)
            final_table_rgb = cv2.cvtColor(final_table, cv2.COLOR_BGR2RGB)
            processed_images.append(final_table_rgb)
            print(f"หน้า {page_num+1}: ตรวจพบตารางเรียบร้อย")
        else:
            print(f"หน้า {page_num+1}: ไม่พบตาราง")

    # 3. รวมรูปที่ได้กลับเป็น PDF
    if processed_images:
        new_doc = fitz.open()
        for img_arr in processed_images:
            # สร้างหน้าใหม่ตามขนาดรูป
            img_h, img_w, _ = img_arr.shape
            page = new_doc.new_page(width=img_w, height=img_h)
            
            # ใส่รูปเข้าไปในหน้า
            img_bytes = cv2.imencode('.jpg', cv2.cvtColor(img_arr, cv2.COLOR_RGB2BGR))[1].tobytes()
            page.insert_image(page.rect, stream=img_bytes)
            
        new_doc.save(output_pdf)
        new_doc.close()
        print(f"---------------------------------\nเสร็จสิ้น! บันทึกไฟล์ที่: {output_pdf}")
    
    doc.close()

# --- วิธีรันโปรแกรม ---
input_file = './data/devided/Constituency_สมหวัง.pdf'
output_file = './data/croped/Constituency_Tables_Only.pdf'
process_pdf_to_tables(input_file, output_file)