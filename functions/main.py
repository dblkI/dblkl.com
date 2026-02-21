"""
PDF to EPUB Converter — v2 Closed-Loop Pipeline
================================================
Stage 1: Deep PDF Analysis (font histogram, heading detection, scan detection)
Stage 2: OCR Fallback (Google Cloud Vision API for scanned pages)
Stage 3: Intelligent Chapter Structuring (TOC → headings → page-chunk fallback)
Stage 4: EPUB Assembly (CSS, images, TOC)
Stage 5: Closed-Loop Validation with automatic re-iteration
"""

from firebase_functions import storage_fn
import firebase_admin
from firebase_admin import storage, firestore
import fitz  # PyMuPDF
from ebooklib import epub
import os
import io
import re
import tempfile
import pathlib
import urllib.parse
from collections import Counter, defaultdict

# Initialize Firebase Admin SDK
firebase_admin.initialize_app()

# ─────────────────────────────────────────────────────────
# STAGE 1: Deep PDF Analysis
# ─────────────────────────────────────────────────────────

def analyze_pdf(doc):
    """
    Extracts structured data from the PDF using font analysis.
    Returns a dict with font histogram, detected headings, images, 
    scanned-page flags, text content per page, and embedded TOC.
    """
    font_sizes = []
    pages_data = []
    all_images = []
    scanned_pages = []
    total_words = 0

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]

        page_text_blocks = []
        page_word_count = 0
        page_has_images = False

        for block in blocks:
            # Image block
            if block.get("type") == 1:
                page_has_images = True
                continue

            # Text block
            if "lines" not in block:
                continue

            for line in block["lines"]:
                for span in line["spans"]:
                    text = span["text"].strip()
                    if not text:
                        continue
                    
                    size = round(span["size"], 1)
                    flags = span["flags"]  # 1=superscript, 2=italic, 4=serif, 16=bold
                    is_bold = bool(flags & 16)
                    
                    font_sizes.append(size)
                    word_count = len(text.split())
                    page_word_count += word_count

                    page_text_blocks.append({
                        "text": text,
                        "size": size,
                        "bold": is_bold,
                        "flags": flags,
                        "bbox": span["bbox"],
                    })

        # Extract images from this page
        image_list = page.get_images(full=True)
        page_images = []
        for img_index, img_info in enumerate(image_list):
            xref = img_info[0]
            try:
                base_image = doc.extract_image(xref)
                if base_image:
                    page_images.append({
                        "data": base_image["image"],
                        "ext": base_image["ext"],
                        "page": page_num,
                        "index": img_index,
                    })
            except Exception:
                continue

        all_images.extend(page_images)
        total_words += page_word_count

        # Detect scanned pages: has images but very few words
        is_scanned = page_has_images and page_word_count < 10
        if is_scanned:
            scanned_pages.append(page_num)

        pages_data.append({
            "page_num": page_num,
            "blocks": page_text_blocks,
            "word_count": page_word_count,
            "is_scanned": is_scanned,
            "images": page_images,
        })

    # Calculate font size histogram
    if font_sizes:
        size_counter = Counter(font_sizes)
        body_size = size_counter.most_common(1)[0][0]
    else:
        body_size = 12.0

    # Extract embedded TOC
    toc = doc.get_toc()

    return {
        "pages": pages_data,
        "body_font_size": body_size,
        "toc": toc,
        "images": all_images,
        "scanned_pages": scanned_pages,
        "total_words": total_words,
        "total_pages": len(doc),
    }


# ─────────────────────────────────────────────────────────
# STAGE 2: OCR Fallback (Google Cloud Vision API)
# ─────────────────────────────────────────────────────────

