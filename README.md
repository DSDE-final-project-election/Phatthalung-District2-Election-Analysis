# Polling Unit Lat/Long Mapping README

ไฟล์ชุดนี้ใช้สำหรับเชื่อมข้อมูลหน่วยเลือกตั้งจาก `ข้อมูลหน่วยเลือกตั้ง.pdf` เข้ากับไฟล์พิกัด `phatthalung_electorate2_latlong.csv` และเตรียม merge ต่อกับผลเลือกตั้งจาก `constituency.csv` / `partylist.csv`

## ไฟล์ที่แนะนำให้ใช้

ใช้ไฟล์นี้เป็นหลักสำหรับงาน visualization/map:

```text
phatthalung_polling_units_latlong_expanded.csv
```

เหตุผล: ไฟล์นี้ใช้ PDF เป็นฐาน จึงมีครบทุกหน่วยเลือกตั้ง `273` แถว แล้วเติม `latitude` / `longitude` เข้าไปให้ เหมาะกับการ merge กับผลเลือกตั้งมากกว่าไฟล์ lat/long เดิมที่มี `272` แถว

## Key สำหรับ merge กับผลเลือกตั้ง

ผล OCR ใช้ `unit_index` แบบเริ่มจาก `0` ส่วน PDF ใช้เลขหน่วยเลือกตั้งจริงแบบเริ่มจาก `1`

```text
unit_index = polling_unit_no - 1
```

แนะนำให้ merge ด้วย:

```text
source_subdistrict_pdf + unit_index
```

ถ้า `constituency.csv` / `partylist.csv` ยังไม่มีคอลัมน์ตำบล ให้ดึงจาก `source_file` ก่อน เช่น:

```text
24ตำบลมะกอกเหนือ(เทศบาล).pdf -> มะกอกเหนือ(เทศบาล)
```

แล้วนำไป match กับ `source_subdistrict_pdf`

## 1. phatthalung_electorate2_latlong.csv

ไฟล์พิกัดต้นฉบับ มี 272 แถว

| Column | Meaning |
|---|---|
| `province` | จังหวัด |
| `registrar` | หน่วยงาน/อำเภอ/เทศบาลที่รับผิดชอบ เช่น `อำเภอกงหรา`, `ท้องถิ่นเทศบาลตำบลชะรัด` |
| `subdistrict` | ตำบลจากไฟล์ lat/long |
| `electorate` | เขตเลือกตั้ง ในชุดนี้เป็นเขต `2` |
| `location` | ชื่อสถานที่เลือกตั้งจากไฟล์ lat/long |
| `latitude` | ละติจูด |
| `longitude` | ลองจิจูด |

หมายเหตุ: ไฟล์นี้ยังไม่มีเลขหน่วยเลือกตั้ง จึงยัง merge กับผล OCR รายหน่วยไม่ได้ตรง ๆ

## 2. phatthalung_polling_units_from_pdf.csv

ไฟล์ที่ extract จาก `ข้อมูลหน่วยเลือกตั้ง.pdf` โดยตรง มี 273 แถว

| Column | Meaning |
|---|---|
| `pdf_page` | เลขหน้าของ PDF ที่ record นี้อยู่ |
| `pdf_sequence` | เลขลำดับรวมใน PDF |
| `polling_unit_no` | เลขหน่วยเลือกตั้งจริง เริ่มจาก `1` |
| `district` | อำเภอ |
| `source_subdistrict_pdf` | ชื่อตำบลตาม PDF รวมกรณีเทศบาล เช่น `มะกอกเหนือ(เทศบาล)` |
| `moo` | หมู่ที่ ถ้ามีหลายค่าจะคั่นด้วย `|` |
| `polling_place_pdf` | ชื่อสถานที่เลือกตั้งตาม PDF |
| `registered_voters_66` | จำนวนผู้มีสิทธิเลือกตั้ง ปี 2566 จาก PDF |

## 3. phatthalung_electorate2_latlong_with_units.csv

ไฟล์ที่เอา `phatthalung_electorate2_latlong.csv` เป็นฐาน แล้วเติมเลขหน่วยจาก PDF มี 272 แถว

| Column | Meaning |
|---|---|
| `province` | จังหวัดจากไฟล์ lat/long |
| `registrar` | หน่วยงาน/อำเภอ/เทศบาลจากไฟล์ lat/long |
| `subdistrict` | ตำบลจากไฟล์ lat/long |
| `electorate` | เขตเลือกตั้ง |
| `location` | สถานที่เลือกตั้งจากไฟล์ lat/long |
| `latitude` | ละติจูด |
| `longitude` | ลองจิจูด |
| `district` | อำเภอที่ match จาก PDF |
| `source_subdistrict_pdf` | ตำบลตาม PDF |
| `polling_unit_no` | เลขหน่วยเลือกตั้งจริง เริ่มจาก `1` |
| `unit_index` | เลขหน่วยสำหรับ merge กับ OCR เริ่มจาก `0` |
| `moo` | หมู่ที่จาก PDF |
| `polling_place_pdf` | สถานที่เลือกตั้งจาก PDF |
| `registered_voters_66` | จำนวนผู้มีสิทธิเลือกตั้ง ปี 2566 จาก PDF |
| `pdf_sequence` | เลขลำดับรวมใน PDF |
| `pdf_page` | เลขหน้า PDF |
| `unit_match_method` | วิธีที่ใช้ match ระหว่าง lat/long กับ PDF |
| `unit_match_score` | คะแนนความคล้ายของชื่อสถานที่ 0-1 ยิ่งใกล้ 1 ยิ่งมั่นใจ |
| `unit_match_note` | หมายเหตุจากการ match |

