import io
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Conciliacao
import re
from app.services.exportacao import gerar_xlsx
from app.services.pacote_dados import gerar_pacote_dados
from app.services.tempo import formatar_dt, formatar_competencia, formatar_periodo
from app.services.configuracao import contexto_cliente, obter_config

router = APIRouter()
templates = Jinja2Templates(directory="templates")
from app.services.formatacao import largura_numeros, pad_numero, registrar_filtros
from app.services import aliquotas as serv_aliquotas
from app.services import excecoes as serv_excecoes
from app.services import validacoes as serv_validacoes
from app.services import aceites as serv_aceites
from app.services.recalculo import pendencia_sieg
from app.services.normalizacao import so_digitos, valores_batem, normalizar_numero_nf
from app.services import vinculos as serv_vinculos
from collections import defaultdict
import json
registrar_filtros(templates)
_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

_SP_EXTRA = ("sp_sem_sieg", "sp_duplicada")


def _carregar(db, conciliacao_id):
    conc = db.query(Conciliacao).filter(Conciliacao.id == conciliacao_id).first()
    if not conc:
        raise HTTPException(status_code=404, detail="Conciliação não encontrada")
    return conc


def _data_iso(data_br):
    try:
        d, m, a = (data_br or "").split("/")
        return f"{a}-{m.zfill(2)}-{d.zfill(2)}"
    except ValueError:
        return None


def _fmt_cnpj(c):
    """14 dígitos -> 'XX.XXX.XXX/XXXX-XX'; senão devolve como veio."""
    d = "".join(ch for ch in str(c or "") if ch.isdigit())
    if len(d) == 14:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    if len(d) == 11:   # CPF
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
    return str(c or "")


def _par(s, p, chave):
    """Par Sieg × SP Data de um tributo (p/ o expand de impostos no Resultado)."""
    sv = s.get(chave, 0.0)
    pv = (p or {}).get(chave) if p else None
    delta = None if (sv is None or pv is None) else round(sv - pv, 2)
    return {"sieg": sv, "sp": pv, "delta": delta}


