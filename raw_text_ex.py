import fitz  # PyMuPDF
import re
import os
from datetime import datetime

# -----------------------------------
# 🗞️ Extended Newspaper Mapping
# -----------------------------------
newspaper_map = {
    "HT": "Hindustan Times",
    "TOI": "Times of India",
    "FE": "Financial Express",
    "TH": "The Hindu",
    "BL": "Business Line",
    "ET": "Economic Times",
    "IE": "Indian Express",
    "Asian Age": "Asian Age",
    "Deccan Chronicle": "Deccan Chronicle",
    "Tribune": "Tribune",
    "Pioneer": "Pioneer",
    "MINT": "Mint",
    "Business Standard": "Business Standard",
    "Hindu_Hindi": "The Hindu Hindi",
    "TH-School": "The Hindu School Edition",
    "INDIAN EXPRESS UPSC": "Indian Express UPSC Edition"
}

# 🏙️ Known Edition Cities
known_editions = [
    # Tier-1 & Metro Cities
    "Delhi", "Mumbai", "Chennai", "Kolkata", "Bangalore", "Hyderabad",

    # Tier-2 Cities
    "Ahmedabad", "Pune", "Lucknow", "Chandigarh", "Jaipur", "Patna", "Ranchi", "Bhopal", "Nagpur", "Indore",

    # Others in your screenshots or common editions
    "Jalandhar", "Noida", "Ghaziabad", "Kanpur", "Varanasi", "Guwahati", "Thiruvananthapuram", "Vijayawada",
    "Coimbatore", "Visakhapatnam", "Raipur", "Ludhiana", "Dehradun", "Srinagar", "Shimla",

    # International Editions
    "London", "New York", "Dubai", "Doha", "Singapore", "International"
]


# -----------------------------------
# 📥 Extract PDF Text
# -----------------------------------
def extract_text_from_pdf(pdf_path):
    text = ""
    with fitz.open(pdf_path) as doc:
        for page in doc:
            text += page.get_text()
    return text

# -----------------------------------
# 📅 Extract Date from Filename
# -----------------------------------
def extract_date_from_filename(filename):
    clean_filename = re.sub(r"[~‹•@+]", "-", filename)

    patterns = [
        (r'\d{4}[-_/\.]\d{2}[-_/\.]\d{2}', "%Y-%m-%d"),
        (r'\d{2}[-_/\.]\d{2}[-_/\.]\d{4}', "%d-%m-%Y"),
        (r'\d{2}[-_/\.]\d{2}[-_/\.]\d{2}', "%d-%m-%y")
    ]

    for pattern, fmt in patterns:
        match = re.search(pattern, clean_filename)
        if match:
            raw_date = match.group(0)
            normalized = re.sub(r'[-_/\.]', '-', raw_date)
            try:
                date_obj = datetime.strptime(normalized, fmt)
                return date_obj.strftime("%B %d, %Y")
            except:
                continue
    return "Date not found"

# -----------------------------------
# 📰 Extract Newspaper Name from Filename
# -----------------------------------
def extract_newspaper_from_filename(filename):
    cleaned = filename.replace("_", " ").replace("-", " ").replace("•", " ").lower()
    for key, full_name in newspaper_map.items():
        if key.lower() in cleaned:
            return full_name
    return "Unknown Newspaper"

# -----------------------------------
# 🏙️ Extract Edition (city or special)
# -----------------------------------
def extract_edition(pdf_filename, pdf_text):
    # Normalize filename
    cleaned_name = pdf_filename.replace("_", " ").replace("-", " ").replace("•", " ").lower()

    # 1️⃣ Check for known city editions in filename
    for city in known_editions:
        if city.lower() in cleaned_name:
            return f"{city} Edition"

    # 2️⃣ Check for special edition keywords
    special_editions = {
        "school": "School Edition",
        "student": "Student Edition",
        "upsc": "UPSC IAS Edition",
        "ias": "UPSC IAS Edition",
        "cbse": "CBSE Special Edition",
        "ad free": "Ad-Free Edition",
        "ad-free": "Ad-Free Edition"
    }

    for keyword, edition_label in special_editions.items():
        if keyword.lower() in cleaned_name:
            return edition_label

    # 3️⃣ Fallback to scanning text content
    for line in pdf_text.splitlines()[:10]:
        for city in known_editions:
            if city.lower() in line.lower():
                return f"{city} Edition"

    return "Edition not found"


# -----------------------------------
# 🛠️ Main Processing Function
# -----------------------------------
def process_pdf(pdf_path):
    filename = os.path.basename(pdf_path)
    text = extract_text_from_pdf(pdf_path)

    newspaper = extract_newspaper_from_filename(filename)
    date = extract_date_from_filename(filename)
    edition = extract_edition(filename, text)

    base_name = os.path.splitext(filename)[0]
    output_file = f"{base_name}_metadata.txt"

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"📰 Newspaper: {newspaper}\n")
        f.write(f"📅 Date: {date}\n")
        f.write(f"🏙️ Edition: {edition}\n")

    print(f"✅ Metadata saved to {output_file}")

# ------------ MAIN ------------
if __name__ == "__main__":
    pdf_path = "THE HINDU HD International Editable Full Edition 14~06~2025.pdf"  # Change this to your test file

    if os.path.isfile(pdf_path) and pdf_path.lower().endswith(".pdf"):
        print(f"🔍 Processing: {pdf_path}")
        process_pdf(pdf_path)
    else:
        print("❌ File not found or not a PDF.")
