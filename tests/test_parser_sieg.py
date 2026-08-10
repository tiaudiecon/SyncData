import io
from datetime import date, datetime
import openpyxl
from app.services.parser_sieg import ler_sieg, NotaSieg

HEADERS = ["Numero", "Dt_Emissao", "Dt_Competencia", "Prestador", "RzPrestador",
           "Uf_Prest", "Mun_Prest", "Insc_Prest", "Tomador", "RzTomador",
           "Valor_Servico", "Valor_Liquido", "Dt_Cancelamento", "Status"]
CLIENTE = "04541288000162"


def _linha(numero, prestador, nome, emissao, servico, liquido,
           tomador=CLIENTE, dt_cancel=None, status="Autorizado o uso da NFS-e"):
    base = {"Numero": numero, "Dt_Emissao": emissao, "Prestador": prestador,
            "RzPrestador": nome, "Tomador": tomador, "Valor_Servico": servico,
            "Valor_Liquido": liquido, "Dt_Cancelamento": dt_cancel, "Status": status}
    return [base.get(h) for h in HEADERS]


def _xlsx(*linhas):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(HEADERS)
    for ln in linhas:
        ws.append(ln)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def test_filtra_tomador_cliente():
    arq = _xlsx(
        _linha("4291", "11111111000111", "FORNEC A", datetime(2026, 7, 3), 150, 150),
        _linha("4269", "22222222000122", "FORNEC B", datetime(2026, 7, 3), 100, 100,
               tomador="99999999000199"),  # outro tomador: ignora
    )
    autorizadas, canceladas = ler_sieg(arq, CLIENTE)
    assert len(autorizadas) == 1
    assert autorizadas[0].numero == "4291"
    assert autorizadas[0].cnpj_prestador == "11111111000111"
    assert autorizadas[0].emissao == date(2026, 7, 3)
    assert autorizadas[0].valor_servico == 150.0
    assert canceladas == []


def test_separa_canceladas():
    arq = _xlsx(
        _linha("500", "11111111000111", "FORNEC A", datetime(2026, 7, 1), 10, 10),
        _linha("501", "11111111000111", "FORNEC A", datetime(2026, 7, 2), 20, 20,
               dt_cancel=datetime(2026, 7, 5), status="Cancelada"),
    )
    autorizadas, canceladas = ler_sieg(arq, CLIENTE)
    assert [n.numero for n in autorizadas] == ["500"]
    assert [n.numero for n in canceladas] == ["501"]
    assert canceladas[0].cancelada is True
