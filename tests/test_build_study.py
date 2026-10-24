import copy, json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from build_study import study_data,build_study
class StudyDataTests(unittest.TestCase):
 def setUp(self):
  self.word=dict(word='abide',slug='abide',senses=[dict(number=1,title='【動詞 abide by】従う',definition='<p>守る</p>',collocations=[dict(example='Abide by the rules.',translation='規則を守る。')])])
 def test_exact_copy_and_construction(self):
  before=copy.deepcopy(self.word);c,s,e,r,er=study_data([self.word]);self.assertEqual(self.word,before);self.assertEqual(c[0]['prompt'],'abide by');self.assertEqual(c[0]['definition'],self.word['senses'][0]['definition']);self.assertEqual(e[0]['translation'],'規則を守る。');self.assertEqual(s['abide:1']['url'],'words/abide.html#sense-1')
 def test_every_published_pair_matches(self):
  root=Path(__file__).resolve().parents[1];words=[json.loads(p.read_text()) for p in sorted((root/'content').glob('*.json'))];c,s,e,r,er=study_data(words);expected={(f"{w['slug']}:{sn['number']}",p['example'],p['translation']) for w in words for sn in w['senses'] for p in sn['collocations']};self.assertEqual({(v['senseId'],v['example'],v['translation']) for v in e},expected);self.assertEqual(len(e),sum(len(sn['collocations']) for w in words for sn in w['senses']));self.assertEqual(len(c),len(words))
 def test_missing_translation_rejected(self):
  del self.word['senses'][0]['collocations'][0]['translation']
  with self.assertRaises(ValueError): study_data([self.word])
 def test_duplicate_pair_rejected(self):
  self.word['senses'][0]['collocations']*=2
  with self.assertRaises(ValueError):study_data([self.word])
 def test_invalid_slug_rejected(self):
  self.word['slug']='../bad'
  with self.assertRaises(ValueError):study_data([self.word])
 def test_duplicate_word_rejected(self):
  with self.assertRaises(ValueError):study_data([self.word,self.word])
 def test_failed_build_preserves_outputs(self):
  with tempfile.TemporaryDirectory() as tmp:
   dest=Path(tmp);build_study([self.word],dest);before={p.name:p.read_bytes() for p in dest.iterdir()};self.word['senses']=[]
   with self.assertRaises(ValueError):build_study([self.word],dest)
   self.assertEqual(before,{p.name:p.read_bytes() for p in dest.iterdir()})
 def test_example_id_is_content_stable(self):
  first=study_data([self.word])[2][0]['id'];self.word['senses'][0]['collocations'].insert(0,dict(example='Another sentence.',translation='別の文。'));self.assertEqual(study_data([self.word])[2][1]['id'],first)