หมายเหตุ: ไฟล์นี้ยังขาด 1 หน่วย เพราะใช้ไฟล์ lat/long เดิมเป็นฐาน ซึ่งมี 272 แถว

## 4. phatthalung_electorate2_latlong_unit_match_report.csv

ไฟล์ตรวจสอบเฉพาะแถวที่ match แบบ fuzzy หรือควรเปิดดูเพิ่ม มี 34 แถว

| Column | Meaning |
|---|---|
| `registrar` | หน่วยงาน/อำเภอ/เทศบาลจากไฟล์ lat/long |
| `subdistrict` | ตำบลจากไฟล์ lat/long |
| `location` | สถานที่จากไฟล์ lat/long |
| `district` | อำเภอที่ match จาก PDF |
| `source_subdistrict_pdf` | ตำบลตาม PDF |
| `polling_unit_no` | เลขหน่วยเลือกตั้งจริง |
| `unit_index` | เลขหน่วยสำหรับ merge กับ OCR |
| `polling_place_pdf` | สถานที่เลือกตั้งตาม PDF |
| `unit_match_method` | วิธี match เช่น `location_fuzzy` |
| `unit_match_score` | คะแนนความคล้ายของชื่อสถานที่ |
| `unit_match_note` | หมายเหตุจากการ match |

ส่วนใหญ่เป็นความต่างของการสะกด เช่น `ประจำ` vs `ประจ า` หรือมีคำว่า `หมู่ที่` เพิ่มเข้ามา

## 5. phatthalung_polling_units_latlong_expanded.csv

ไฟล์หลักที่แนะนำให้ใช้ มี 273 แถว ใช้ PDF เป็นฐาน แล้วเติม lat/long จากไฟล์พิกัด

| Column | Meaning |
|---|---|
| `pdf_page` | เลขหน้า PDF |
| `pdf_sequence` | เลขลำดับรวมใน PDF |
| `district` | อำเภอ |
| `source_subdistrict_pdf` | ตำบลตาม PDF |
| `polling_unit_no` | เลขหน่วยเลือกตั้งจริง เริ่มจาก `1` |
| `unit_index` | เลขหน่วยสำหรับ merge กับ OCR เริ่มจาก `0` |
| `moo` | หมู่ที่จาก PDF |
| `polling_place_pdf` | สถานที่เลือกตั้งจาก PDF |
| `registered_voters_66` | จำนวนผู้มีสิทธิเลือกตั้ง ปี 2566 จาก PDF |
| `province` | จังหวัดจากไฟล์ lat/long |
| `registrar` | หน่วยงาน/อำเภอ/เทศบาลจากไฟล์ lat/long |
| `latlong_subdistrict` | ตำบลจากไฟล์ lat/long |
| `latlong_location` | สถานที่เลือกตั้งจากไฟล์ lat/long |
| `latitude` | ละติจูด |
| `longitude` | ลองจิจูด |
| `electorate` | เขตเลือกตั้ง |
| `latlong_row_id` | เลข row เดิมจากไฟล์ lat/long ใช้ trace กลับไปหา record ต้นทาง |
| `latlong_match_method` | วิธี match lat/long เข้ากับ PDF |
| `latlong_match_score` | คะแนนความคล้ายของชื่อสถานที่ 0-1 |
| `coordinate_reused_count` | จำนวนหน่วยที่ใช้พิกัด row เดียวกัน ถ้ามากกว่า 1 แปลว่ามีหลายหน่วยอยู่สถานที่เดียวกัน |
| `merge_key_subdistrict_unit` | key สำเร็จรูปในรูป `source_subdistrict_pdf|unit_index` |

หมายเหตุสำคัญ: `ชะรัด(เทศบาล)` หน่วย 5 และ 6 ใช้สถานที่เดียวกันคือ `อาคารสำนักงานเทศบาลตำบลชะรัด` จึงใช้พิกัดเดียวกัน และ `coordinate_reused_count = 2`

## 6. phatthalung_polling_units_latlong_expanded_review.csv

ไฟล์ review ของไฟล์ expanded มี 36 แถว รวมแถวที่ match แบบ fuzzy หรือใช้พิกัดซ้ำ

