"""Batch whitelist, shared-budget and early CMS regression contracts; no paid calls."""
import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import openrouter_batch as batch
import openrouter_pilot as pilot

class BatchContracts(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.dest=self.root/'batch';self.dest.mkdir()
  self.cases=[]
  for i in range(batch.BATCH_SIZE):
   slug=f'term-{i}';name=batch.BATCH_ID+'-'+slug;job=self.root/'jobs'/name;job.mkdir(parents=True)
   (job/'request.json').write_text(json.dumps({'batch':batch.BATCH_ID,'slug':slug,'term':f'Term {i}'}))
   self.cases.append({'slug':slug,'term':f'Term {i}','job':'jobs/'+name})
  self.manifest={'cases':self.cases,'openrouter_global_cap_usd':3};self.save()
  for obj,name,value in [(batch,'ROOT',self.root),(pilot,'ROOT',self.root),(pilot,'JOBS',list(batch.PILOT_JOBS)),(pilot,'ROUND2_JOBS',list(pilot.ROUND2_JOBS)),(pilot,'CAP',3.)]:
   ctx=patch.object(obj,name,value);ctx.start();self.addCleanup(ctx.stop)
 def save(self): (self.dest/'manifest.json').write_text(json.dumps(self.manifest))
 def test_batch_preserves_all_prior_charges_and_blocks_critics(self):
  jobs=batch.configure(self.dest);self.assertEqual(len(jobs),batch.BATCH_SIZE);self.assertEqual(len(pilot.JOBS),batch.BATCH_SIZE+len(batch.PILOT_JOBS))
  old=self.root/'jobs'/batch.PILOT_JOBS[0]/'pilot/api/paid/attempt-001/receipt.json';old.parent.mkdir(parents=True);old.write_text(json.dumps({'status':'success','cost_usd':.32896257}))
  self.assertEqual(pilot.usage()['cost_usd'],.32896257);self.assertEqual(pilot.CAP,3.)
  with self.assertRaisesRegex(pilot.PilotError,'no critic'):pilot.critique(next(iter(jobs.values())),'kimi')
 def test_no_manifest_path_escape(self):
  self.manifest['cases'][0]['job']='jobs/../outside';self.save()
  with self.assertRaises(pilot.PilotError):batch.configure(self.dest)
 def test_cap_and_approved_case_count_must_remain_fixed(self):
  for key,value in [('openrouter_global_cap_usd',4),('cases',self.cases[:-1])]:
   with self.subTest(key=key):
    original=self.manifest[key];self.manifest[key]=value;self.save()
    with self.assertRaises(pilot.PilotError):batch.configure(self.dest)
    self.manifest[key]=original
 def test_identity_drift_rejected(self):
  path=self.root/self.cases[0]['job']/'request.json';path.write_text(json.dumps({'batch':'other','slug':'term-0','term':'Term 0'}))
  with self.assertRaises(pilot.PilotError):batch.configure(self.dest)
 def test_active_editor_handoff_cannot_overwrite_prose(self):
  job=self.root/self.cases[0]['job'];(job/'edited.md').write_text('Existing reviewed text')
  with self.assertRaisesRegex(pilot.PilotError,'locked'):batch.handoff(job)
  self.assertEqual((job/'edited.md').read_text(),'Existing reviewed text')

class EarlyCMS(unittest.TestCase):
 def test_aligned_markdown_table_is_detected_before_semantic_qa(self):
  with tempfile.TemporaryDirectory() as temp:
   job=Path(temp);d=job/'pilot/arms/a';(d/'units').mkdir(parents=True)
   (job/'sections.json').write_text(json.dumps({'sections':[{'id':'rules','title':'Rules','subheadings':[]}]}))
   (d/'meta.json').write_text(json.dumps({'term':'Term','slug':'term','locale':'en','definition':'Meaning.','metaTitle':'Term','metaDescription':'Meaning.','indexable':False}))
   for aligned in [True,False]:
    body='## Rules\n\n| Item | Amount |\n|---|'+('---:' if aligned else '---')+'|\n| A | 2 |\n'
    (d/'assembled.md').write_text(body);(d/'units/rules-01.md').write_text(body)
    result=batch.static_check(job)
    self.assertEqual(result['sanitizer_equal'],not aligned)
    self.assertEqual(result['unit_ids_with_sanitizer_changes'],['rules-01'] if aligned else [])


class FormatNormalization(unittest.TestCase):
 def test_only_complete_table_delimiters_change(self):
  original='Time 12:30 and https://example.org.\r\n\n| A | B |\n| :--- | ---: |\n| a:b | https://x |\n\n---:\n'
  expected=original.replace('| :--- | ---: |','| --- | --- |')
  self.assertEqual(batch.plain_table_separators(original),expected)
 def test_raw_snapshot_and_prose_are_immutable_and_replay_is_idempotent(self):
  with tempfile.TemporaryDirectory() as temp:
   j=Path(temp);d=j/'pilot/arms/a';(d/'units').mkdir(parents=True);(j/'sections.json').write_text(json.dumps({'sections':[{'id':'rules','title':'Rules','subheadings':[]}]}))
   body='## Rules\n\nAmount: 12:30.\n\n| A | B |\n|---|---:|\n| C | 2 |\n';(d/'units/rules-01.md').write_text(body);(d/'assembled.md').write_text(body)
   for name in ['meta.json','history.json','stage.json']:(d/name).write_text('{}')
   (j/'pilot/frozen-manifest.json').write_text('{}')
   result=batch.normalize_tables(j);self.assertEqual((j/'pilot/raw/assembled.md').read_text(),body);self.assertEqual((d/'assembled.md').read_text(),body.replace('|---|---:|','|---|---|'))
   self.assertEqual(result['changes'][0]['removed_alignment_colons'],1);self.assertEqual(batch.normalize_tables(j),result)
   self.assertEqual((d/'meta.json').read_text(),'{}');self.assertEqual((d/'history.json').read_text(),'{}')
 def test_locked_editor_prevents_format_mutation(self):
  with tempfile.TemporaryDirectory() as temp:
   j=Path(temp);(j/'edited.md').write_text('Reviewed text')
   with self.assertRaisesRegex(pilot.PilotError,'locked'):batch.normalize_tables(j)
   self.assertEqual((j/'edited.md').read_text(),'Reviewed text')

if __name__=='__main__':unittest.main()
