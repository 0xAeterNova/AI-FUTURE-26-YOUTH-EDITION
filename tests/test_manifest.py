import json
import tempfile
import unittest
from pathlib import Path
from burhan.documents import index_folder
from burhan.retrieve import Retriever

class ManifestTest(unittest.TestCase):
    def test_split_merged_text_source(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root/'merged.txt').write_text('خدمة تصريح الفعالية\nرسوم التصريح 5 دنانير', encoding='utf8')
            (root/'map.json').write_text(json.dumps({'services': [{'title':'تصريح الفعالية', 'file':'merged.txt','pages':[1]}]}), encoding='utf8')
            index = index_folder(d, str(root/'index.json'), str(root/'map.json'))
            self.assertEqual(index['documents'][0]['title'], 'تصريح الفعالية')
            self.assertEqual(index['chunks'][0]['page_id'], 'D01-P1')

    def test_global_question_includes_all_services(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            (p/'a.txt').write_text('خدمة بطاقة\nرسوم: 5 دنانير\nالاستثناء: لا رسوم للطلاب',encoding='utf8')
            (p/'b.txt').write_text('خدمة شهادة\nرسوم: 20 دينار\nالاستثناء: لا يوجد',encoding='utf8')
            idx=index_folder(d,str(p/'index.json'))
            r=Retriever(idx)
            q='أي الخدمات رسومها أعلى؟'
            ctx,pg,rank=r.context(q,r.search(q))
            self.assertIn('5 دنانير',ctx)
            self.assertIn('20 دينار',ctx)
            self.assertEqual(len(pg),2)

if __name__ == '__main__': unittest.main()
