"""Derive cards from published JSON without changing dictionary content."""
import hashlib, json, re

def required(obj,key):
 v=obj.get(key)
 if not isinstance(v,str) or not v.strip(): raise ValueError('Missing/non-text '+key)
 return v

def study_data(words):
 cards=[]; senses={}; examples=[]; seen_words=set(); seen_ids=set(); total_senses=0
 for word in words:
  name=required(word,'word'); slug=required(word,'slug')
  if not re.fullmatch(r'[a-z0-9-]+',slug) or name in seen_words: raise ValueError('Invalid/duplicate word: '+name)
  seen_words.add(name); ws=word.get('senses')
  if not isinstance(ws,list) or not ws or ws[0].get('number')!=1: raise ValueError('Missing first sense: '+name)
  for sense in ws:
   total_senses+=1; n=sense.get('number')
   if type(n) is not int or n<1: raise ValueError('Invalid sense number: '+name)
   key=f'{slug}:{n}'
   if key in senses: raise ValueError('Duplicate sense: '+key)
   title=required(sense,'title'); definition=required(sense,'definition')
   senses[key]=dict(word=name,senseNumber=n,meaning=title,definition=definition,url=f'words/{slug}.html#sense-{n}')
   pairs=sense.get('collocations')
   if not isinstance(pairs,list) or not pairs: raise ValueError('Missing example: '+key)
   for pair in pairs:
    en=required(pair,'example');ja=required(pair,'translation');cid=key+':'+hashlib.sha256((en+'\0'+ja).encode()).hexdigest()[:20]
    if cid in seen_ids: raise ValueError('Duplicate example: '+cid)
    seen_ids.add(cid);examples.append(dict(id=cid,senseId=key,example=en,translation=ja))
  first=ws[0];title=first['title'];match=re.search(r'\b'+re.escape(name)+r'(?: [a-z]+)+\b',title.split('】',1)[0]);pair=first['collocations'][0]
  cards.append(dict(word=name,prompt=match.group() if match else name,meaning=title,definition=first['definition'],example=pair['example'],translation=pair['translation'],url=f'words/{slug}.html'))
 report=dict(total=len(words),accepted=len(cards),excluded=[],counts=dict(missing=0,unsupported=0,review_mismatch=0),scope='Published dictionary JSON; existing first-sense example')
 er=dict(words=len(words),totalSenses=total_senses,coveredSenses=len(senses),sourcePairs=len(examples),accepted=len(examples),excluded=[],missingSenses=[],verification='English/Japanese copied from the same published JSON collocation')
 return cards,senses,examples,report,er

def build_study(words,destination):
 cards,senses,examples,report,er=study_data(words);encode=lambda x:json.dumps(x,ensure_ascii=False,separators=(',',':'))
 w='const WORDS='+encode(cards)+';\nconst IMPORT_REPORT='+encode(report)+';\n'
 e='const EXAMPLE_SENSES='+encode(senses)+';\nconst EXAMPLES='+encode(examples)+';\nconst EXAMPLE_REPORT='+encode(er)+';\n'
 destination.mkdir(exist_ok=True)
 (destination/'study-words.js').write_text(w,encoding='utf-8');(destination/'study-examples.js').write_text(e,encoding='utf-8')
 print(f'Built study: {len(cards)} words, {len(senses)} senses, {len(examples)} existing example pairs.')