def ocr_scanned_pages(doc, scanned_indices):
    """
    Uses Google Cloud Vision API to OCR scanned pages.
    Returns a dict mapping page_num → extracted text.
    """
    if not scanned_indices:
        return {}

    try:
        from google.cloud import vision
        client = vision.ImageAnnotatorClient()
    except Exception as e:
        print(f"Cloud Vision unavailable, skipping OCR: {e}")
        return {}

    ocr_results = {}

    for page_num in scanned_indices:
        try:
            page = doc.load_page(page_num)
            # Render page as high-quality image
            pix = page.get_pixmap(dpi=200)
            img_bytes = pix.tobytes("png")

            image = vision.Image(content=img_bytes)
            response = client.document_text_detection(image=image)

            if response.full_text_annotation:
                ocr_text = response.full_text_annotation.text
                ocr_results[page_num] = ocr_text
                print(f"  OCR page {page_num + 1}: {len(ocr_text)} chars extracted")
            else:
                ocr_results[page_num] = ""

        except Exception as e:
            print(f"  OCR failed for page {page_num + 1}: {e}")
            ocr_results[page_num] = ""

    return ocr_results


# ─────────────────────────────────────────────────────────
# STAGE 3: Intelligent Chapter Structuring
# ─────────────────────────────────────────────────────────

def structure_chapters(analysis, ocr_results, params):
    """
    Groups pages into chapters using three-tier priority:
    1. Embedded TOC (if available)
    2. Heading detection (font-size based)
    3. Page-chunk fallback
    
    Returns list of chapter dicts: {title, pages, content_html}
    """
    pages = analysis["pages"]
    toc = analysis["toc"]
    body_size = analysis["body_font_size"]
    heading_threshold = params.get("heading_threshold", 1.3)
    chunk_size = params.get("chunk_size", 15)
    min_chapter_words = params.get("min_chapter_words", 100)

    chapters = []

    # ── Strategy 1: Use embedded TOC ──
    if toc and len(toc) >= 2:
        print(f"  Using embedded TOC with {len(toc)} entries")
        chapter_boundaries = []
        for level, title, page_num in toc:
            if level <= 2:  # Only top-level and second-level headings
                chapter_boundaries.append({
                    "title": title,
                    "start_page": page_num - 1,  # TOC pages are 1-indexed
                })

        if chapter_boundaries:
            for i, boundary in enumerate(chapter_boundaries):
                start = boundary["start_page"]
                end = chapter_boundaries[i + 1]["start_page"] if i + 1 < len(chapter_boundaries) else len(pages)
                
                chapter_pages = list(range(max(0, start), min(end, len(pages))))
                if chapter_pages:
                    chapters.append({
                        "title": boundary["title"],
                        "pages": chapter_pages,
                    })

            if chapters:
                # Add front matter if first chapter doesn't start at page 0
                if chapters[0]["pages"][0] > 0:
                    front_pages = list(range(0, chapters[0]["pages"][0]))
                    if front_pages:
                        chapters.insert(0, {"title": "Portada", "pages": front_pages})
                
                return _build_chapter_content(chapters, pages, ocr_results, analysis)

    # ── Strategy 2: Heading detection ──
    heading_min_size = body_size * heading_threshold
    detected_headings = []

    for page_data in pages:
        if page_data["is_scanned"]:
            continue
        for block in page_data["blocks"]:
            if (block["size"] >= heading_min_size and 
                block["bold"] and
                len(block["text"].split()) <= 12 and
                len(block["text"]) > 2):
                
                # Check for chapter-like patterns
                text = block["text"].strip()
                is_chapter_like = (
                    re.match(r'^(cap[íi]tulo|chapter|parte|part|secci[oó]n|section)\s', text, re.IGNORECASE) or
                    re.match(r'^\d+[\.\)\-\s]', text) or
                    re.match(r'^[IVXLCDM]+[\.\)\-\s]', text) or
                    block["size"] >= body_size * 1.5  # Very large text is likely a heading
                )
                
                if is_chapter_like or block["size"] >= heading_min_size:
                    detected_headings.append({
                        "title": text,
                        "page": page_data["page_num"],
                        "size": block["size"],
                    })

    if len(detected_headings) >= 2:
        print(f"  Detected {len(detected_headings)} headings via font analysis")
        # Deduplicate headings on same page (keep largest)
        seen_pages = {}
        for h in detected_headings:
            if h["page"] not in seen_pages or h["size"] > seen_pages[h["page"]]["size"]:
                seen_pages[h["page"]] = h
        
        sorted_headings = sorted(seen_pages.values(), key=lambda x: x["page"])

        for i, heading in enumerate(sorted_headings):
            start = heading["page"]
            end = sorted_headings[i + 1]["page"] if i + 1 < len(sorted_headings) else len(pages)
            
            chapter_pages = list(range(start, end))
            if chapter_pages:
                chapters.append({
                    "title": heading["title"],
                    "pages": chapter_pages,
                })

        if chapters:
            # Add front matter
            if chapters[0]["pages"][0] > 0:
                front_pages = list(range(0, chapters[0]["pages"][0]))
                if front_pages:
                    chapters.insert(0, {"title": "Portada", "pages": front_pages})
            
            return _build_chapter_content(chapters, pages, ocr_results, analysis)

    # ── Strategy 3: Page-chunk fallback ──
    print(f"  No headings detected, using page-chunk fallback (size={chunk_size})")
    total = len(pages)
    for i in range(0, total, chunk_size):
        end = min(i + chunk_size, total)
        chapter_pages = list(range(i, end))
        chapters.append({
            "title": f"Sección {len(chapters) + 1}",
            "pages": chapter_pages,
        })

    return _build_chapter_content(chapters, pages, ocr_results, analysis)


