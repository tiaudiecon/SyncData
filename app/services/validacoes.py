"""Validações manuais da divergência de impostos.

O operador confirma que uma nota específica NÃO tem erro de imposto ("Marcar
como validada"). A nota sai do filtro Divergência de Impostos e passa a contar
como Gerenciada. Vale SÓ para a competência trabalhada — por isso a chave é
(competência, CNPJ, número da nota). Ver [[excecoes]] (aquela vale por CNPJ para
todas as competências; esta é pontual, por competência).
"""
from app.models import ValidacaoImposto
from app.services.normalizacao import so_digitos


def mapa(db, competencia):
    """{(cnpj_norm, numero_norm): observacao} das validações da competência."""
    if not competencia:
        return {}
    linhas = (db.query(ValidacaoImposto)
                .filter(ValidacaoImposto.competencia == competencia).all())
    return {(so_digitos(v.cnpj), so_digitos(v.numero)): (v.observacao or "")
            for v in linhas}


def salvar(db, competencia, cnpj, numero, nome, observacao):
    """Cria/atualiza a validação (idempotente por competência+CNPJ+número)."""
    cn, nn = so_digitos(cnpj), so_digitos(numero)
    if not (competencia and cn and nn):
        return None
    v = (db.query(ValidacaoImposto)
           .filter(ValidacaoImposto.competencia == competencia,
                   ValidacaoImposto.cnpj == cn,
                   ValidacaoImposto.numero == nn).first())
    if v:
        v.observacao = observacao or ""
        if nome:
            v.nome = nome
    else:
        v = ValidacaoImposto(competencia=competencia, cnpj=cn, numero=nn,
                             nome=nome or "", observacao=observacao or "")
        db.add(v)
    db.commit()
    return v


def remover(db, competencia, cnpj, numero):
    cn, nn = so_digitos(cnpj), so_digitos(numero)
    v = (db.query(ValidacaoImposto)
           .filter(ValidacaoImposto.competencia == competencia,
                   ValidacaoImposto.cnpj == cn,
                   ValidacaoImposto.numero == nn).first())
    if v:
        db.delete(v)
        db.commit()
        return True
    return False
