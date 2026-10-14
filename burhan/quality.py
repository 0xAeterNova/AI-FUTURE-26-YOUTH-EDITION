"""Auditable Arabic extraction. Original physical PDF pages are always canonical."""
from __future__ import annotations
import re
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from .arabic import normalize, digits_in

ARABIC = re.compile(r'[\u0621-\u064a]')


def quality(text: str) -> dict:
    s = text or ''
    printable = sum(ch.isprintable() or ch in '\r\n\t' for ch in s)
    total = len(s)
    arabic = len(ARABIC.findall(s))
    bad = s.count('\ufffd') + s.count('\x00')
    suspicious = total < 80 or (bad > max(2, total * .01)) or (total > 200 and arabic < 5 and not re.search(r'[A-Za-z]{10}', s))
    return {'characters': total, 'arabic_characters': arabic,
            'printable_ratio': round(printable / max(total, 1), 3),
            'replacement_chars': bad, 'suspicious': suspicious}


def tesseract_cmd() -> str | None:
    if os.environ.get('BURHAN_TESSERACT') and Path(os.environ['BURHAN_TESSERACT']).exists():
        return os.environ['BURHAN_TESSERACT']
    return shutil.which('tesseract') or (str(Path(r'C:\Program Files\Tesseract-OCR\tesseract.exe'))
                                      if Path(r'C:\Program Files\Tesseract-OCR\tesseract.exe').is_file() else None)


def ocr_pdf_page(page, lang: str = 'ara+eng') -> str:
    """OCR only the indicated page. Requires Tesseract and ara language files."""
    exe = tesseract_cmd()
    if not exe:
        raise RuntimeError('Tesseract is not installed; OCR unavailable')
    with tempfile.TemporaryDirectory(prefix='burhan_ocr_') as d:
        path = Path(d) / 'page.png'
        page.get_pixmap(matrix=__import__('pymupdf').Matrix(2.0, 2.0), alpha=False).save(str(path))
        call = subprocess.run([exe, str(path), 'stdout', '-l', lang, '--psm', '3'],
                              capture_output=True, timeout=90)
        if call.returncode:
            raise RuntimeError(call.stderr.decode('utf-8', errors='replace')[-500:])
        return call.stdout.decode('utf-8', errors='replace').strip()


def markitdown_text(path: Path) -> tuple[str, str]:
    """Use installed Microsoft MarkItDown locally; no remote OCR/LLM calls."""
    try:
        from markitdown import MarkItDown
        converted = MarkItDown(enable_plugins=False).convert(str(path))
        return (getattr(converted, 'markdown', None) or getattr(converted, 'text_content', '') or '', '')
    except Exception as e:
        return ('', f'MarkItDown unavailable/failed: {type(e).__name__}: {e}')


def extract_pdf_with_audit(path: Path, ocr: str = 'auto', use_markitdown: bool = True) -> tuple[list[str], list[dict], list[str]]:
    try:
        import pymupdf
    except ImportError as e:
        raise RuntimeError('Install PDF support: pip install -e ".[documents]"') from e
    result, reports, warnings = [], [], []
    with pymupdf.open(str(path)) as pdf:
        for i, p in enumerate(pdf, 1):
            canonical = p.get_text('text', sort=True).strip()
            before = quality(canonical)
            how = 'pymupdf'
            if ocr == 'always' or (ocr == 'auto' and before['suspicious']):
                try:
                    ocr_text = ocr_pdf_page(p)
                    q_ocr = quality(ocr_text)
                    if q_ocr['characters'] >= 80 and (before['suspicious'] or ocr == 'always'):
                        canonical, how = ocr_text, 'tesseract-ocr'
                    else:
                        warnings.append(f'{path.name} page {i}: OCR produced insufficient text; manually inspect scan')
                except Exception as e:
                    warnings.append(f'{path.name} page {i}: OCR unavailable/failed: {e}')
            q = quality(canonical)
            reports.append({'page': i, 'method': how, 'quality': q, 'original_quality': before})
            if q['suspicious']:
                warnings.append(f'{path.name} page {i}: low-quality text: {q}; VERIFY ORIGINAL')
            result.append(canonical)
    if use_markitdown:
        md, err = markitdown_text(path)
        if err:
            warnings.append(f'{path.name}: {err}')
        elif md:
            raw_nums, md_nums = digits_in('\n'.join(result)), digits_in(md)
            # Cross-tool mismatch is a review signal, not grounds to overwrite reliable page text.
            if raw_nums and (raw_nums - md_nums):
                warnings.append(f'{path.name}: numeric values differ from MarkItDown: {sorted(raw_nums - md_nums)[:12]}')
            reports.append({'method': 'markitdown-crosscheck', 'characters': len(md),
                            'canonical_numbers_not_in_markdown': sorted(raw_nums - md_nums)[:20]})
    return result, reports, warnings


def extract_with_audit(path: Path, ocr: str = 'auto', use_markitdown: bool = True):
    if path.suffix.lower() == '.pdf':
        return extract_pdf_with_audit(path, ocr, use_markitdown)
    from .documents import extract
    pages = extract(path)
    reports = [{'page': i, 'method': 'native', 'quality': quality(s)} for i, s in enumerate(pages, 1)]
    warnings = [f'{path.name} page {r["page"]}: suspicious extraction quality' for r in reports if r['quality']['suspicious']]
    if use_markitdown and path.suffix.lower() == '.docx':
        md, err = markitdown_text(path)
        if md and len(md.strip()) > len(pages[0].strip()) and len(pages[0]) < 160:
            pages = [md]  # logical page; DOCX physical page references are unavailable
            reports[0]['method'] = 'markitdown-docx'
        elif err:
            warnings.append(f'{path.name}: {err}')
    return pages, reports, warnings
