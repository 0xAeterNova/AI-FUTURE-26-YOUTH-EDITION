"""Hardware, Python dependencies, optional services: safe and read-only."""
from __future__ import annotations
import importlib.util
import json
import platform
import shutil
import subprocess
import sys
import urllib.request
from .quality import tesseract_cmd


def doctor(url='http://localhost:11434') -> dict:
    details = {'os': platform.platform(), 'python': sys.version.split()[0],
               'arch': platform.machine(), 'dependencies': {}}
    for module in ('pymupdf', 'docx', 'markitdown', 'sounddevice', 'faster_whisper'):
        details['dependencies'][module] = importlib.util.find_spec(module) is not None
    gpu = shutil.which('nvidia-smi')
    if gpu:
        try:
            cmd = [gpu, '--query-gpu=name,memory.total,memory.free', '--format=csv,noheader']
            details['gpu'] = subprocess.check_output(cmd, text=True, timeout=8, errors='replace').strip()
        except Exception as e:
            details['gpu'] = str(e)
    else:
        details['gpu'] = 'nvidia-smi unavailable'
    details['tesseract'] = tesseract_cmd() or 'not found'
    if tesseract_cmd():
        try:
            r = subprocess.run([tesseract_cmd(), '--list-langs'], capture_output=True, timeout=10)
            details['ocr_arabic'] = 'ara' in r.stdout.decode(errors='replace') or 'ara' in r.stderr.decode(errors='replace')
        except Exception:
            details['ocr_arabic'] = False
    try:
        with urllib.request.urlopen(url.rstrip('/') + '/api/tags', timeout=3) as r:
            details['ollama_models'] = [row['name'] for row in json.load(r).get('models', [])]
    except Exception as e:
        details['ollama_models'] = []
        details['ollama_error'] = str(e)
    return details
