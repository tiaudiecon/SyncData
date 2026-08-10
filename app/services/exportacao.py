import io
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

_NAVY = "FF1C2B5E"
_BRANCO = "FFFFFFFF"
_CREME = "FFF4F0E5"
_LINHA = "FFD9D4C6"
_TINTA = "FF15182B"

_FILL_STATUS = {
    "ok": (PatternFill("solid", fgColor="FFE4F1EA"), Font(color="FF1A6E4A", size=10)),
    "diverg": (PatternFill("solid", fgColor="FFF8EED7"), Font(color="FFB0791E", size=10)),
    "falta": (PatternFill("solid", fgColor="FFF6E0DA"), Font(color="FFA8331C", size=10)),
}
_ROTULO_STATUS = {"ok": "OK", "diverg": "Divergência", "falta": "Não encontrada"}

_FONTE_CAB = Font(bold=True, color=_BRANCO, size=11)
_FILL_CAB = PatternFill("solid", fgColor=_NAVY)
_FILL_ZEBRA = PatternFill("solid", fgColor=_CREME)
_FONTE_DADO = Font(color=_TINTA, size=10)
_BORDA = Border(bottom=Side(style="thin", color=_LINHA))
_CENTRO = Alignment(vertical="center")

CABECALHOS = ["Nº NF", "Fornecedor", "Emissão", "Valor Bruto", "Valor Líquido",
              "Lançamento", "Arquivo", "Divergências", "Veredito"]


def _linha_item(it):
    detalhes = "; ".join(d for d in (it["detalhe_lancamento"], it["detalhe_arquivo"]) if d)
    return [it["numero"], it["nome_fornecedor"], it["data_emissao"],
            it["valor_bruto"], it["valor_liquido"],
            _ROTULO_STATUS.get(it["status_lancamento"], it["status_lancamento"]),
            _ROTULO_STATUS.get(it["status_arquivo"], it["status_arquivo"]),
            detalhes, it["veredito"].capitalize()]


def _largura(ws, cabecalhos, linhas):
    for i in range(1, len(cabecalhos) + 1):
        maior = max([len(str(cabecalhos[i - 1]))]
                    + [len(str(l[i - 1])) for l in linhas if i - 1 < len(l)] + [8])
        ws.column_dimensions[get_column_letter(i)].width = min(maior + 2, 55)


def _escrever_aba(ws, itens, com_totais=None):
    linha_atual = 1
    if com_totais:
        for rotulo, valor in com_totais:
            ws.cell(linha_atual, 1, rotulo).font = Font(bold=True, color=_NAVY, size=10)
            ws.cell(linha_atual, 2, valor).font = _FONTE_DADO
            linha_atual += 1
        linha_atual += 1  # linha em branco

    for c, texto in enumerate(CABECALHOS, start=1):
        cel = ws.cell(linha_atual, c, texto)
        cel.font = _FONTE_CAB
        cel.fill = _FILL_CAB
        cel.alignment = _CENTRO
    ws.freeze_panes = ws.cell(linha_atual + 1, 1)
    primeira_dado = linha_atual + 1

    linhas = [_linha_item(it) for it in itens]
    for offset, (it, linha) in enumerate(zip(itens, linhas)):
        r = primeira_dado + offset
        for c, valor in enumerate(linha, start=1):
            cel = ws.cell(r, c, valor)
            cel.font = _FONTE_DADO
            cel.border = _BORDA
            if offset % 2 == 1:
                cel.fill = _FILL_ZEBRA
        # colore as colunas de status (6 = Lançamento, 7 = Arquivo)
        for col, chave in ((6, it["status_lancamento"]), (7, it["status_arquivo"])):
            fill, fonte = _FILL_STATUS.get(chave, (None, _FONTE_DADO))
            if fill:
                ws.cell(r, col).fill = fill
                ws.cell(r, col).font = fonte
    _largura(ws, CABECALHOS, [[""] * len(CABECALHOS)] + linhas)


def gerar_xlsx(resumo: dict, itens: list) -> bytes:
    wb = openpyxl.Workbook()
    ws1 = wb.active
    ws1.title = "Conciliação"
    totais = [
        ("CNPJ do cliente", resumo["cnpj"]),
        ("Gerado em", resumo["data_hora"]),
        ("Total de notas (Sieg)", resumo["total_universo"]),
        ("Valor total (bruto)", resumo["valor_total"]),
        ("Gerenciadas", resumo["qt_gerenciadas"]),
        ("Com ressalva", resumo["qt_ressalva"]),
        ("Faltou lançar", resumo["qt_falta_lancar"]),
        ("Faltou arquivar", resumo["qt_falta_arquivar"]),
        ("Canceladas (informativo)", resumo["qt_canceladas"]),
    ]
    _escrever_aba(ws1, itens, com_totais=totais)
    _escrever_aba(wb.create_sheet("Faltou Lançar"),
                  [i for i in itens if i["status_lancamento"] == "falta"])
    _escrever_aba(wb.create_sheet("Faltou Arquivar"),
                  [i for i in itens if i["status_arquivo"] == "falta"])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
