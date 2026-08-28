import re

from app.database import SessionLocal, engine, Base
from app.models import Conciliacao, ConciliacaoItem
from app.services import vinculos as serv


def test_service_mapa_salvar_remover():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    serv.salvar(db, "2026-07", "54017315000170", "300", "FORN",
                "54017315000170", "0", 970.0, "num errado no spdata")
    m = serv.mapa(db, "2026-07")
    v = m[("54017315000170", "300")]
    assert v["sp_numero"] == "0" and v["sp_valor"] == 970.0 and "errado" in v["obs"]
    assert serv.mapa(db, "2026-08") == {}                 # isolado por competência
    assert serv.remover(db, "2026-07", "54017315000170", "300") is True
    assert serv.mapa(db, "2026-07") == {}
    db.close()


from app.routers.resultado import montar_resumo_e_itens
from app.services import aliquotas as serv_al


def _conc_nota_e_orfao(db, competencia="2026-07"):
    """Conciliação com: NOTA Sieg 300 'faltou lançar' + lançamento SP 'sem sieg'
    (mesmo CNPJ e valor, número 0)."""
    conc = Conciliacao(cnpj="11", competencia=competencia,
                       periodo_inicio="2026-07-01", periodo_fim="2026-07-31")
    db.add(conc); db.flush()
    db.add(ConciliacaoItem(conciliacao_id=conc.id, numero="300",
        cnpj_fornecedor="54017315000170", nome_fornecedor="FORN", data_emissao="03/07/2026",
        valor_bruto=970.0, valor_liquido=970.0, imp_sieg=0.0,
        status_lancamento="falta", status_arquivo="ok", veredito="pendente", cancelada=False))
    db.add(ConciliacaoItem(conciliacao_id=conc.id, numero="0",
        cnpj_fornecedor="54017315000170", nome_fornecedor="FORN", data_emissao="",
        valor_bruto=0.0, valor_liquido=0.0, sp_valor_bruto=970.0, sp_valor_liquido=970.0,
        imp_spdata=0.0, status_lancamento="", status_arquivo="", veredito="sp_sem_sieg",
        cancelada=False))
    db.commit(); db.refresh(conc); return conc


def test_vinculo_valores_batem_vira_gerenciada_e_tira_orfao(client):  # client garante schema
    db = SessionLocal(); serv_al.garantir_padrao(db)
    conc = _conc_nota_e_orfao(db)
    serv.salvar(db, "2026-07", "54017315000170", "300", "FORN",
                "54017315000170", "0", 970.0, "num errado")
    resumo, itens = montar_resumo_e_itens(conc, serv_al.listar(db), None, None, None,
                                          serv.mapa(db, "2026-07"))
    nota = next(i for i in itens if i["numero"] == "300")
    assert nota["vinculada"] and nota["eh_gerenciada"] and not nota["tem_erro"]
    assert resumo["qt_vinculadas"] == 1
    assert resumo["qt_sp_sem_sieg"] == 0            # o órfão foi consumido
    db.close()


def test_vinculo_valores_divergem_vira_ressalva(client):
    db = SessionLocal(); serv_al.garantir_padrao(db)
    conc = _conc_nota_e_orfao(db)
    # órfão com valor diferente da nota (970) -> divergência
    orf = db.query(ConciliacaoItem).filter(ConciliacaoItem.veredito == "sp_sem_sieg").first()
    orf.sp_valor_bruto = 900.0; orf.sp_valor_liquido = 900.0; db.commit()
    serv.salvar(db, "2026-07", "54017315000170", "300", "FORN",
                "54017315000170", "0", 900.0, "num errado, valor diverge")
    resumo, itens = montar_resumo_e_itens(conc, serv_al.listar(db), None, None, None,
                                          serv.mapa(db, "2026-07"))
    nota = next(i for i in itens if i["numero"] == "300")
    assert nota["vinculada"] and nota["tem_erro"]          # Ressalva (diverge)
    assert nota["status_lancamento"] == "diverg"
    db.close()


def test_pacote_dados_traz_vinculo_e_contagem(client):  # client garante schema
    from app.services import pacote_dados

    db = SessionLocal(); serv_al.garantir_padrao(db)
    conc = _conc_nota_e_orfao(db)
    serv.salvar(db, "2026-07", "54017315000170", "300", "FORN",
                "54017315000170", "0", 970.0, "num errado")
    resumo, itens = montar_resumo_e_itens(conc, serv_al.listar(db), None, None, None,
                                          serv.mapa(db, "2026-07"))
    pacote = pacote_dados.gerar_pacote_dados(resumo, itens, conc)
    nota = next(i for i in pacote["itens"] if i["numero"] == "300")
    assert nota["vinculo"] == {
        "sp_cnpj": "54017315000170", "sp_numero": "0", "sp_valor": 970.0,
        "observacao": "num errado",
    }
    assert pacote["resumo"]["vinculadas"] == 1
    db.close()


