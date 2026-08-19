from app.services.recalculo import pendencia_sieg, esperado

ALIQ = {"irpj": 1.50, "consolidado": 4.65}


def test_sieg_correto_sem_pendencia():
    sieg = {"ir": 150.0, "csrf": 465.0, "optante_sn": False}
    pend, itens = pendencia_sieg(sieg, 10000.0, ALIQ)   # 1,5% e 4,65% de 10.000
    assert pend is False and itens == []


def test_sieg_divergente_vira_pendencia():
    sieg = {"ir": 100.0, "csrf": 465.0, "optante_sn": False}   # IRPJ deveria ser 150
    pend, itens = pendencia_sieg(sieg, 10000.0, ALIQ)
    assert pend is True
    assert itens[0]["nome"] == "IRPJ" and itens[0]["esperado"] == 150.0
    assert itens[0]["apurado"] == 100.0


def test_simples_nacional_dispensado():
    # SN: esperado 0; se o SIEG não reteve, OK
    sieg = {"ir": 0.0, "csrf": 0.0, "optante_sn": True}
    assert pendencia_sieg(sieg, 10000.0, ALIQ) == (False, [])
    # SN mas o SIEG reteve -> anomalia -> pendência
    sieg2 = {"ir": 150.0, "csrf": 0.0, "optante_sn": True}
    pend, itens = pendencia_sieg(sieg2, 10000.0, ALIQ)
    assert pend is True and itens[0]["esperado"] == 0.0


def test_dispensa_valor_pequeno_e_faculdade():
    # base 500: IRPJ esperado 7,50 (<= R$ 10) — a dispensa é FACULDADE: reter o
    # valor certo OU não reter, ambos corretos.
    assert esperado(500.0, 1.50, False) == 7.50        # esperado cheio, NÃO zera
    assert esperado(500.0, 4.65, False) == 23.25
    # 1) cliente NÃO reteve (dispensa exercida) -> OK
    assert pendencia_sieg({"ir": 0.0, "csrf": 23.25, "optante_sn": False},
                          500.0, ALIQ) == (False, [])
    # 2) cliente reteve o valor certo 7,50 -> OK (era o bug: apontava divergência)
    assert pendencia_sieg({"ir": 7.50, "csrf": 23.25, "optante_sn": False},
                          500.0, ALIQ) == (False, [])
    # 3) cliente reteve valor errado (nem 0, nem 7,50) -> pendência
    pend, itens = pendencia_sieg({"ir": 5.00, "csrf": 23.25, "optante_sn": False},
                                 500.0, ALIQ)
    assert pend is True and itens[0]["esperado"] == 7.50 and itens[0]["apurado"] == 5.00
