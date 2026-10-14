import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from burhan.arabic import normalize, tokens, digits_in
from burhan.documents import index_folder, split_chunks, load_index
from burhan.retrieve import Retriever
from burhan.engine import Engine
from burhan.evaluate import retrieval_report

class FakeOllama:
    def __init__(self, answer):
        self.answer = answer
        self.requests = []
    def chat(self, system, user, schema=True):
        self.requests.append((system, user, schema))
        return self.answer

class TestBurhan(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = TemporaryDirectory()
        cls.idx_file = str(Path(cls.tmp.name) / "index.json")
        cls.docs = index_folder(str(Path(__file__).parent.parent / "examples"), cls.idx_file)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_normalization(self):
        self.assertEqual(normalize('إصدار بِطاقة ٥ دنانير'), 'اصدار بطاقه 5 دنانير')
    def test_digits(self):
        self.assertEqual(digits_in('الرسوم ٥ دنانير'), {'5'})
    def test_tokens_clitics(self):
        self.assertIn('كتاب', tokens('والكتاب'))
    def test_index(self):
        self.assertEqual(len(self.docs['documents']), 3)
        self.assertEqual(load_index(self.idx_file)['documents'][0]['id'], 'D01')
    def test_pages(self):
        self.assertEqual(self.docs['documents'][0]['pages'][0]['id'], 'D01-P1')
    def test_chunks(self):
        self.assertTrue(split_chunks('أ' * 1200))
    def test_retrieval_title(self):
        r = Retriever(self.docs)
        ranked = r.rank_services('كم رسوم إصدار بطاقة المكتبة العامة؟', r.search('كم رسوم إصدار بطاقة المكتبة العامة؟'))
        self.assertEqual(ranked[0][0], 'D01')
    def test_retrieval_other_service(self):
        r = Retriever(self.docs)
        q = 'ما الأوراق اللازمة لتصريح الفعالية الثقافية؟'
        ranked = r.rank_services(q, r.search(q))
        self.assertEqual(ranked[0][0], 'D03')
    def test_retrieval_evaluation(self):
        gold = [json.loads(line) for line in (Path(__file__).parent.parent/'examples/gold.jsonl').read_text(encoding='utf8').splitlines()]
        report = retrieval_report(self.docs, gold)
        self.assertGreaterEqual(report['hit_at_2'], 0.8)
    def test_citation_validation(self):
        m = FakeOllama({'status':'answered','answer':'الرسوم 5 دنانير','citations':['D01-P1','D99-P1']})
        e = Engine(self.docs, ollama=m)
        answer = e.ask('كم رسوم بطاقة المكتبة العامة؟')
        self.assertEqual(answer['status'], 'answered')
        self.assertEqual(answer['citations'], ['D01-P1'])
        self.assertEqual(answer['invalid_citations'], ['D99-P1'])
    def test_fabricated_number_rejected(self):
        m = FakeOllama({'status':'answered','answer':'الرسوم 999 ديناراً','citations':['D01-P1']})
        answer = Engine(self.docs, ollama=m).ask('كم رسوم بطاقة المكتبة العامة؟')
        self.assertEqual(answer['status'], 'numeric_warning')
    def test_missing_citation_rejected(self):
        m = FakeOllama({'status':'answered','answer':'الرسوم 5 دنانير','citations':[]})
        answer = Engine(self.docs, ollama=m).ask('كم رسوم بطاقة المكتبة العامة؟')
        self.assertEqual(answer['status'], 'invalid')
    def test_full_doc_context(self):
        e = Engine(self.docs, ollama=FakeOllama({'status':'insufficient','answer':'غير مذكور','citations':[]}))
        ctx = e.retrieve('كم رسوم إصدار بطاقة المكتبة العامة؟')
        self.assertIn('الطلبة دون عمر 18', ctx['context'])
    def test_no_documents_refusal(self):
        e = Engine({'documents':[], 'chunks':[]}, ollama=FakeOllama({}))
        self.assertEqual(e.ask('سؤال')['status'], 'insufficient')

if __name__ == '__main__':
    unittest.main()
