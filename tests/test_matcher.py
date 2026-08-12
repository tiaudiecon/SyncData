from datetime import date
from app.services.parser_spdata import LancamentoSpData
from app.services.parser_sieg import NotaSieg
from app.services.parser_renew import RegistroRenew
from app.services.matcher import conciliar, STATUS_OK, STATUS_DIVERG, STATUS_FALTA


def nota(numero="100", cnpj="11111111000111", emissao=date(2026, 7, 3),
         servico=150.0, liquido=150.0, cancelada=False):
    return NotaSieg(numero, numero.lstrip("0"), cnpj, "FORNEC A", emissao,
                    servico, liquido, cancelada)


def lanc(numero="100", cnpj="11111111000111", emissao=date(2026, 7, 3),
         bruto=150.0, liquido=150.0):
    return LancamentoSpData(numero, numero.lstrip("0"), cnpj, "FORNEC A",
                            emissao, bruto, liquido)


def reg(numero="100", cnpj="11111111000111", emissao=date(2026, 7, 3), valor=150.0):
    return RegistroRenew(numero, numero.lstrip("0"), cnpj, "FORNEC A", emissao, valor)


def test_nota_totalmente_gerenciada():
    r = conciliar([nota()], [], [lanc()], [reg()])
    item = r.itens[0]
    assert item.lancamento.status == STATUS_OK
    assert item.arquivo.status == STATUS_OK
    assert item.veredito == "gerenciada"
    assert r.qt_gerenciadas == 1


def test_faltou_lancar_e_faltou_arquivar():
    r = conciliar([nota()], [], [], [])   # não achou em lugar nenhum
    item = r.itens[0]
    assert item.lancamento.status == STATUS_FALTA
    assert item.arquivo.status == STATUS_FALTA
    assert item.veredito == "pendente"
    assert r.qt_falta_lancar == 1
    assert r.qt_falta_arquivar == 1


def test_divergencia_de_valor_vira_ressalva():
    r = conciliar([nota(liquido=150.0, servico=150.0)],
                  [], [lanc(bruto=150.0, liquido=140.0)], [reg(valor=150.0)])
    item = r.itens[0]
    assert item.lancamento.status == STATUS_DIVERG
    assert "líquido" in item.lancamento.detalhe.lower()
    assert item.arquivo.status == STATUS_OK
    assert item.veredito == "ressalva"
    assert r.qt_ressalva == 1


def test_divergencia_de_data():
    r = conciliar([nota(emissao=date(2026, 7, 3))],
                  [], [lanc(emissao=date(2026, 7, 5))], [reg()])
    item = r.itens[0]
    assert item.lancamento.status == STATUS_DIVERG
    assert "data" in item.lancamento.detalhe.lower()


def test_tolerancia_5_centavos_conta_como_ok():
    r = conciliar([nota(liquido=150.00, servico=150.00)],
                  [], [lanc(bruto=150.05, liquido=150.00)], [reg(valor=150.00)])
    assert r.itens[0].lancamento.status == STATUS_OK


def test_canceladas_ficam_a_parte():
    r = conciliar([nota()], [nota(numero="900", cancelada=True)], [lanc()], [reg()])
    assert r.total_universo == 1
    assert r.qt_canceladas == 1
    assert r.itens[0].veredito == "gerenciada"


def test_falta_domina_diverg_vira_pendente():
    # lançamento diverge (líquido), arquivo não encontrado → pendente (falta domina)
    r = conciliar([nota(servico=150.0, liquido=150.0)],
                  [], [lanc(bruto=150.0, liquido=140.0)], [])
    item = r.itens[0]
    assert item.lancamento.status == STATUS_DIVERG
    assert item.arquivo.status == STATUS_FALTA
    assert item.veredito == "pendente"


def test_divergencia_na_frente_arquivo_renew():
    # arquivo (Renew) diverge no valor (bruto); lançamento ok → ressalva
    r = conciliar([nota(servico=150.0, liquido=150.0)], [], [lanc()], [reg(valor=140.0)])
    item = r.itens[0]
    assert item.lancamento.status == STATUS_OK
    assert item.arquivo.status == STATUS_DIVERG
    assert "valor" in item.arquivo.detalhe.lower()
    assert item.veredito == "ressalva"


def test_multiplos_candidatos_escolhe_o_que_casa():
    # dois lançamentos com a mesma chave (nº+CNPJ): um diverge, o outro casa
    # tudo → a frente deve varrer os candidatos e resultar OK, não parar no 1º.
    r = conciliar(
        [nota(emissao=date(2026, 7, 3), servico=150.0, liquido=150.0)], [],
        [lanc(emissao=date(2026, 7, 1), bruto=999.0, liquido=999.0),
         lanc(emissao=date(2026, 7, 3), bruto=150.0, liquido=150.0)],
        [reg()])
    assert r.itens[0].lancamento.status == STATUS_OK
    assert r.itens[0].veredito == "gerenciada"
