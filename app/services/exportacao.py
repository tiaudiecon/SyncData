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

_MOEDA = 'R$ #,##0.00'
CABECALHOS = ["Nº NF", "Fornecedor", "Emissão",
              "Bruto (Sieg)", "Líq (Sieg)", "Imp (Sieg)",
              "Bruto (SPData)", "Líq (SPData)", "Imp (SPData)",
              "Desc?", "Lançamento", "Arquivo", "Divergências", "Veredito"]
_COLS_MOEDA = (4, 5, 6, 7, 8, 9)          # 1-based: as 6 colunas de valor
_COL_STATUS = (11, 12)                     # Lançamento, Arquivo


def _linha_item(it):
    return [it["numero"], it["nome_fornecedor"], it["data_emissao"],
            it.get("sieg_bruto", 0.0), it.get("sieg_liquido", 0.0), it.get("sieg_imp", 0.0),
            it.get("sp_bruto"), it.get("sp_liquido"), it.get("sp_imp"),
            "Sim" if it.get("tem_desconto") else "",
            _ROTULO_STATUS.get(it["status_lancamento"], it["status_lancamento"]),
            _ROTULO_STATUS.get(it["status_arquivo"], it["status_arquivo"]),
            it.get("detalhe", ""), it["veredito"].capitalize()]


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
            if c in _COLS_MOEDA and isinstance(valor, (int, float)):
                cel.number_format = _MOEDA
        for col, chave in ((_COL_STATUS[0], it["status_lancamento"]),
                           (_COL_STATUS[1], it["status_arquivo"])):
            fill, fonte = _FILL_STATUS.get(chave, (None, _FONTE_DADO))
            if fill:
                ws.cell(r, col).fill = fill
                ws.cell(r, col).font = fonte
    _largura(ws, CABECALHOS, [[""] * len(CABECALHOS)] + linhas)


CAB_IMP = ["Nº NF", "Fornecedor",
           "ISS Sieg", "ISS SP", "INSS Sieg", "INSS SP", "IRRF Sieg", "IRRF SP",
           "CSRF Sieg", "CSRF SP", "Descontos", "Base Cálc.", "Alíquota",
           "Total Sieg", "Total SP"]


def _aba_impostos(ws, itens):
    for c, t in enumerate(CAB_IMP, start=1):
        cel = ws.cell(1, c, t); cel.font = _FONTE_CAB; cel.fill = _FILL_CAB; cel.alignment = _CENTRO
    ws.freeze_panes = "A2"
    for off, it in enumerate(itens):
        s = (it.get("impostos") or {}).get("sieg") or {}
        p = (it.get("impostos") or {}).get("spdata") or {}
        vals = [it["numero"], it["nome_fornecedor"],
                s.get("iss", 0), p.get("iss"), s.get("inss", 0), p.get("inss"),
                s.get("ir", 0), p.get("ir"), s.get("csrf", 0), p.get("csrf"),
                s.get("descontos", 0), s.get("base_calculo", 0), s.get("aliquota", 0),
                s.get("total", 0), p.get("total")]
        r = 2 + off
        for c, v in enumerate(vals, start=1):
            cel = ws.cell(r, c, v); cel.font = _FONTE_DADO; cel.border = _BORDA
            if off % 2 == 1:
                cel.fill = _FILL_ZEBRA
            if c >= 3 and c != 13 and isinstance(v, (int, float)):   # 13 = Alíquota (não é moeda)
                cel.number_format = _MOEDA
    _largura(ws, CAB_IMP, [[c] for c in CAB_IMP])


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
    _aba_impostos(wb.create_sheet("Impostos"), itens)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
