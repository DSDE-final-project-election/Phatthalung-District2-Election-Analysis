import PyPDF2
import math

def split_election_pdfs(input_pdf_path, const_output_path, partylist_output_path):
    # กำหนดแพทเทิร์นว่า 1 หน่วยเลือกตั้งมีกี่หน้า
    PAGES_PER_UNIT = 6
    
    # กำหนด Index ย่อยในแต่ละชุด (เริ่มนับจาก 0)
    # แบบแบ่งเขต คือหน้า 1-2 ของชุด (Index 0, 1)
    const_indices = [0] 
    
    # แบบบัญชีรายชื่อ คือหน้า 3-6 ของชุด (Index 2, 3, 4, 5)
    partylist_indices = [2, 3, 4] 

    with open(input_pdf_path, 'rb') as infile:
        reader = PyPDF2.PdfReader(infile)
        total_pages = len(reader.pages)
        total_units = math.ceil(total_pages / PAGES_PER_UNIT)
        
        print(f"พบเอกสารทั้งหมด {total_pages} หน้า (คาดว่ามีประมาณ {total_units} หน่วยเลือกตั้ง)")
        
        const_writer = PyPDF2.PdfWriter()
        partylist_writer = PyPDF2.PdfWriter()
        
        # ลูปตัดหน้าตามแพทเทิร์นทีละ 6 หน้า
        for i in range(0, total_pages, PAGES_PER_UNIT):
            
            # ดึงหน้าของ "แบบแบ่งเขต"
            for offset in const_indices:
                page_num = i + offset
                if page_num < total_pages:
                    const_writer.add_page(reader.pages[page_num])
                    
            # ดึงหน้าของ "แบบบัญชีรายชื่อ"
            for offset in partylist_indices:
                page_num = i + offset
                if page_num < total_pages:
                    partylist_writer.add_page(reader.pages[page_num])
                    
        # บันทึกไฟล์แบบแบ่งเขต
        with open(const_output_path, 'wb') as const_out:
            const_writer.write(const_out)
            
        # บันทึกไฟล์แบบบัญชีรายชื่อ
        with open(partylist_output_path, 'wb') as partylist_out:
            partylist_writer.write(partylist_out)
            
    print("--------------------------------------------------")
    print(f"สร้างไฟล์เสร็จเรียบร้อย!")
    print(f"1. ไฟล์แบบแบ่งเขต: {const_output_path}")
    print(f"2. ไฟล์แบบบัญชีรายชื่อ: {partylist_output_path}")

# ==========================================
# วิธีใช้งาน: ระบุชื่อไฟล์ต้นฉบับ และชื่อไฟล์ปลายทางที่ต้องการ
# ==========================================
input_file = './data/raw/46ตำบลสมหวัง.pdf'
const_file = './data/processed/Constituency_สมหวัง.pdf' # ชื่อไฟล์แบบแบ่งเขตที่จะได้
partylist_file = './data/processed/PartyList_สมหวัง.pdf' # ชื่อไฟล์แบบบัญชีรายชื่อที่จะได้

split_election_pdfs(input_file, const_file, partylist_file)