import re
import spacy
from transformers import pipeline, AutoTokenizer
from datetime import datetime
from pymongo import MongoClient
import hashlib

# Load spaCy model
try:
    nlp = spacy.load('en_core_web_sm')
except OSError:
    raise RuntimeError("Run: python -m spacy download en_core_web_sm")

# Load summarizer
summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
tokenizer = AutoTokenizer.from_pretrained("facebook/bart-large-cnn")

# === Text Cleaning Utilities ===
def spacy_sent_tokenize(text):
    doc = nlp(text)
    return [sent.text.strip() for sent in doc.sents]

def clean_truncated_heading(heading):
    heading = re.sub(r"\b(?:in|of|at|for|by|on|with|during|and|to)\b$", '', heading.strip(), flags=re.IGNORECASE)
    heading = re.sub(r"\b\w{1,3}$", '', heading).strip()
    heading = re.sub(r"\bs\b", "'s", heading)
    return heading

def clean_article_text(text):
    # Remove common junk
    junk_patterns = [
        r"(?i)^follow us.*",
        r"https?://\S+",
        r"(?i)vol\.\s*\d+\s*no\.\s*\d+",
        r"(?i)^page\s+\d+",
    ]
    for pattern in junk_patterns:
        text = re.sub(pattern, '', text)

    # Remove excess whitespace
    text = re.sub(r"\n{2,}", '\n', text)
    text = re.sub(r"[ \t]{2,}", ' ', text)

    # Fix common typos
    typo_fixes = {
        "no-fy": "no-fly",
        "kick of": "kick off",
        "fowers": "flowers",
        "s Ganderbal": "’s Ganderbal",
        "oors": "floors",
        "oicials": "officials",
        "overthe": "over the",
        "arrangement,which": "arrangement, which"
    }
    for wrong, correct in typo_fixes.items():
        text = text.replace(wrong, correct)

    return text.strip()

