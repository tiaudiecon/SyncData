import json
from app.database import SessionLocal, engine, Base
from app.models import Conciliacao, ConciliacaoItem
from app.routers.resultado import montar_resumo_e_itens
from app.services import excecoes as serv
from app.services import aliquotas as al
from app.services.aliquotas import garantir_padrao
from app.services.parser_spdata import LancamentoSpData


def test_item5_liquido_spdata_e_bruto_menos_impostos():
    # item 5: líquido do SP Data = Bruto − Impostos (não a coluna do arquivo)
    l = LancamentoSpData("1", "1", "11", "F", None, 1000.0,
                         issqn=10.0, irpj=15.0, csrf=46.5)   # impostos = 71,50
    assert l.total_retencoes == 71.5
    assert l.valor_liquido == 928.5                         # 1000 − 71,50


def _conc_com_divergencia(db):
    conc = Conciliacao(cnpj="11", competencia="2026-07")
    db.add(conc); db.flush()
    imp = {"sieg": {"ir": 0.0, "csrf": 0.0, "iss": 0.0, "inss": 0.0, "optante_sn": False,
                    "descontos": 0.0, "base_calculo": 1000.0, "total": 0.0, "iss_retido": False},
           "spdata": {"iss": 0, "inss": 0, "ir": 0, "csrf": 0, "total": 0}}
    db.add(ConciliacaoItem(
        conciliacao_id=conc.id, numero="1", cnpj_fornecedor="11222333000199",
        nome_fornecedor="FORN X", data_emissao="03/07/2026", valor_bruto=1000.0,
        valor_liquido=1000.0, imp_sieg=0.0, impostos_json=json.dumps(imp),
        status_lancamento="ok", status_arquivo="ok", veredito="gerenciada",
        cancelada=False, sp_valor_bruto=1000.0, sp_valor_liquido=1000.0))
    db.commit(); db.refresh(conc)
    return conc


def test_item6_excecao_tira_de_divergencia_impostos(client):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal(); garantir_padrao(db)
    conc = _conc_com_divergencia(db)
    # base 1000: IRPJ esperado 15 (>10) apurado 0 -> pendência (sem exceção)
    _, itens = montar_resumo_e_itens(conc, al.listar(db))
    assert itens[0]["pendencia_sieg"] is True and itens[0]["excecao"] is False
    assert itens[0]["tem_erro"] is True and itens[0]["eh_gerenciada"] is False
    # marca o fornecedor como exceção
    serv.salvar(db, "11.222.333/0001-99", "FORN X", "entidade imune")
    _, itens2 = montar_resumo_e_itens(conc, al.listar(db), serv.mapa_cnpjs(db))
    assert itens2[0]["excecao"] is True
    assert itens2[0]["pendencia_sieg"] is False            # sai de Divergência Impostos
    # item (ajuste): exceção também conta como Gerenciada, além de aparecer em Exceções
    assert itens2[0]["eh_gerenciada"] is True and itens2[0]["tem_erro"] is False
    assert itens2[0]["excecao_obs"] == "entidade imune"
    db.close()


def test_item6_servico_crud(client):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    e = serv.salvar(db, "11.222.333/0001-99", "FORN X", "motivo A")
    assert serv.mapa_cnpjs(db).get("11222333000199") == "motivo A"
    serv.salvar(db, "11222333000199", "FORN X", "motivo B")   # idempotente por CNPJ
    assert len(serv.listar(db)) == 1                          # não duplica
    assert serv.mapa_cnpjs(db)["11222333000199"] == "motivo B"
    assert serv.remover(db, e.id) is True
    assert serv.mapa_cnpjs(db) == {}
    db.close()
