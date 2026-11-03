"""Invariantes del experimento; integración siempre en la base de pruebas aislada."""

from datetime import datetime, timezone
from dataclasses import replace
from types import SimpleNamespace
from uuid import uuid4

import numpy as np
import pytest

from src.database import (ConfiguracionModelo, ModelConfigRepository, DocumentRepository,
                          VersionRepository, FragmentRepository, VectorRepository)
from src.embeddings import EmbeddingService
from src.embeddings.registry import EMBEDDING_MODELS
from src.experiments import (MODEL_TABLES, digest, metrics, search_selected, verify, verify_coverage,
                             judgment_index, judge_ranking, first_relevant)


def configuration(alias, dimension):
    return ConfiguracionModelo(uuid4(), alias, EMBEDDING_MODELS[alias], dimension, True, True,
                               {"tabla_embeddings": MODEL_TABLES[alias]}, datetime.now(timezone.utc))


@pytest.mark.parametrize("alias,dimension", [("alia",768),("qwen3",1024),("bge-m3",1024)])
def test_each_provider_reports_backend_dimension_and_normalizes(alias, dimension):
    class Backend:
        def __init__(self,*args,**kwargs):
            self.calls=[]
        def get_embedding_dimension(self):
            return dimension
        def encode(self,texts,**kwargs):
            self.calls.append(kwargs)
            assert kwargs['normalize_embeddings'] is True
            return np.full((len(texts),dimension),1/np.sqrt(dimension),dtype=np.float32)
    service=EmbeddingService(alias,device='cpu',model_loader=Backend)
    vector=service.encode_query('consulta original')
    assert vector.shape==(dimension,) and np.linalg.norm(vector)==pytest.approx(1,abs=1e-5)
    assert service.encode_documents(['documento']).shape==(1,dimension)
    repo=VectorRepository(None,configuration(alias,dimension))
    assert repo.table_name==MODEL_TABLES[alias]


def test_selected_query_model_must_match_even_when_dimensions_match():
    calls=[]
    service=SimpleNamespace(model_name=EMBEDDING_MODELS['qwen3'],dimension=1024,
                            encode_query=lambda text:calls.append(text) or np.ones(1024))
    repo=SimpleNamespace(config=configuration('qwen3',1024),
                         search_similar=lambda vec,top_k:('qwen3',top_k))
    assert search_selected(service,repo,'sin reformular',10)==('qwen3',10)
    assert calls==['sin reformular']
    repo.config=configuration('bge-m3',1024)
    with pytest.raises(ValueError,match='no coincide'):
        search_selected(service,repo,'sin reformular',10)
    assert calls==['sin reformular']


def test_same_dimension_cannot_route_qwen_into_bge_table():
    cfg=configuration('qwen3',1024)
    cfg=replace(cfg,parametros={'tabla_embeddings':MODEL_TABLES['bge-m3']})
    with pytest.raises(ValueError,match='no corresponde'):
        VectorRepository(None,cfg)


def test_coverage_checks_ids_not_only_count():
    ids=['a','b']
    conn=SimpleNamespace(execute=lambda *args:SimpleNamespace(fetchall=lambda:[(i,) for i in ids]))
    repo=SimpleNamespace(table_name=MODEL_TABLES['alia'],config=configuration('alia',768))
    manifest={'chunks':[{'id':'a'},{'id':'b'}]}
    assert verify_coverage(conn,repo,manifest)==ids
    ids[:]=['a','c']
    with pytest.raises(ValueError,match='conjunto'):
        verify_coverage(conn,repo,manifest)


def test_freeze_rejects_changed_text_or_metadata(monkeypatch):
    state={'fragmentos':[{'texto':'original','ubicacion':'seccion'}]}
    manifest={'corpus_state_sha256':digest(state),'archivos_protegidos':{}}
    monkeypatch.setattr('src.experiments.corpus_state',lambda conn:state)
    verify(None,manifest)
    state['fragmentos'][0]['ubicacion']='otra'
    with pytest.raises(ValueError,match='cambió'):
        verify(None,manifest)


