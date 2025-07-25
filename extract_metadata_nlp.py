import fitz  # PyMuPDF
import spacy
from datetime import datetime

# Load spaCy English model
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    raise RuntimeError("❌ Run: python -m spacy download en_core_web_sm")

def extract_first_page_text(pdf_path, output_raw="metadata_raw.txt"):
    with fitz.open(pdf_path) as doc:
        first_page_text = doc[0].get_text("text")
        with open(output_raw, "w", encoding="utf-8") as f:
            f.write(first_page_text)
        print(f"✅ First page text saved to: {output_raw}")
    return first_page_text

def extract_metadata_nlp(text):
    doc = nlp(text)
    newspaper_name = "Unknown"
    edition = "Unknown"
    date_str = "Unknown"

    # Extract organization (ORG) as newspaper name
    for ent in doc.ents:
        if ent.label_ == "ORG" and 5 < len(ent.text.strip()) < 50:
            newspaper_name = ent.text.strip()
            break

    # Extract city/edition
    for ent in doc.ents:
        if ent.label_ in ("GPE", "LOC") and 3 < len(ent.text.strip()) < 40:
            edition = ent.text.strip()
            break

    # Extract date
    for ent in doc.ents:
        if ent.label_ == "DATE":
            raw_date = ent.text.strip()
            try:
                # Try parsing to standard format
                parsed = datetime.strptime(raw_date, "%d %B %Y")
                date_str = parsed.strftime("%d %B %Y")
                break
            except:
                continue

    metadata = {
        "newspaper_name": newspaper_name,
        "edition": edition,
        "date": date_str
    }

    with open("extracted_metadata.txt", "w", encoding="utf-8") as f:
        for k, v in metadata.items():
            f.write(f"{k}: {v}\n")

    print("✅ NLP-based metadata saved to: extracted_metadata.txt")
    return metadata

# === Run ===
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("❌ Usage: python extract_metadata_nlp.py <PDF_PATH>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    raw_text = extract_first_page_text(pdf_path)
    extract_metadata_nlp(raw_text)