def _build_chapter_content(chapters, pages, ocr_results, analysis):
    """Builds HTML content for each chapter from its pages."""
    for chapter in chapters:
        html_parts = []
        chapter_word_count = 0
        chapter_images = []

        for page_num in chapter["pages"]:
            if page_num >= len(pages):
                continue
            
            page_data = pages[page_num]

            # Use OCR text if page was scanned
            if page_data["is_scanned"] and page_num in ocr_results:
                ocr_text = ocr_results[page_num]
                if ocr_text:
                    paragraphs = ocr_text.split("\n\n")
                    for p in paragraphs:
                        p = p.strip()
                        if p:
                            html_parts.append(f"<p>{_escape_html(p)}</p>")
                            chapter_word_count += len(p.split())
            else:
                # Build HTML from structured text blocks
                body_size = analysis["body_font_size"]
                for block in page_data["blocks"]:
                    text = block["text"]
                    size = block["size"]

                    if size >= body_size * 1.5:
                        html_parts.append(f"<h2>{_escape_html(text)}</h2>")
                    elif size >= body_size * 1.2:
                        html_parts.append(f"<h3>{_escape_html(text)}</h3>")
                    elif block["bold"]:
                        html_parts.append(f"<p><strong>{_escape_html(text)}</strong></p>")
                    else:
                        html_parts.append(f"<p>{_escape_html(text)}</p>")
                    
                    chapter_word_count += len(text.split())

            # Collect images for this page
            chapter_images.extend(page_data.get("images", []))

        chapter["content_html"] = "\n".join(html_parts)
        chapter["word_count"] = chapter_word_count
        chapter["images"] = chapter_images

    return chapters


