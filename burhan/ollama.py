"""Direct HTTP connection to LOCAL Ollama; no API keys or cloud traffic."""
from __future__ import annotations
import json
import os
import urllib.error
import urllib.request
from urllib.parse import urlparse
from typing import Any

SCHEMA = {
    'type': 'object',
    'properties': {
        'status': {'type': 'string', 'enum': ['answered', 'insufficient', 'clarification']},
        'answer': {'type': 'string'},
        'citations': {'type': 'array', 'items': {'type': 'string'}},
        'evidence_quotes': {'type': 'array', 'items': {'type': 'string'}},
    },
    'required': ['status', 'answer', 'citations'],
}

class OllamaClient:
    def __init__(self, model: str, base_url: str | None = None, context_tokens: int = 4096,
                 timeout: int = 180, think: bool | None = False, num_predict: int = 400):
        if not model:
            raise ValueError('Set BURHAN_MODEL to EXACT organizers\' Ollama model name.')
        self.model = model
        self.url = (base_url or os.environ.get('OLLAMA_HOST', 'http://localhost:11434')).rstrip('/')
        parsed = urlparse(self.url)
        if parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', 'localhost', '::1') or parsed.username:
            raise ValueError('BURHAN permits local HTTP Ollama endpoint only.')
        self.context_tokens = context_tokens
        self.timeout = timeout
        self.think = think
        self.num_predict = num_predict
        self.last_stats: dict[str, Any] = {}

    def _request(self, path: str, payload: dict | None = None) -> Any:
        data = json.dumps(payload, ensure_ascii=False).encode('utf-8') if payload is not None else None
        req = urllib.request.Request(self.url + path, data=data, headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.loads(r.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            detail = e.read().decode('utf-8', errors='replace')[:500]
            raise RuntimeError(f'Ollama HTTP {e.code}: {detail}') from e
        except urllib.error.URLError as e:
            raise RuntimeError(f'Ollama not reachable at {self.url}: {e}') from e

    def installed_models(self) -> list[str]:
        return [row.get('name', '') for row in self._request('/api/tags').get('models', [])]

    def chat(self, system: str, user: str, schema: bool = True) -> dict[str, Any]:
        payload = {
            'model': self.model,
            'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}],
            'stream': False, 'keep_alive': '30m',
            'options': {'temperature': 0, 'num_ctx': self.context_tokens, 'num_predict': self.num_predict},
        }
        if self.think is not None:
            payload['think'] = self.think
        if schema:
            payload['format'] = SCHEMA
        try:
            answer = self._request('/api/chat', payload)
        except RuntimeError as e:
            # Older model variants may not support think or schema. One compatibility retry.
            if 'HTTP 400' not in str(e):
                raise
            payload.pop('think', None)
            if schema:
                payload['format'] = 'json'
            answer = self._request('/api/chat', payload)
        self.last_stats = {k: answer.get(k) for k in ('total_duration', 'load_duration', 'prompt_eval_count',
                            'prompt_eval_duration', 'eval_count', 'eval_duration') if k in answer}
        content = answer.get('message', {}).get('content', '')
        try:
            obj = json.loads(content)
        except (TypeError, json.JSONDecodeError):
            return {'status': 'invalid', 'answer': 'تعذر التحقق من صيغة إجابة النموذج.', 'citations': [], 'raw': content}
        if not isinstance(obj, dict) or not all(k in obj for k in ('status', 'answer', 'citations')):
            return {'status': 'invalid', 'answer': 'تعذر التحقق من صيغة إجابة النموذج.', 'citations': [], 'raw': content}
        return obj