| Column | Meaning |
|---|---|
| `district` | อำเภอ |
| `source_subdistrict_pdf` | ตำบลตาม PDF |
| `polling_unit_no` | เลขหน่วยเลือกตั้งจริง |
| `unit_index` | เลขหน่วยสำหรับ merge กับ OCR |
| `polling_place_pdf` | สถานที่เลือกตั้งจาก PDF |
| `latlong_location` | สถานที่จากไฟล์ lat/long ที่ถูก match |
| `latitude` | ละติจูดที่เติมให้ |
| `longitude` | ลองจิจูดที่เติมให้ |
| `latlong_match_method` | วิธี match |
| `latlong_match_score` | คะแนนความคล้ายของชื่อสถานที่ |
| `coordinate_reused_count` | จำนวนครั้งที่พิกัดนี้ถูกใช้ |

ใช้ไฟล์นี้เพื่อตรวจความมั่นใจก่อนนำไปทำแผนที่จริง

## ความหมายของ match method

| Value | Meaning |
|---|---|
| `location_exact_normalized` | ชื่อสถานที่ตรงกันหลัง normalize ข้อความ เช่น เอาช่องว่าง/รูปสระบางแบบออก |
| `location_fuzzy` | ชื่อสถานที่คล้ายกันมาก แต่สะกดไม่เหมือนกัน 100% |
| `unmatched` | ไม่พบคู่ match ที่มั่นใจพอ |

ในไฟล์ที่สร้างล่าสุด ไม่มี `unmatched`

## ตัวอย่างการ merge ด้วย pandas

```python
import pandas as pd

units = pd.read_csv(
    "phatthalung_polling_units_latlong_expanded.csv",
    encoding="utf-8-sig",
)

constituency = pd.read_csv(
    "output/constituency.csv",
    encoding="utf-8-sig",
)

# ต้องเตรียมคอลัมน์ source_subdistrict_pdf ใน constituency ก่อน
# เช่น extract จาก source_file แล้ว normalize ให้ตรงกับชื่อใน units

merged = constituency.merge(
    units,
    on=["source_subdistrict_pdf", "unit_index"],
    how="left",
    validate="many_to_one",
)
```

ถ้าใช้ข้อมูลรายตำบลจาก `source_file` ให้ระวังชื่อเทศบาล เช่น `มะกอกเหนือ` กับ `มะกอกเหนือ(เทศบาล)` ต้องแยกกัน

## สคริปต์ merge สำเร็จรูป

มีสคริปต์สำหรับ merge ผลเลือกตั้งกับ lat/long แล้ว:

```text
merge_election_with_latlong.py
```

รันจาก root ของโปรเจกต์:

```bash
python merge_election_with_latlong.py
```

ค่า default:

| Input | Default path |
|---|---|
| constituency result | `constituency.csv` หรือ `output/constituency.csv` |
| party-list result | `partylist.csv` หรือ `output/partylist.csv` |
| polling unit lat/long | `phatthalung_polling_units_latlong_expanded.csv` |
| output folder | `merged_output/` |

ไฟล์ output ที่ได้:

| Output | Meaning |
|---|---|
| `merged_output/constituency_with_latlong*.csv` | ผล ส.ส.เขต แบบ wide table พร้อม lat/long |
| `merged_output/partylist_with_latlong*.csv` | ผลบัญชีรายชื่อ แบบ wide table พร้อม lat/long |
| `merged_output/election_results_with_latlong_long*.csv` | ผลเลือกตั้งแบบ long table หนึ่งแถวต่อผู้สมัคร/พรรค เหมาะกับ Streamlit/Plotly |
| `merged_output/latlong_merge_unmatched_report*.csv` | รายการแถวที่ merge lat/long ไม่ได้ |

สคริปต์จะไม่เขียนทับไฟล์เดิม ถ้าชื่อ output ซ้ำ จะสร้างไฟล์ใหม่แบบ `_v2`, `_v3`, ...

คอลัมน์สำคัญที่เพิ่มหลัง merge:

| Column | Meaning |
|---|---|
| `polling_unit_no` | เลขหน่วยเลือกตั้งจริง เริ่มจาก `1` |
| `unit_index` | เลขหน่วยแบบ OCR เริ่มจาก `0` |
| `latitude` | ละติจูด |
| `longitude` | ลองจิจูด |
| `registered_voters_66` | จำนวนผู้มีสิทธิเลือกตั้งจาก PDF |
| `polling_place_pdf` | สถานที่เลือกตั้งจาก PDF |
| `latlong_merge_status` | `matched` หรือ `unmatched` |
| `latlong_result_match_method` | วิธี match result กับ lat/long เช่น `exact_key`, `fallback_unique_subdistrict_key` |

หมายเหตุจากรอบทดสอบล่าสุด:

```text
Constituency matched/unmatched: 273 / 15
Party-list matched/unmatched  : 273 / 15
```

แถวที่ unmatched ส่วนใหญ่เป็น advance voting ที่ไม่มีพิกัดหน่วยเลือกตั้งปกติ และมีแถว election day เกินจาก `เกาะเต่า` / `ลานข่อย` บางหน่วย ควรตรวจใน `latlong_merge_unmatched_report*.csv`
