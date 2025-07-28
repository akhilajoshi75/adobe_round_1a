import os
import json
import re
import pdfplumber
import numpy as np
from collections import defaultdict
from pathlib import Path

INPUT_DIR = "/app/input"
OUTPUT_DIR = "/app/output"

def dedupe_chars(text):
    return re.sub(r'([A-Za-z])\1{2,}', r'\1', text)

def clean_line(text):
    text = dedupe_chars(text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def is_noisy_heading(text):
    text = text.strip(" :-•●")
    if len(text) < 5:
        return True
    if re.fullmatch(r"[A-Z\d\s,]+", text) and len(text.split()) <= 4:
        return True
    if re.search(r"\.com|\bwww\b|RSVP\b|^\d{5}$", text, re.IGNORECASE):
        return True
    if text.lower().strip(":") in {"address", "date", "time", "location", "page"}:
        return True
    return False

def extract_lines(words, y_tol=2):
    lines = defaultdict(list)
    for w in words:
        y_key = round(w['top'] / y_tol)
        lines[(w['page_num'], y_key)].append(w)
    merged_lines = []
    for (page_num, y_key), line_words in lines.items():
        line_words = sorted(line_words, key=lambda x: x['x0'])
        line_text = ''
        prev_right = None
        for w in line_words:
            if prev_right is not None and w['x0'] - prev_right > 2:
                line_text += ' '
            line_text += w['text']
            prev_right = w['x1']
        avg_size = sum(w['size'] for w in line_words) / len(line_words)
        fontnames = [w['fontname'] for w in line_words]
        is_bold = any("Bold" in f or "bold" in f for f in fontnames)
        merged_lines.append({
            "text": clean_line(line_text),
            "raw_text": line_text,
            "size": avg_size,
            "font": fontnames[0],
            "is_bold": is_bold,
            "x0": min(w['x0'] for w in line_words),
            "x1": max(w['x1'] for w in line_words),
            "y0": min(w['top'] for w in line_words),
            "y1": max(w['bottom'] for w in line_words),
            "page": page_num - 1  # 0-indexed
        })
    return merged_lines

def merge_multiline_title(lines):
    first_page = [l for l in lines if l['page'] == 0]
    top_lines = sorted([l for l in first_page if l['y0'] < 120], key=lambda l: l['y0'])
    if not top_lines:
        return ''
    max_font = max(l['size'] for l in top_lines)
    title_lines = [l for l in top_lines if abs(l['size'] - max_font) < 1.5]
    merged = ' '.join(clean_line(l['text']) for l in title_lines)
    return re.sub(r'\s+', ' ', merged).strip()

def is_form_pdf(lines):
    first_page = [l for l in lines if l['page'] == 0]
    short_lines = [l for l in first_page if len(l['text']) < 30]
    field_words = ['name', 'date', 'form', 'designation', 'service', 'advance', 'book', 'block', 'relationship', 'fare']
    field_labels = sum(any(w in l['text'].lower() for w in field_words) for l in first_page)
    return (len(short_lines) > 0.5 * len(first_page)) and (field_labels > 2)

def merge_multiline_headings(headings):
    merged = []
    skip = set()
    for i, h in enumerate(headings):
        if i in skip:
            continue
        merged_line = h.copy()
        j = i + 1
        while j < len(headings):
            nxt = headings[j]
            if (nxt['page'] == merged_line['page'] and
                abs(nxt['y0'] - merged_line['y1']) < 15 and
                abs(nxt['size'] - merged_line['size']) < 1.2 and
                abs(nxt['x0'] - merged_line['x0']) < 10):
                merged_line['text'] += ' ' + nxt['text']
                merged_line['y1'] = nxt['y1']
                skip.add(j)
                j += 1
            else:
                break
        merged_line['text'] = clean_line(merged_line['text'])
        merged.append(merged_line)
    return merged

def extract_headings(lines):
    content_lines = [l for l in lines if len(l['text']) >= 5]
    all_sizes = [l['size'] for l in content_lines]
    if not all_sizes:
        return []

    size_90 = np.percentile(all_sizes, 90)
    size_75 = np.percentile(all_sizes, 75)
    size_60 = np.percentile(all_sizes, 60)

    heading_candidates = []
    for l in content_lines:
        level = None
        if l['size'] >= size_90:
            level = "H1"
        elif l['size'] >= size_75:
            level = "H2"
        elif l['size'] >= size_60:
            level = "H3"
        if level:
            l['level'] = level
            heading_candidates.append(l)

    heading_candidates = sorted(heading_candidates, key=lambda l: (l['page'], l['y0']))
    merged = merge_multiline_headings(heading_candidates)

    result_outline = []
    seen = set()
    for h in merged:
        htext = clean_line(h['text'])
        if is_noisy_heading(htext):
            continue
        key = (htext, h['page'], h['level'])
        if key not in seen:
            result_outline.append({
                "level": h['level'],
                "text": htext,
                "page": h['page']
            })
            seen.add(key)

    return result_outline[:10]

def process_pdf(pdf_path, output_path):
    with pdfplumber.open(pdf_path) as pdf:
        all_lines = []
        for page_num, page in enumerate(pdf.pages, 1):
            words = page.extract_words(extra_attrs=["size", "fontname", "x0", "x1", "top", "bottom"])
            for w in words:
                w['page_num'] = page_num
            all_lines.extend(extract_lines(words))

    title = merge_multiline_title(all_lines)
    if is_form_pdf(all_lines):
        outline = []
    else:
        outline = extract_headings(all_lines)
    output = {
        "title": title,
        "outline": outline
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    pdfs = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith(".pdf")]
    for fname in pdfs:
        in_path = os.path.join(INPUT_DIR, fname)
        out_path = os.path.join(OUTPUT_DIR, Path(fname).stem + ".json")
        process_pdf(in_path, out_path)

if __name__ == "__main__":
    main()