def test_hit_and_truncated_mrr_include_queries_without_a_hit():
    scores=metrics([1,3,10,None])
    assert scores=={'Hit@1':.25,'Hit@3':.5,'Hit@5':.5,'Hit@10':.75,
                    'MRR@10':pytest.approx((1+1/3+1/10)/4)}
    with pytest.raises(ValueError):metrics([])
    with pytest.raises(ValueError):metrics([11])


def test_human_judgment_is_never_replaced_by_assisted():
    human=[{'consulta_id':'MD10','fragmento_id':'a','pertinente':False,'motivo':'aumento de peso'}]
    index=judgment_index(human,[])
    assert index[('MD10','a')]['tipo_juicio']=='humano'
    for verdict in (True,False):
        with pytest.raises(ValueError,match='humano'):
            judgment_index(human,[{'consulta_id':'MD10','fragmento_id':'a','pertinente':verdict}])
    with pytest.raises(ValueError,match='contradictorios'):
        judgment_index([],[{'consulta_id':'Q','fragmento_id':'b','pertinente':True},
                           {'consulta_id':'Q','fragmento_id':'b','pertinente':False}])


def test_judgments_are_per_query_and_complete():
    index=judgment_index([{'consulta_id':'MD01','fragmento_id':'a','pertinente':True}],
                         [{'consulta_id':'MD01','fragmento_id':'b','pertinente':True}])
    ranking=judge_ranking('MD01',['b','a'],index)
    assert [j['tipo_juicio'] for j in ranking]==['asistido_preliminar','humano']
    assert first_relevant(ranking)==1
    assert first_relevant(ranking,kinds=('humano',))==2
    # The same fragment judged for another query is not reused.
    with pytest.raises(ValueError,match='faltan'):
        judge_ranking('MD02',['a'],index)


@pytest.mark.integration
def test_same_fragments_separate_model_tables_and_configs(db):
    doc=DocumentRepository(db).create('Experimento aislado', 'Prueba')
    version=VersionRepository(db).activate(VersionRepository(db).create(doc.id,'1').id)
    fragments=[FragmentRepository(db).create(version.id,i,f'texto {i}') for i in (1,2)]
    repos={}
    for alias,dimension in [('alia',768),('qwen3',1024),('bge-m3',1024)]:
        cfg=ModelConfigRepository(db).register(alias,EMBEDDING_MODELS[alias],dimension,True,
                                              {'tabla_embeddings':MODEL_TABLES[alias]})
        repos[alias]=VectorRepository(db,cfg)
        for i,f in enumerate(fragments):
            vector=np.zeros(dimension,dtype=np.float32)
            vector[(1-i) if alias=='bge-m3' else i]=1
            repos[alias].save_embedding(f.id,vector)
        assert repos[alias].count_embeddings()==2
        assert ModelConfigRepository(db).get_active(alias).id==cfg.id
        wrong=np.zeros(dimension+1,dtype=np.float32);wrong[0]=1
        with pytest.raises(ValueError,match='forma'):
            repos[alias].search_similar(wrong)
        with pytest.raises(ValueError,match='normalizados'):
            repos[alias].search_similar(np.ones(dimension,dtype=np.float32))
    for alias,repo in repos.items():
        q=np.zeros(repo.dimension,dtype=np.float32);q[0]=1
        hits=repo.search_similar(q,2,documento_id=doc.id)
        assert {h.fragmento_id for h in hits}=={f.id for f in fragments}
        assert hits[0].fragmento_id==fragments[1 if alias=='bge-m3' else 0].id
    repos['qwen3'].delete_embeddings_for_fragment(fragments[0].id)
    assert repos['qwen3'].count_embeddings()==1
    assert repos['bge-m3'].count_embeddings()==repos['alia'].count_embeddings()==2


def _persisted_or_skip(db_name='vianova_rag'):
    import os
    from src.config import DatabaseSettings
    from src.database import connect, DatabaseUnavailableError
    if os.getenv('RUN_MODEL_TESTS')!='1':
        pytest.skip('Defina RUN_MODEL_TESTS=1 para verificar el experimento persistido.')
    try:
        return connect(replace(DatabaseSettings.from_env(),dbname=db_name))
    except (DatabaseUnavailableError,ValueError) as exc:
        pytest.skip(str(exc))