def extract_metadata(text):
    newspaper_name = "The Hindu"
    date_match = re.search(r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+(\w+\s+\d{1,2},\s+\d{4})", text)
    try:
        date_obj = datetime.strptime(date_match.group(2), "%B %d, %Y").date() if date_match else None
    except Exception:
        date_obj = None
    city_list = re.findall(r"(Chennai|Hyderabad|Mumbai|Bengaluru|Kolkata|Delhi|Noida|Coimbatore|Madurai|Thiruvananthapuram|Kochi|Lucknow|Patna|Cuttack|Visakhapatnam|Mangaluru|Tiruchirapalli|Hubballi|Malappuram|Mohali|Vijayawada)", text)
    return newspaper_name, str(date_obj) if date_obj else None, city_list[0] if city_list else None

def generate_hashtags(text, max_tags=5):
    from sklearn.feature_extraction.text import TfidfVectorizer
    import numpy as np

    tag_stoplist = {
        "news", "centre", "government", "ajith", "home", "factory", "kill", "day", "body",
        "cooperation", "halt", "facility", "france", "batch", "expand", "lead"
    }
    doc = nlp(clean_article_text(text))
    cleaned = ' '.join([token.lemma_.lower() for token in doc if not token.is_stop and token.is_alpha])
    preview = " ".join(spacy_sent_tokenize(cleaned)[:4])

    tfidf = TfidfVectorizer(max_features=100, stop_words='english')
    tfidf_matrix = tfidf.fit_transform([cleaned])
    feature_array = np.array(tfidf.get_feature_names_out())
    scores = tfidf_matrix.toarray()[0]
    top_keywords = feature_array[scores.argsort()[::-1]][:max_tags * 3]

    keywords = set()
    for kw in top_keywords:
        kw_clean = kw.strip().lower().replace(' ', '')
        if kw_clean not in tag_stoplist and 2 < len(kw_clean) < 25:
            keywords.add(kw_clean)

    for ent in doc.ents:
        if ent.label_ in {"GPE", "ORG", "EVENT", "PERSON"}:
            ent_text = ent.text.strip().lower().replace(' ', '')
            if ent_text in preview and ent_text not in tag_stoplist:
                keywords.add(ent_text)

    return [f"#{k}" for k in sorted(keywords)][:max_tags]

def generate_heading(article_text):
    article_text = clean_article_text(article_text)
    sentences = spacy_sent_tokenize(article_text)
    short_intro = " ".join(sentences[:2])
    try:
        tokens = tokenizer(short_intro, return_tensors="pt", truncation=False)
        max_len = min(20, max(5, int(tokens["input_ids"].shape[1] * 0.5)))
        summary = summarizer(short_intro, max_length=max_len, min_length=4, do_sample=False)[0]["summary_text"]
        return clean_truncated_heading(summary.replace('.', '').strip())
    except Exception:
        return sentences[0] if sentences else "Untitled"

def summarize_article(article_text, max_points=5):
    article_text = clean_article_text(article_text)
    sentences = spacy_sent_tokenize(article_text)
    chunks = [" ".join(sentences[i:i+6]) for i in range(0, len(sentences), 6)]
    summary_points = []

    for chunk in chunks:
        try:
            tokens = tokenizer(chunk, return_tensors="pt", truncation=False)
            if tokens["input_ids"].shape[1] < 40:
                continue
            max_len = min(100, max(30, int(tokens["input_ids"].shape[1] * 0.5)))
            summary = summarizer(chunk, max_length=max_len, min_length=20, do_sample=False)[0]["summary_text"]
            summary_points += [p.strip() for p in spacy_sent_tokenize(summary) if len(p.strip()) > 10]
        except Exception:
            continue
    return summary_points[:max_points]

def generate_summary_paragraph(article_text):
    cleaned = clean_article_text(article_text)
    try:
        tokens = tokenizer(cleaned, return_tensors="pt", truncation=False)
        if tokens["input_ids"].shape[1] > 40:
            return summarizer(cleaned, max_length=150, min_length=40, do_sample=False)[0]["summary_text"]
    except Exception:
        return None

def split_into_articles(text):
    return [s.strip() for s in re.split(r'\n-{3,}\n', text.strip()) if len(s.strip()) > 100 and not s.strip().startswith("PAGE ")]

def process_file(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()

    articles = split_into_articles(text)
    print(f"🧩 Found {len(articles)} article(s)")
    results = []

    for article in articles:
        cleaned_article = clean_article_text(article)
        heading = generate_heading(cleaned_article)
        summary_points = summarize_article(cleaned_article)
        summary_paragraph = generate_summary_paragraph(cleaned_article)
        hashtags = generate_hashtags(cleaned_article)
        newspaper, date, city = extract_metadata(cleaned_article)

        if summary_points:
            results.append({
                "heading": heading,
                "summary_points": summary_points,
                "summary_paragraph": summary_paragraph,
                "hashtags": hashtags,
                "article_text": cleaned_article,
                "newspaper": newspaper,
                "date": date,
                "city": city
            })
    return results

def save_to_mongodb(summaries, input_path=None, mongo_uri="mongodb://localhost:27017", db_name="news_summarizer", collection_name="summaries"):
    try:
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=3000)
        client.server_info()
    except Exception as e:
        print("❌ MongoDB connection failed:", e)
        return

    collection = client[db_name][collection_name]
    for entry in summaries:
        doc_id = hashlib.md5((entry["heading"] + " ".join(entry["summary_points"])).encode()).hexdigest()
        doc = {
            "_id": doc_id,
            "heading": entry["heading"],
            "summary_points": entry["summary_points"],
            "summary_paragraph": entry["summary_paragraph"],
            "hashtags": entry["hashtags"],
            "article_text": entry["article_text"],
            "source_file": input_path,
            "timestamp": datetime.utcnow(),
            "newspaper": entry["newspaper"],
            "date": entry["date"],
            "city": entry["city"]
        }
        collection.update_one({"_id": doc_id}, {"$set": doc}, upsert=True)

    print(f"✅ {len(summaries)} summaries saved to MongoDB.")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("❌ Provide input file path")
        sys.exit(1)

    file_path = sys.argv[1]
    data = process_file(file_path)
    save_to_mongodb(data, input_path=file_path)
    print("✅ All done.")
