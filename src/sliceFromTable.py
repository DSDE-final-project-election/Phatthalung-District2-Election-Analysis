import os
from typhoon_ocr import ocr_document
import fitz  # PyMuPDF

def extract_raw_markdown(pdf_path, output_md_path):
    if not os.environ.get("TYPHOON_OCR_API_KEY"):
        print("❌ กรุณาตั้งค่า TYPHOON_OCR_API_KEY")
        return

    # 1. เปิด PDF
    doc = fitz.open(pdf_path)
    
    # เคลียร์ไฟล์เก่าถ้ามี หรือสร้างไฟล์ใหม่
    with open(output_md_path, 'w', encoding='utf-8') as f:
        f.write("# Raw Election Data\n\n")

    for page_num in range(len(doc)):
        unit_key = f"Unit_{page_num + 1}"
        print(f"⏳ กำลังแปลงหน้า {page_num + 1} เป็นรูปภาพ และส่งเข้า Typhoon...")
        
        try:
            # 2. แปลงเป็นรูปชั่วคราว (เพื่อหลีกเลี่ยง Poppler Error)
            page = doc.load_page(page_num)
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            temp_img_path = f"temp_{unit_key}.jpg"
            pix.save(temp_img_path)
            
            # 3. เรียกใช้ Typhoon OCR (จะได้ผลลัพธ์เป็น Markdown ดิบๆ)
            raw_markdown = ocr_document(pdf_or_image_path=temp_img_path)
            
            # ลบไฟล์ชั่วคราว
            if os.path.exists(temp_img_path):
                os.remove(temp_img_path)
            
            # 4. เขียน Raw Data ลงไฟล์ .md แยกเป็นสัดส่วน
            with open(output_md_path, 'a', encoding='utf-8') as f:
                f.write(f"## {unit_key}\n")
                f.write(raw_markdown + "\n\n")
                f.write("---\n\n") # เส้นคั่น
                
            print(f"✅ บันทึก Raw Data ของ {unit_key} สำเร็จ")
            
        except Exception as e:
            print(f"❌ Error ใน {unit_key}: {e}")
            if os.path.exists(f"temp_{unit_key}.jpg"):
                os.remove(f"temp_{unit_key}.jpg")

    doc.close()
    print(f"\n🎉 เสร็จสิ้น! ข้อมูล Raw Data ถูกบันทึกที่: {output_md_path}")

# ==========================================
# รันโปรแกรม
# ==========================================
input_file = './data/croped/Constituency_Tables_Only.pdf'
output_file = './data/sliced/Constituency_Raw_Data.md'

extract_raw_markdown(input_file, output_file)