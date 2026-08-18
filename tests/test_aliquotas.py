from app.database import SessionLocal
from app.services import aliquotas as al


def test_padrao_e_vigente(db_limpo):
    s = SessionLocal()
    try:
        al.garantir_padrao(s)
        assert len(al.listar(s)) == 1
        v = al.vigente(s, "2026-07-15")
        assert v["irpj"] == 1.50 and v["pis"] == 0.65
        assert v["cofins"] == 3.00 and v["csll"] == 1.00
        assert v["consolidado"] == 4.65          # pis+cofins+csll
    finally:
        s.close()


def test_vigencia_por_periodo(db_limpo):
    s = SessionLocal()
    try:
        al.garantir_padrao(s)                          # 2026-01-01 padrão
        al.salvar_vigencia(s, "2026-06-01", 1.20, 0.65, 3.00, 1.00)   # nova vigência
        # antes de junho usa o padrão; a partir de junho usa a nova
        assert al.vigente(s, "2026-05-31")["irpj"] == 1.50
        assert al.vigente(s, "2026-06-10")["irpj"] == 1.20
        # salvar de novo a mesma vigência ATUALIZA (não duplica)
        al.salvar_vigencia(s, "2026-06-01", 1.30, 0.65, 3.00, 1.00)
        assert al.vigente(s, "2026-06-10")["irpj"] == 1.30
        assert len(al.listar(s)) == 2
    finally:
        s.close()


def test_tela_config_mostra_aliquotas(client):
    r = client.get("/configuracoes")
    assert r.status_code == 200
    assert "Alíquotas base de retenção" in r.text
    assert "Consolidado" in r.text