def montar_resumo_e_itens(conc, tabelas=None, excecoes=None, validacoes=None, aceites=None,
                          vinculos=None):
    tabelas = tabelas or []
    excecoes = excecoes or {}     # {cnpj_norm: obs} — exceção por CNPJ (todas as competências)
    validacoes = validacoes or {}  # {(cnpj_norm, numero_norm): obs} — validada só nesta competência
    aceites = aceites or {}        # {(cnpj_norm, numero_norm): obs} — divergência de valor/arquivo aceita (só nesta competência)
    vinculos = vinculos or {}      # {(cnpj_norm, numero_norm) da NOTA: {sp_cnpj, sp_numero, sp_valor, obs}}
    resumo = {
        "cnpj": conc.cnpj, "data_hora": formatar_dt(conc.data_hora),
        "competencia": formatar_competencia(conc.competencia),
        "competencia_raw": conc.competencia or "",   # chave p/ marcar validada
        "periodo": formatar_periodo(conc.periodo_inicio, conc.periodo_fim),   # print3
        "total_universo": conc.total_universo, "valor_total": conc.valor_total,
        "qt_canceladas": conc.qt_canceladas,
        "qt_falta_arquivar": conc.qt_falta_arquivar,
        "qt_sp_duplicadas": sum(1 for i in conc.itens if i.veredito == "sp_duplicada"),
    }
    largura = largura_numeros([i.numero for i in conc.itens])
    itens = []
    for i in conc.itens:
        detalhe = "; ".join(d for d in (i.detalhe_lancamento, i.detalhe_arquivo) if d)
        imp = json.loads(i.impostos_json) if i.impostos_json else {}
        sieg_dict = imp.get("sieg") or {}
        sp_dict = imp.get("spdata") or {}
        # CON-05: pendência do SIEG (recálculo) — só p/ notas do SIEG.
        pend, pend_itens = False, []
        if i.veredito not in ("cancelada", *_SP_EXTRA) and sieg_dict:
            aliq = serv_aliquotas.vigente_na_lista(tabelas, _data_iso(i.data_emissao))
            pend, pend_itens = pendencia_sieg(sieg_dict, i.valor_bruto, aliq)
        cnpj_norm = so_digitos(i.cnpj_fornecedor)
        numero_norm = so_digitos(i.numero)
        # item 6: exceção por CNPJ (divergência esperada, vai p/ Exceções)
        _obs_exc = excecoes.get(cnpj_norm) if pend else None
        is_excecao = pend and _obs_exc is not None
        # novo: validada manualmente (só nesta competência) -> vira Gerenciada
        _obs_val = validacoes.get((cnpj_norm, numero_norm)) if (pend and not is_excecao) else None
        is_validada = _obs_val is not None
        pend_aberta = pend and not is_excecao and not is_validada   # divergência ainda em aberto
        principal = i.veredito not in ("cancelada", *_SP_EXTRA)
        # Aceite: divergência de VALOR/ARQUIVO (ressalva/pendente) aceita manualmente
        # (só nesta competência) -> limpa o erro de lançamento/arquivo. Ortogonal ao imposto.
        _obs_ace = (aceites.get((cnpj_norm, numero_norm))
                    if i.veredito in ("ressalva", "pendente") else None)
        is_aceita = _obs_ace is not None
        erro_lanc_aberto = (i.veredito in ("ressalva", "pendente")) and not is_aceita
        # buckets (item 1): Gerenciadas x Erros. Validada/Exceção resolvem o imposto;
        # Aceite resolve valor/arquivo. Nota sem nenhum erro em aberto -> Gerenciada.
        tem_erro = principal and (erro_lanc_aberto or pend_aberta)
        eh_gerenciada = principal and not tem_erro
        p_sp = imp.get("spdata")   # None se a nota não foi lançada no SP Data
        itens.append({
            "id": i.id,
            "numero": pad_numero(i.numero, largura),
            "nome_fornecedor": i.nome_fornecedor,
            "cnpj_fornecedor": _fmt_cnpj(i.cnpj_fornecedor),   # item 3
            "data_emissao": i.data_emissao,
            "sp_data_lancamento": sp_dict.get("data_lancamento", ""),   # CON-01
            "tem_desconto": bool(i.tem_desconto),
            "sieg_bruto": i.valor_bruto, "sieg_liquido": i.valor_liquido,
            "sieg_imp": i.imp_sieg,
            "sp_bruto": i.sp_valor_bruto, "sp_liquido": i.sp_valor_liquido,
            "sp_imp": i.imp_spdata,
            "status_lancamento": i.status_lancamento, "status_arquivo": i.status_arquivo,
            "detalhe": detalhe,
            "detalhe_lancamento": i.detalhe_lancamento or "",
            "detalhe_arquivo": i.detalhe_arquivo or "",
            "veredito": i.veredito, "cancelada": bool(i.cancelada),
            "sp_extra": i.veredito in _SP_EXTRA,          # CON-02/04
            "principal": principal,
            "eh_gerenciada": eh_gerenciada, "tem_erro": tem_erro,   # item 1
            "optante_sn": bool(sieg_dict.get("optante_sn")),   # DET-02 (SN)
            "pendencia_sieg": pend_aberta,     # CON-05 (exceção/validada não contam)
            "excecao": is_excecao, "excecao_obs": _obs_exc or "",   # item 6
            "validada": is_validada, "validada_obs": _obs_val or "",   # item 1
            "aceita": is_aceita, "aceita_obs": _obs_ace or "",   # tratativa Aceita (valor/arquivo)
            "cnpj_norm": cnpj_norm, "numero_norm": numero_norm,
            # item 3: presença em cada sistema (SP Data × SIEG).
            # sp_extra (SP sem SIEG / duplicada) EXISTE no SP Data -> consta_spdata.
            "consta_spdata": (i.veredito in _SP_EXTRA) or (i.status_lancamento in ("ok", "diverg")),
            "consta_sieg": i.veredito not in _SP_EXTRA,
            "impostos": imp,
            "arquivo_pdf": i.arquivo_pdf,
            # expand de impostos no Resultado (quebra Sieg × SP Data por tributo)
            "imp_iss": _par(sieg_dict, p_sp, "iss"),
            "imp_inss": _par(sieg_dict, p_sp, "inss"),
            "imp_ir": _par(sieg_dict, p_sp, "ir"),
            "imp_csrf": _par(sieg_dict, p_sp, "csrf"),
            "imp_total": _par(sieg_dict, p_sp, "total"),
            "iss_retido": bool(sieg_dict.get("iss_retido")),
            "imp_descontos": sieg_dict.get("descontos", 0.0),
            "imp_base": sieg_dict.get("base_calculo", 0.0),
            "sem_spdata": p_sp is None,
            "fornecedor_sp": (p_sp or {}).get("fornecedor", ""),
            # item 2: CNPJ como veio do SP Data (p/ comparação com o do SIEG).
            # Conciliações antigas não têm esse campo -> cai no CNPJ do fornecedor.
            "cnpj_fornecedor_sp": _fmt_cnpj((p_sp or {}).get("cnpj") or i.cnpj_fornecedor),
            "pendencia_itens": pend_itens,
            # Vínculo manual (item-NOTA vinculado / órfão sp_sem_sieg consumido)
            "vinculada": False, "vinculo_obs": "",
            "vinculo_sp_cnpj": "", "vinculo_sp_numero": "", "vinculo_sp_valor": None,
            "vinculado": False,
        })
    # Vínculo manual (pós-passo): liga uma NOTA em erro a um órfão "sp_sem_sieg"
    # (mesmo CNPJ/número/valor do lançamento SP escolhido), compara os valores
    # persistidos e recalcula o erro da NOTA. Roda ANTES de contar os buckets
    # (Gerenciadas/Erros) para que a NOTA vinculada já reflita o novo status.
    orfaos_idx = defaultdict(list)
    for it in itens:
        if it["veredito"] == "sp_sem_sieg":
            # nº do órfão SEM zeros à esquerda (tolera o padding que vem no import)
            chave = (it["cnpj_norm"], normalizar_numero_nf(it["numero_norm"]), round(it["sp_bruto"] or 0.0, 2))
            orfaos_idx[chave].append(it)
    for (cnpj_norm, numero_norm), v in vinculos.items():
        nota = next((it for it in itens if it["principal"]
                    and it["cnpj_norm"] == cnpj_norm and it["numero_norm"] == numero_norm), None)
        if nota is None:
            continue
        chave_orf = (v["sp_cnpj"], normalizar_numero_nf(v["sp_numero"]), round(v["sp_valor"] or 0.0, 2))
        orf = next((o for o in orfaos_idx.get(chave_orf, []) if not o.get("vinculado")), None)
        if orf is None:
            continue
        divergs = []
        if not valores_batem(nota["sieg_bruto"] or 0.0, orf["sp_bruto"] or 0.0):
            divergs.append(f"bruto {nota['sieg_bruto']}≠{orf['sp_bruto']}")
        if not valores_batem(nota["sieg_liquido"] or 0.0, orf["sp_liquido"] or 0.0):
            divergs.append(f"líquido {nota['sieg_liquido']}≠{orf['sp_liquido']}")
        if not valores_batem(nota["sieg_imp"] or 0.0, orf["sp_imp"] or 0.0):
            divergs.append(f"impostos {nota['sieg_imp']}≠{orf['sp_imp']}")
        status = "diverg" if divergs else "ok"
        nota["status_lancamento"] = status
        nota["detalhe_lancamento"] = "; ".join(divergs)
        nota["vinculada"] = True
        nota["vinculo_obs"] = v["obs"]
        nota["vinculo_sp_cnpj"] = v["sp_cnpj"]
        nota["vinculo_sp_numero"] = v["sp_numero"]
        nota["vinculo_sp_valor"] = v["sp_valor"]
        # Traz os valores do lançamento vinculado para as colunas do SPData (o
        # lançamento agora EXISTE, via vínculo): bruto/líquido/impostos + consta.
        nota["sp_bruto"] = orf["sp_bruto"]
        nota["sp_liquido"] = orf["sp_liquido"]
        nota["sp_imp"] = orf["sp_imp"]
        nota["consta_spdata"] = True
        # O vínculo só resolve o lado do LANÇAMENTO; o lado do ARQUIVO (PDF)
        # pode continuar em aberto (falta/diverg) -- precisa entrar no recálculo
        # senão uma nota sem PDF arquivado seria promovida a Gerenciada. Aceite
        # cobre valor E arquivo (é a mesma tratativa de ressalva/pendente).
        arquivo_aberto = nota["status_arquivo"] in ("falta", "diverg")
        erro_lanc_aberto = ((status == "diverg") or arquivo_aberto) and not nota["aceita"]
        nota["tem_erro"] = nota["principal"] and (erro_lanc_aberto or nota["pendencia_sieg"])
        nota["eh_gerenciada"] = nota["principal"] and not nota["tem_erro"]
        orf["vinculado"] = True

    # contagens em tempo de exibição (refletem exceção/validada/vínculo atuais) — item 1
    prin = [it for it in itens if it["principal"]]
    resumo["qt_gerenciadas"] = sum(1 for it in prin if it["eh_gerenciada"])
    resumo["qt_erros"] = sum(1 for it in prin if it["tem_erro"])
    resumo["qt_divergencia"] = sum(1 for it in prin if it["pendencia_sieg"])
    resumo["qt_excecoes"] = sum(1 for it in prin if it["excecao"])
    resumo["qt_validadas"] = sum(1 for it in prin if it["validada"])
    resumo["qt_aceitas"] = sum(1 for it in prin if it["aceita"])
    resumo["qt_ressalva"] = sum(1 for it in prin if it["veredito"] == "ressalva")
    resumo["qt_falta_lancar"] = sum(1 for it in prin if it["veredito"] == "pendente")
    resumo["qt_sp_sem_sieg"] = sum(1 for it in itens
                                   if it["veredito"] == "sp_sem_sieg" and not it.get("vinculado"))
    resumo["qt_vinculadas"] = sum(1 for it in prin if it.get("vinculada"))
    return resumo, itens