@pytest.mark.integration
def test_persisted_experiment_uses_same_419_chunks_in_every_model_table():
    import json
    from src.config import PROJECT_ROOT
    manifest=json.loads((PROJECT_ROOT/'eval/experimentos/corpus_v01_manifest.json').read_text())
    with _persisted_or_skip() as conn:
        conn.execute('SET TRANSACTION READ ONLY')
        verify(conn,manifest)
        coverage={}
        for alias,table in MODEL_TABLES.items():
            cfg=ModelConfigRepository(conn).get_active(alias)
            repo=VectorRepository(conn,cfg)
            assert repo.table_name==table and cfg.model_id==EMBEDDING_MODELS[alias]
            coverage[alias]=verify_coverage(conn,repo,manifest)
            dims=conn.execute(f'SELECT DISTINCT vector_dims(embedding) FROM {table} WHERE configuracion_id=%s',
                              (cfg.id,)).fetchall()
            assert dims==[(cfg.dimension,)]
        assert len(coverage['alia'])==419 and coverage['alia']==coverage['qwen3']==coverage['bge-m3']


@pytest.mark.integration
@pytest.mark.parametrize('alias',['qwen3','bge-m3'])
def test_real_model_dimension_normalization_and_query_format(alias):
    import json,os
    from src.config import PROJECT_ROOT
    if os.getenv('RUN_MODEL_TESTS')!='1':
        pytest.skip('Defina RUN_MODEL_TESTS=1 para cargar el modelo real.')
    from sentence_transformers import SentenceTransformer
    revision=json.loads((PROJECT_ROOT/'eval/experimentos/model_revisions_v01.json').read_text())[alias]['revision']
    import torch
    # Misma configuración que el experimento: float32 (Qwen3 carga en bfloat16 por defecto y su norma se desvía ~2e-3).
    loader=lambda model_id,device:SentenceTransformer(model_id,device=device,revision=revision,local_files_only=True,
                                                      model_kwargs={'dtype':torch.float32})
    service=EmbeddingService(alias,batch_size=2,model_loader=loader)
    text='signos de infección durante la quimioterapia'
    doc=service.encode_documents([text])[0]
    query=service.encode_query(text)
    assert service.dimension==doc.shape[0]==query.shape[0]==1024
    assert np.linalg.norm(doc)==pytest.approx(1,abs=1e-4)
    assert np.linalg.norm(query)==pytest.approx(1,abs=1e-4)
    if alias=='qwen3':
        assert not np.allclose(doc,query,atol=1e-3)  # query lleva la instrucción de retrieval
    else:
        assert np.allclose(doc,query,atol=1e-5)  # BGE-M3 dense: sin instrucción


@pytest.mark.integration
@pytest.mark.parametrize('alias',['alia','qwen3','bge-m3'])
def test_persisted_top10_is_reproducible_with_selected_model(alias):
    import gc,json
    import torch
    from src.config import PROJECT_ROOT
    from sentence_transformers import SentenceTransformer
    conn=_persisted_or_skip()
    raw=json.loads((PROJECT_ROOT/f'eval/experimentos/resultados_{alias}_v01.json').read_text())
    revision=raw['configuracion']['revision']
    loader=lambda model_id,device:SentenceTransformer(model_id,device=device,revision=revision,local_files_only=True,
                                                      model_kwargs={'dtype':torch.float32})
    service=EmbeddingService(alias,batch_size=16,model_loader=loader)
    try:
        with conn:
            conn.execute('SET TRANSACTION READ ONLY')
            repo=VectorRepository(conn,ModelConfigRepository(conn).get_active(alias))
            for q in raw['consultas']:
                hits=search_selected(service,repo,q['texto'],10)
                assert [str(h.fragmento_id) for h in hits]==q['top_k_ids']['10'], q['id']
    finally:
        del service; gc.collect()
        if torch.cuda.is_available(): torch.cuda.empty_cache()
