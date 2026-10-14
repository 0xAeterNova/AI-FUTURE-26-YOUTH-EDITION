"""Opt-in, fully local speech in/out. Runs ASR on CPU to protect Ollama GPU VRAM."""
from __future__ import annotations
import platform
import subprocess
import tempfile
import wave
from pathlib import Path


def record_and_transcribe(seconds: int = 6, model_name: str = 'small', language: str = 'ar') -> dict:
    try:
        import sounddevice as sd
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise RuntimeError('Optional voice dependencies missing: pip install -e ".[voice]"') from e
    # Never allocate CUDA VRAM for optional speech during judge evaluation.
    rate = 16000
    frames = sd.rec(int(seconds * rate), samplerate=rate, channels=1, dtype='int16')
    sd.wait()
    with tempfile.TemporaryDirectory(prefix='burhan_audio_') as temp:
        wavfile = Path(temp) / 'query.wav'
        with wave.open(str(wavfile), 'wb') as out:
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(rate)
            out.writeframes(frames.tobytes())
        model = WhisperModel(model_name, device='cpu', compute_type='int8')
        segments, info = model.transcribe(str(wavfile), language=language, beam_size=5,
                                          initial_prompt='خدمات حكومية، رسوم، وثائق، هوية، شهادة، تجديد، طلب، استثناء')
        result = list(segments)
    transcript = ' '.join(s.text.strip() for s in result).strip()
    return {'text': transcript, 'language': info.language,
            'avg_logprob': round(sum(s.avg_logprob for s in result)/len(result), 3) if result else None}


def speak_windows(text: str) -> bool:
    """System.Speech voice, no network. Arabic voice depends on installed Windows voices."""
    if platform.system() != 'Windows':
        return False
    # Send text by standard input, not interpolated PowerShell command strings.
    cmd = '[Console]::InputEncoding=[System.Text.Encoding]::UTF8; Add-Type -AssemblyName System.Speech; ' \
          '$v=New-Object System.Speech.Synthesis.SpeechSynthesizer; ' \
          '$voices=@($v.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -like "ar-*" }); ' \
          'if($voices.Count -eq 0){ exit 4 }; ' \
          '$v.SelectVoice($voices[0].VoiceInfo.Name); ' \
          '$msg=[Console]::In.ReadToEnd(); $v.Speak($msg)'
    try:
        r = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', cmd],
                           input=text, text=True, capture_output=True, timeout=120, encoding='utf-8')
        return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False
