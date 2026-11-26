from scripts.semantic_briefing import compact


def test_compact_view_preserves_all_ids_forms_counts_and_provenance_without_locations():
    row={'id':'Q-a','type':'query','text':'contractor invoices','variants':['contractor invoices'],
         'query_ids':['Q-a'],'impressions':3,
         'before':{'exact':0,'morph':1,'morph_locations':[{'excerpt':'large'}]},
         'after':{'exact':2,'morph':3,'exact_locations':[{'excerpt':'large'}]}}
    report={'rows':[row],'summary':{'queries':1},'definitions':{'exact':'literal'}}
    view=compact(report,'bound-source-hash')
    assert view['coverage_sha256']=='bound-source-hash' and len(view['rows'])==1
    assert view['rows'][0]['variants']==row['variants'] and view['rows'][0]['query_ids']==row['query_ids']
    assert view['rows'][0]['counts']=={'exact_before':0,'exact_after':2,'morph_before':1,'morph_after':3}
    assert 'locations' not in str(view['rows']) and 'large' not in str(view)


def test_no_top_n_truncation_of_agent_view():
    rows=[{'id':str(i),'type':'unigram','text':'word','variants':['word'],'query_ids':['q'],
           'all_stopwords':False,'before':{'exact':0,'morph':0},'after':{'exact':1,'morph':1}}
          for i in range(1200)]
    assert len(compact({'rows':rows,'summary':{},'definitions':{}},'hash')['rows'])==1200
