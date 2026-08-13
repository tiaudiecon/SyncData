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


def test_data_do_spdata_e_ignorada():
    # A data do SpData é a de lançamento (não de emissão), então diferença de
    # data NÃO gera divergência na frente de lançamento — se os valores batem,
    # é 🟢. (A do Renew, essa sim, continua conferida — teste abaixo.)
    r = conciliar([nota(emissao=date(2026, 7, 3))],
                  [], [lanc(emissao=date(2026, 7, 25))], [reg()])
    item = r.itens[0]
    assert item.lancamento.status == STATUS_OK
    assert item.veredito == "gerenciada"


def test_data_do_renew_ainda_conta():
    # No Renew a data é a de emissão de verdade → diferença vira divergência.
    r = conciliar([nota(emissao=date(2026, 7, 3))],
                  [], [lanc()], [reg(emissao=date(2026, 7, 25))])
    item = r.itens[0]
    assert item.lancamento.status == STATUS_OK
    assert item.arquivo.status == STATUS_DIVERG
    assert "data" in item.arquivo.detalhe.lower()
    assert item.veredito == "ressalva"


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


def test_numero_composto_casa_por_sufixo():
    # Sieg/Renew trazem o número composto '2600000002098'; o SpData guarda '2098'.
    # Com o mesmo CNPJ e o valor batendo, é a mesma nota → 🟢.
    r = conciliar([nota(numero="2600000002098", servico=150.0, liquido=150.0)],
                  [], [lanc(numero="2098", bruto=150.0, liquido=150.0)],
                  [reg(numero="2600000002098", valor=150.0)])
    item = r.itens[0]
    assert item.lancamento.status == STATUS_OK
    assert item.arquivo.status == STATUS_OK
    assert item.veredito == "gerenciada"


def test_sufixo_so_vale_quando_o_valor_bate():
    # Número casa por sufixo, mas o valor NÃO bate → não é aceito como a mesma
    # nota (guarda contra falso-positivo) → faltou lançar.
    r = conciliar([nota(numero="2600000002098", servico=150.0, liquido=150.0)],
                  [], [lanc(numero="2098", bruto=999.0, liquido=999.0)], [])
    assert r.itens[0].lancamento.status == STATUS_FALTA


def test_sufixo_tail_curto_de_composto_casa():
    # Mesmo tail curto (ex.: '18') casa quando o número longo é claramente
    # composto (prefixo grande) e o valor bate — caso real do Sieg.
    r = conciliar([nota(numero="2026000000018", servico=150.0, liquido=150.0)],
                  [], [lanc(numero="18", bruto=150.0, liquido=150.0)], [])
    assert r.itens[0].lancamento.status == STATUS_OK


def test_sufixo_nao_casa_numeros_curtos_parecidos():
    # '5' NÃO casa com '125' (diferença de tamanho pequena) mesmo com valor
    # batendo — evita falso-positivo entre números curtos distintos.
    r = conciliar([nota(numero="125", servico=150.0, liquido=150.0)],
                  [], [lanc(numero="5", bruto=150.0, liquido=150.0)], [])
    assert r.itens[0].lancamento.status == STATUS_FALTA


def test_desconto_nao_gera_divergencia():
    # Sieg bruto 10000, desconto 615 -> ajustado 9385. Os lados registram bases
    # diferentes (confirmado com dados reais): o SPData lança LÍQUIDO do desconto
    # (9385), e o Renew guarda o BRUTO cheio (10000). Nenhuma frente diverge.
    n = NotaSieg("100", "100", "11111111000111", "F", date(2026, 7, 3),
                 10000.0, 9385.0, False, deducoes=615.0)
    l = LancamentoSpData("100", "100", "11111111000111", "F", date(2026, 7, 3),
                         9385.0, 9385.0)
    r = conciliar([n], [], [l], [reg(valor=10000.0)])
    item = r.itens[0]
    assert item.lancamento.status == STATUS_OK
    assert item.arquivo.status == STATUS_OK
    assert item.veredito == "gerenciada"


def test_item_carrega_linha_spdata_casada():
    r = conciliar([nota()], [], [lanc()], [reg()])
    assert r.itens[0].lancamento_row is not None
    assert r.itens[0].lancamento_row.cnpj == "11111111000111"


def test_faltou_lancar_sem_linha_spdata():
    r = conciliar([nota()], [], [], [reg()])
    assert r.itens[0].lancamento_row is None


def test_renew_aceita_valor_bruto_mesmo_com_desconto():
    # Sieg bruto 10000, desconto 615 -> ajustado 9385. Se o Renew guardar o
    # valor CHEIO (10000), ainda assim é a mesma nota (não diverge).
    n = NotaSieg("100", "100", "11111111000111", "F", date(2026, 7, 3),
                 10000.0, 9385.0, False, deducoes=615.0)
    l = LancamentoSpData("100", "100", "11111111000111", "F", date(2026, 7, 3),
                         9385.0, 9385.0)
    r = conciliar([n], [], [l], [reg(valor=10000.0)])   # Renew com o bruto cheio
    assert r.itens[0].arquivo.status == STATUS_OK
