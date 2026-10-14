import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from burhan.arabic import tokens
from burhan.documents import index_folder
from burhan.quality import quality, markitdown_text
from burhan.ledger import candidate_facts, potential_conflicts, relevant_conflicts
from burhan.ollama import OllamaClient
from burhan.doctor import doctor
from burhan.engine import Engine


class ExtraAccuracyTests(unittest.TestCase):
    def test_dialect_expands_cost(self):
        words = tokens('قديش بتكلف المعاملة؟', expand=True)
        self.assertIn('رسوم', words)

    def test_arabic_digits_values_are_canonical(self):
        source = {'documents': [{'id': 'D01', 'title': 'خدمة أ', 'file': 'a.txt',
                                 'pages': [{'id': 'D01-P1', 'number': 1, 'text': 'رسوم الطلب ٥ دنانير\nالعمر ١٨ عاما'}]}]}
        vals = candidate_facts(source)
        self.assertEqual(vals[0]['field'], 'fee')
        self.assertEqual(vals[0]['values'], ['5'])
        self.assertEqual(vals[1]['field'], 'age')
        self.assertEqual(vals[1]['values'], ['18'])

    def test_age_exemption_not_fee(self):
        idx = {'documents': [{'id': 'D01', 'title': 'تسجيل', 'file': 'a.txt',
                             'pages': [{'id': 'D01-P1', 'number': 1, 'text': 'الأطفال دون عمر 18 معفيون من الرسوم'}]}]}
        self.assertEqual(candidate_facts(idx)[0]['field'], 'age')

    def test_potential_conflict_same_service_not_confirmed(self):
        idx = {'documents': [
          {'id': 'D01', 'title': 'إصدار بطاقة', 'file': 'a.txt', 'pages': [{'id': 'D01-P1', 'number': 1, 'text': 'رسوم الإصدار 5 دنانير'}]},
          {'id': 'D02', 'title': 'إصدار بطاقة', 'file': 'b.txt', 'pages': [{'id': 'D02-P1', 'number': 1, 'text': 'رسوم الإصدار 7 دنانير'}]}
        ]}
        facts = candidate_facts(idx)
        alerts = potential_conflicts(facts)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]['status'], 'potential_conflict_needs_review')
        self.assertEqual([alerts[0]['a']['values'], alerts[0]['b']['values']], [['5'], ['7']])
        idx['ledger'] = {'potential_conflicts': alerts}
        self.assertEqual(len(relevant_conflicts(idx, 'كم الرسوم؟', {'D01-P1', 'D02-P1'})), 1)
        self.assertEqual(len(relevant_conflicts(idx, 'شو الأوراق؟', {'D01-P1'})), 0)

    def test_no_cross_service_conflict(self):
        facts = [{'service': n, 'field': 'fee', 'conditional': False, 'values': [v],
                  'source_id': f'D0{i}-P1', 'line': 1} for i, (n,v) in enumerate([('شهادة', '5'), ('ترخيص', '7')],1)]
        self.assertEqual(potential_conflicts(facts), [])

    def test_low_quality_warning(self):
        self.assertTrue(quality('')['suspicious'])
        self.assertFalse(quality('ما هي الأوراق المطلوبة لإصدار البطاقة؟ ' * 6)['suspicious'])

    def test_markitdown_absence_is_graceful(self):
        text, issue = markitdown_text(Path('does-not-exist.pdf'))
        self.assertFalse(text)
        self.assertTrue(issue)

    def test_ingest_and_ledger(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            (d/'service.txt').write_text('خدمة تصريح تجريبي\nالرسوم: 5 دنانير\n' + 'الوثائق المطلوبة: البطاقة الشخصية\n' * 5, encoding='utf-8')
            idx = index_folder(str(d), str(d/'idx.json'), ocr='off', use_markitdown=False)
            self.assertEqual(idx['ledger']['facts'][0]['values'], ['5'])
            self.assertEqual(idx['documents'][0]['pages'][0]['number'], 1)
            self.assertIn('extraction_reports', idx)

    def test_page_manifest_retains_source_page(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            (d/'merged.txt').write_text('بطاقة تجريبية رسومها 5 دنانير', encoding='utf-8')
            m = {'services': [{'file': 'merged.txt', 'title': 'بطاقة تجريبية', 'pages': [1]}]}
            (d/'manifest.json').write_text(json.dumps(m, ensure_ascii=False), encoding='utf-8')
            idx = index_folder(str(d), str(d/'i.json'), manifest=str(d/'manifest.json'), ocr='off', use_markitdown=False)
            self.assertEqual(idx['documents'][0]['pages'][0]['id'], 'D01-P1')

    def test_client_local_url_strict(self):
        for url in ('https://localhost:11434', 'http://attacker.example.org:11434'):
            with self.assertRaises(ValueError):
                OllamaClient('qwen3:8b', base_url=url)
        self.assertIsNotNone(OllamaClient('qwen3:8b', base_url='http://127.0.0.1:11434'))

    def test_ollama_stats_are_optional(self):
        cl = OllamaClient('qwen3:8b')
        with patch.object(cl, '_request', return_value={'message': {'content': json.dumps({'status':'answered','answer':'ok','citations':['D01-P1']})},
                                                        'eval_count': 25, 'total_duration': 3000000}):
            a=cl.chat('system','question')
        self.assertEqual(a['citations'], ['D01-P1'])
        self.assertEqual(cl.last_stats['eval_count'], 25)

    def test_citation_quote_validation(self):
        idx = {'version': 1,
               'documents': [{'id':'D01','title':'خدمة إصدار بطاقة','file':'file.txt',
                              'pages':[{'id':'D01-P1','number':1,'text':'رسوم البطاقة 5 دنانير والمطلوب هوية'}]}],
               'chunks':[{'id':'D01-P1-C1','page_id':'D01-P1','doc_id':'D01','text':'رسوم البطاقة 5 دنانير والمطلوب هوية'}]}
        class Fake:
            last_stats = {'eval_count': 10}
            def chat(self, system, user, schema=True):
                return {'status':'answered','answer':'الرسوم 5 دنانير',
                        'citations':['D01-P1'], 'evidence_quotes':['رسوم البطاقة 5 دنانير','غير موجود']}
        out=Engine(idx,ollama=Fake()).ask('كم رسوم خدمة إصدار بطاقة؟')
        self.assertEqual(out['status'], 'answered')
        self.assertEqual(out['verified_quotes'], ['رسوم البطاقة 5 دنانير'])
        self.assertEqual(out['rejected_quotes'], ['غير موجود'])

    def test_doctor_runs_without_ollama(self):
        out=doctor('http://127.0.0.1:9998')
        self.assertIn('dependencies', out)
        self.assertIn('ollama_models', out)


if __name__ == '__main__': unittest.main()