def test_http_seletor_usa_numero_norm_mesmo_com_padding_na_tela(client):
    """Regressão do bug crítico da revisão de código (commit b197229):
    o <option value="cnpj|numero|valor"> do seletor de vínculo usava
    `o.numero` -- o número JÁ FORMATADO com zero-padding (`pad_numero`,
    aplicado quando notas da mesma conciliação têm quantidades de dígitos
    diferentes). O valor de `sp_numero` postado ficava então zero-padded,
    mas `montar_resumo_e_itens` indexa o órfão "sp sem sieg" pelo
    `numero_norm` (sem padding) -- então o vínculo nunca batia: nenhum selo
    "Vinculada" aparecia e a nota continuava "faltou lançar", mesmo com uma
    linha `Vinculo` criada no banco. Round-trip HTTP completo: monta a
    conciliação -> GET /resultado (extrai o <option> real do HTML) ->
    POST /vinculos/marcar com o value exato -> GET /resultado de novo e
    confere que a nota ficou vinculada.
    Este teste FALHA no template pré-fix (value com `o.numero` padded) e
    PASSA com `o.numero_norm`.
    """
    from app.services import aliquotas as serv_al
    from app.routers.resultado import montar_resumo_e_itens

    db = SessionLocal(); serv_al.garantir_padrao(db)
    competencia = "2026-07"
    conc = Conciliacao(cnpj="11", competencia=competencia,
                       periodo_inicio="2026-07-01", periodo_fim="2026-07-31")
    db.add(conc); db.flush()
    # Nota "faltou lançar" com número curto (3 dígitos) -- vai virar "300" ou,
    # se a conciliação tiver outro número mais comprido, "00300" na tela.
    db.add(ConciliacaoItem(conciliacao_id=conc.id, numero="300",
        cnpj_fornecedor="54017315000170", nome_fornecedor="FORN", data_emissao="03/07/2026",
        valor_bruto=970.0, valor_liquido=970.0, imp_sieg=0.0,
        status_lancamento="falta", status_arquivo="ok", veredito="pendente", cancelada=False))
    # Nota comum com número de mais dígitos -- só para FORÇAR o padding (largura=5)
    # de todos os números da conciliação, inclusive os das notas acima/abaixo.
    db.add(ConciliacaoItem(conciliacao_id=conc.id, numero="45678",
        cnpj_fornecedor="11111111000100", nome_fornecedor="OUTRO", data_emissao="01/07/2026",
        valor_bruto=50.0, valor_liquido=50.0, sp_valor_bruto=50.0, sp_valor_liquido=50.0,
        imp_sieg=0.0, imp_spdata=0.0, status_lancamento="ok", status_arquivo="ok",
        veredito="ok", cancelada=False))
    # Órfão "SP sem SIEG": mesmo CNPJ/valor da nota 300, número "0" -- que
    # também vira "00000" na tela por causa do padding acima.
    db.add(ConciliacaoItem(conciliacao_id=conc.id, numero="0",
        cnpj_fornecedor="54017315000170", nome_fornecedor="FORN", data_emissao="",
        valor_bruto=0.0, valor_liquido=0.0, sp_valor_bruto=970.0, sp_valor_liquido=970.0,
        imp_spdata=0.0, status_lancamento="", status_arquivo="", veredito="sp_sem_sieg",
        cancelada=False))
    db.commit(); db.refresh(conc)
    conc_id = conc.id
    db.close()

    r1 = client.get(f"/resultado/{conc_id}")
    assert r1.status_code == 200
    html = r1.text
    assert "00300" in html   # pré-condição: a tela realmente aplicou o padding

    m = re.search(r'<option value="(54017315000170\|[^"]+)">', html)
    assert m, "opção do seletor de vínculo (mesmo CNPJ) não encontrada no HTML"
    sp_cnpj, sp_numero, sp_valor = m.group(1).split("|")
    assert sp_numero == "0", (
        "BUG (finding 1): o <option value> deveria trazer numero_norm ('0'), "
        f"veio '{sp_numero}' (zero-padded) -- o vínculo postado nunca bateria com o órfão"
    )

    # Como o JS faria: separa "cnpj|numero|valor" nos 3 hidden fields e submete.
    resp = client.post("/vinculos/marcar", data={
        "cnpj": "54017315000170", "numero": "300", "nome": "FORN",
        "sp_cnpj": sp_cnpj, "sp_numero": sp_numero, "sp_valor": sp_valor,
        "observacao": "teste round-trip", "competencia": competencia,
        "conciliacao_id": conc_id,
    }, follow_redirects=False)
    assert resp.status_code in (200, 303)

    r2 = client.get(f"/resultado/{conc_id}")
    assert r2.status_code == 200
    html2 = r2.text
    assert "Vinculada" in html2 and "teste round-trip" in html2   # selo teal na tela

    db2 = SessionLocal()
    conc2 = db2.query(Conciliacao).filter(Conciliacao.id == conc_id).first()
    resumo, itens = montar_resumo_e_itens(conc2, serv_al.listar(db2), None, None, None,
                                          serv.mapa(db2, competencia))
    nota = next(i for i in itens if i["numero_norm"] == "300")
    assert nota["vinculada"] is True
    assert nota["eh_gerenciada"] is True and not nota["tem_erro"]
    assert resumo["qt_sp_sem_sieg"] == 0            # o órfão foi consumido
    db2.close()