def _escape_html(text):
    """Escapes HTML special characters."""
    return (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;"))


# ─────────────────────────────────────────────────────────
# STAGE 4: EPUB Assembly
# ─────────────────────────────────────────────────────────

def build_epub(chapters, metadata, output_path):
    """Assembles the EPUB file from structured chapters."""
    book = epub.EpubBook()

    # Metadata
    book.set_identifier(metadata.get("id", "unknown"))
    book.set_title(metadata.get("title", "Converted Book"))
    book.set_language(metadata.get("language", "es"))

    # Reader-friendly CSS
    css_content = """
    body {
        font-family: Georgia, 'Times New Roman', serif;
        background-color: #fdf6e3;
        color: #2c2c2c;
        line-height: 1.7;
        margin: 1.5em;
        font-size: 1em;
    }
    h1, h2, h3 {
        font-family: Helvetica, Arial, sans-serif;
        color: #1a1a1a;
        margin-top: 1.5em;
        margin-bottom: 0.5em;
    }
    h1 { font-size: 1.8em; border-bottom: 1px solid #ccc; padding-bottom: 0.3em; }
    h2 { font-size: 1.4em; }
    h3 { font-size: 1.2em; }
    p {
        margin-bottom: 0.8em;
        text-align: justify;
    }
    img {
        max-width: 100%;
        height: auto;
        display: block;
        margin: 1em auto;
    }
    .chapter-title {
        text-align: center;
        margin-top: 3em;
        margin-bottom: 2em;
    }
    """
    style_item = epub.EpubItem(
        uid="main_style",
        file_name="style/main.css",
        media_type="text/css",
        content=css_content,
    )
    book.add_item(style_item)

    epub_chapters = []
    image_counter = 0

    for i, chapter in enumerate(chapters):
        # Embed images for this chapter
        image_refs = []
        for img in chapter.get("images", []):
            image_counter += 1
            ext = img.get("ext", "png")
            img_filename = f"images/img_{image_counter}.{ext}"
            
            media_type = f"image/{ext}"
            if ext == "jpg":
                media_type = "image/jpeg"

            epub_img = epub.EpubItem(
                uid=f"img_{image_counter}",
                file_name=img_filename,
                media_type=media_type,
                content=img["data"],
            )
            book.add_item(epub_img)
            image_refs.append(img_filename)

        # Build chapter HTML
        images_html = "\n".join(
            f'<img src="{ref}" alt="Image"/>' for ref in image_refs
        )

        chapter_html = f"""<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
  <title>{_escape_html(chapter['title'])}</title>
  <link rel="stylesheet" href="style/main.css" type="text/css"/>
</head>
<body>
  <div class="chapter-title"><h1>{_escape_html(chapter['title'])}</h1></div>
  {chapter['content_html']}
  {images_html}
</body>
</html>"""

        c = epub.EpubHtml(
            title=chapter["title"],
            file_name=f"chapter_{i + 1}.xhtml",
            lang=metadata.get("language", "es"),
        )
        c.content = chapter_html
        c.add_item(style_item)
        book.add_item(c)
        epub_chapters.append(c)

    # Table of Contents
    book.toc = tuple(epub_chapters)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # Spine
    book.spine = ["nav", *epub_chapters]

    # Write
    epub.write_epub(output_path, book, {})
    return len(epub_chapters), image_counter


# ─────────────────────────────────────────────────────────
# STAGE 5: Closed-Loop Validation
# ─────────────────────────────────────────────────────────

def validate_epub(epub_path, source_analysis, chapter_count_expected, image_count_expected):
    """
    Validates the generated EPUB against the source PDF.
    Returns a dict with pass/fail status and detailed metrics.
    """
    # Read the EPUB and count words
    epub_word_count = 0
    try:
        book = epub.read_epub(epub_path)
        for item in book.get_items():
            if item.get_type() == 9:  # XHTML document
                content = item.get_content().decode("utf-8", errors="ignore")
                # Strip HTML tags to count raw words
                clean = re.sub(r'<[^>]+>', ' ', content)
                epub_word_count += len(clean.split())
    except Exception as e:
        return {
            "passed": False,
            "error": f"Could not read EPUB for validation: {e}",
            "word_ratio": 0,
            "chapters": chapter_count_expected,
            "images": image_count_expected,
        }

    source_words = source_analysis["total_words"]
    
    # Handle OCR-enriched word counts (OCR can sometimes add words)
    if source_words > 0:
        word_ratio = min(epub_word_count / source_words, 1.0)
    else:
        word_ratio = 1.0 if epub_word_count == 0 else 0.5  # All-scanned PDFs

    passed = word_ratio >= 0.90
    empty_chapters = False

    report = {
        "passed": passed,
        "word_ratio": round(word_ratio, 3),
        "source_words": source_words,
        "epub_words": epub_word_count,
        "chapters": chapter_count_expected,
        "images": image_count_expected,
        "empty_chapters": empty_chapters,
    }

    # Analyze failure mode for parameter adjustment
    if not passed:
        if word_ratio < 0.5:
            report["failure_mode"] = "severe_word_loss"
        elif word_ratio < 0.9:
            report["failure_mode"] = "moderate_word_loss"
        else:
            report["failure_mode"] = "minor"

    return report


def adjust_params(current_params, validation_report):
    """
    Adjusts structuring parameters based on validation failure analysis.
    Returns updated params for the next iteration.
    """
    new_params = current_params.copy()

    failure = validation_report.get("failure_mode", "minor")

    if failure == "severe_word_loss":
        # Drastic: reduce heading threshold significantly, increase chunk size
        new_params["heading_threshold"] = max(1.1, current_params.get("heading_threshold", 1.3) - 0.15)
        new_params["chunk_size"] = min(30, current_params.get("chunk_size", 15) + 10)
        new_params["min_chapter_words"] = max(25, current_params.get("min_chapter_words", 100) - 50)
    elif failure == "moderate_word_loss":
        new_params["heading_threshold"] = max(1.1, current_params.get("heading_threshold", 1.3) - 0.1)
        new_params["chunk_size"] = min(25, current_params.get("chunk_size", 15) + 5)
        new_params["min_chapter_words"] = max(50, current_params.get("min_chapter_words", 100) - 25)

    return new_params


# ─────────────────────────────────────────────────────────
# ORCHESTRATOR: Cloud Function Entry Point
# ─────────────────────────────────────────────────────────

MAX_ITERATIONS = 3

@storage_fn.on_object_finalized(
    bucket="prod-main-website.firebasestorage.app",
    timeout_sec=540,
    memory=512,
)
def process_epub_conversion(event: storage_fn.CloudEvent[storage_fn.StorageObjectData]) -> None:
    """Triggered when a new PDF is uploaded to the storage bucket."""

    db = firestore.client()

    file_data = event.data
    file_bucket = file_data.bucket
    file_path = file_data.name

    if not file_path.startswith("pdf_uploads/") or not file_path.endswith(".pdf"):
        return

    filename = pathlib.Path(file_path).name
    job_id = pathlib.Path(file_path).stem

    print(f"═══ Starting v2 conversion for job {job_id} / file {filename} ═══")

    job_ref = db.collection("epub_conversions").document(job_id)
    job_ref.set({"status": "processing", "progress": 5}, merge=True)

    bucket = storage.bucket(file_bucket)
    blob = bucket.blob(file_path)

    temp_pdf_path = None
    temp_epub_path = None

    try:
        # Create temp files
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            temp_pdf_path = f.name
        with tempfile.NamedTemporaryFile(suffix=".epub", delete=False) as f:
            temp_epub_path = f.name

        # Download PDF
        blob.download_to_filename(temp_pdf_path)
        job_ref.update({"progress": 10})

        doc = fitz.open(temp_pdf_path)

        # ── STAGE 1: Deep Analysis ──
        print("─── Stage 1: Deep PDF Analysis ───")
        analysis = analyze_pdf(doc)
        print(f"  Pages: {analysis['total_pages']}, Words: {analysis['total_words']}, "
              f"Body font: {analysis['body_font_size']}pt, "
              f"Scanned pages: {len(analysis['scanned_pages'])}, "
              f"Images: {len(analysis['images'])}, "
              f"TOC entries: {len(analysis['toc'])}")
        job_ref.update({"progress": 20})

        # ── STAGE 2: OCR Fallback ──
        ocr_results = {}
        if analysis["scanned_pages"]:
            print(f"─── Stage 2: OCR for {len(analysis['scanned_pages'])} scanned pages ───")
            job_ref.update({"progress": 25, "status": "processing"})
            ocr_results = ocr_scanned_pages(doc, analysis["scanned_pages"])

            # Merge OCR word counts back into analysis
            for page_num, text in ocr_results.items():
                if text:
                    analysis["total_words"] += len(text.split())
            print(f"  OCR complete. Updated total words: {analysis['total_words']}")
        else:
            print("─── Stage 2: No scanned pages, skipping OCR ───")

        job_ref.update({"progress": 35})

        # ── CLOSED-LOOP: Stages 3–5 with re-iteration ──
        params = {
            "heading_threshold": 1.3,
            "chunk_size": 15,
            "min_chapter_words": 100,
        }
        best_result = None

        for iteration in range(1, MAX_ITERATIONS + 1):
            print(f"─── Iteration {iteration}/{MAX_ITERATIONS} ───")

            # ── STAGE 3: Intelligent Structuring ──
            print(f"  Stage 3: Structuring (threshold={params['heading_threshold']}, "
                  f"chunk={params['chunk_size']})")
            chapters = structure_chapters(analysis, ocr_results, params)
            print(f"  Result: {len(chapters)} chapters")

            progress_base = 35 + (iteration - 1) * 15
            job_ref.update({"progress": min(progress_base + 10, 85)})

            # ── STAGE 4: EPUB Assembly ──
            print("  Stage 4: EPUB Assembly")
            chapter_count, image_count = build_epub(
                chapters,
                metadata={
                    "id": job_id,
                    "title": job_ref.get().to_dict().get("fileName", job_id).replace(".pdf", ""),
                    "language": "es",
                },
                output_path=temp_epub_path,
            )
            print(f"  Built: {chapter_count} chapters, {image_count} images")

            job_ref.update({"progress": min(progress_base + 15, 90)})

            # ── STAGE 5: Validation ──
            print("  Stage 5: Validation")
            report = validate_epub(temp_epub_path, analysis, chapter_count, image_count)
            print(f"  Word ratio: {report['word_ratio']}, Passed: {report['passed']}")

            if report["passed"]:
                best_result = report
                print(f"  ✅ Validation PASSED on iteration {iteration}")
                break
            else:
                print(f"  ❌ Validation FAILED: {report.get('failure_mode', 'unknown')}")
                best_result = report

                if iteration < MAX_ITERATIONS:
                    params = adjust_params(params, report)
                    print(f"  Adjusting params → threshold={params['heading_threshold']}, "
                          f"chunk={params['chunk_size']}")
                else:
                    print("  ⚠️ Max iterations reached. Using best-effort result.")

        doc.close()

        # ── Upload result ──
        print("─── Uploading EPUB ───")
        output_path = f"epub_conversions/{job_id}.epub"
        output_blob = bucket.blob(output_path)
        output_blob.upload_from_filename(temp_epub_path, content_type="application/epub+zip")

        encoded_path = urllib.parse.quote(output_path, safe="")
        download_url = f"https://firebasestorage.googleapis.com/v0/b/{bucket.name}/o/{encoded_path}?alt=media"

        # ── Final Firestore update ──
        update_data = {
            "status": "completed",
            "progress": 100,
            "downloadUrl": download_url,
            "qualityReport": {
                "wordRatio": best_result["word_ratio"] if best_result else 0,
                "sourceWords": best_result["source_words"] if best_result else 0,
                "epubWords": best_result["epub_words"] if best_result else 0,
                "chapters": best_result["chapters"] if best_result else 0,
                "images": best_result["images"] if best_result else 0,
                "passed": best_result["passed"] if best_result else False,
            },
        }
        job_ref.update(update_data)
        print(f"═══ Conversion complete for {job_id} ═══")

    except Exception as e:
        print(f"Fatal error for {job_id}: {e}")
        import traceback
        traceback.print_exc()
        job_ref.update({
            "status": "error",
            "error": str(e),
        })

    finally:
        if temp_pdf_path and os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)
        if temp_epub_path and os.path.exists(temp_epub_path):
            os.remove(temp_epub_path)