def _resumo_itens(db, conc):
    """Monta resumo+itens com alíquotas, exceções, validações, aceites e vínculos da competência."""
    return montar_resumo_e_itens(
        conc, serv_aliquotas.listar(db), serv_excecoes.mapa_cnpjs(db),
        serv_validacoes.mapa(db, conc.competencia),
        serv_aceites.mapa(db, conc.competencia),
        serv_vinculos.mapa(db, conc.competencia))


@router.get("/resultado/{conciliacao_id}")
def ver(conciliacao_id: int, request: Request, db: Session = Depends(get_db)):
    conc = _carregar(db, conciliacao_id)
    resumo, itens = _resumo_itens(db, conc)
    return templates.TemplateResponse(request, "resultado.html", {
        "ativo": "resultado", "c": conc,
        "resumo": resumo, "itens": itens, **contexto_cliente(db),
    })


def _nome_arquivo(razao, competencia, conc, ext="xlsx", prefixo="SyncData"):
    """{prefixo}_{empresa}_{competência|data}.{ext} (item 2). Sem acentos."""
    import unicodedata
    sem_acento = (unicodedata.normalize("NFKD", razao or "")
                  .encode("ascii", "ignore").decode("ascii"))
    base = re.sub(r"[^A-Za-z0-9]+", "_", sem_acento.strip()).strip("_") or "Cliente"
    quando = competencia or (conc.data_hora.strftime("%Y-%m-%d") if conc.data_hora else "")
    nome = f"{prefixo}_{base}_{quando}".rstrip("_")
    return f"{nome}.{ext}"


@router.get("/resultado/{conciliacao_id}/planilha.xlsx")
def baixar(conciliacao_id: int, db: Session = Depends(get_db)):
    conc = _carregar(db, conciliacao_id)
    resumo, itens = _resumo_itens(db, conc)
    cfg = obter_config(db)
    resumo["razao_social"] = cfg.razao_social or ""      # cabeçalho do relatório
    conteudo = gerar_xlsx(resumo, itens)
    nome = _nome_arquivo(cfg.razao_social, conc.competencia, conc)
    return StreamingResponse(io.BytesIO(conteudo), media_type=_XLSX,
        headers={"Content-Disposition": f'attachment; filename="{nome}"'})


@router.get("/resultado/{conciliacao_id}/dados.json")
def exportar_dados(conciliacao_id: int, forcar: int = 0, db: Session = Depends(get_db)):
    """Item 3: pacote de dados da conciliação (para o cliente enviar e o fiscal
    importar). Liberado só quando não há mais erros (conferência concluída).
    `?forcar=1` destrava temporariamente para TESTE, mesmo com erros."""
    conc = _carregar(db, conciliacao_id)
    resumo, itens = _resumo_itens(db, conc)
    if resumo.get("qt_erros", 0) > 0 and not forcar:
        raise HTTPException(status_code=409,
            detail="A conciliação ainda tem erros — resolva-os antes de exportar os dados.")
    cfg = obter_config(db)
    resumo["razao_social"] = cfg.razao_social or ""
    pacote = gerar_pacote_dados(resumo, itens, conc)
    conteudo = json.dumps(pacote, ensure_ascii=False, indent=1).encode("utf-8")
    nome = _nome_arquivo(cfg.razao_social, conc.competencia, conc,
                         ext="syncdata.json", prefixo="SyncData_dados")
    return StreamingResponse(io.BytesIO(conteudo), media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{nome}"'})
