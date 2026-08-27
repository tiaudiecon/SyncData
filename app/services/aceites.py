"""Aceite manual de divergência de VALOR (Sieg×SPData) ou de ARQUIVO.

O operador confirma que a nota está correta apesar de não bater — veredito
`ressalva` (valor/arquivo diverge) ou `pendente` (faltou lançar/arquivar). A nota
sai de Erro e passa a contar como Gerenciada, destravando a exportação. Vale SÓ
para a competência trabalhada — chave (competência, CNPJ, número). Ortogonal à
divergência de impostos (essa é tratada por [[validacoes]]/[[excecoes]]).
"""
from app.models import AceiteDivergencia
from app.services.normalizacao import so_digitos


def mapa(db, competencia):
    """{(cnpj_norm, numero_norm): observacao} dos aceites da competência."""
    if not competencia:
        return {}
    linhas = (db.query(AceiteDivergencia)
                .filter(AceiteDivergencia.competencia == competencia).all())
    return {(so_digitos(a.cnpj), so_digitos(a.numero)): (a.observacao or "")
            for a in linhas}


def salvar(db, competencia, cnpj, numero, nome, observacao):
    """Cria/atualiza o aceite (idempotente por competência+CNPJ+número)."""
    cn, nn = so_digitos(cnpj), so_digitos(numero)
    if not (competencia and cn and nn):
        return None
    a = (db.query(AceiteDivergencia)
           .filter(AceiteDivergencia.competencia == competencia,
                   AceiteDivergencia.cnpj == cn,
                   AceiteDivergencia.numero == nn).first())
    if a:
        a.observacao = observacao or ""
        if nome:
            a.nome = nome
    else:
        a = AceiteDivergencia(competencia=competencia, cnpj=cn, numero=nn,
                              nome=nome or "", observacao=observacao or "")
        db.add(a)
    db.commit()
    return a


def remover(db, competencia, cnpj, numero):
    cn, nn = so_digitos(cnpj), so_digitos(numero)
    a = (db.query(AceiteDivergencia)
           .filter(AceiteDivergencia.competencia == competencia,
                   AceiteDivergencia.cnpj == cn,
                   AceiteDivergencia.numero == nn).first())
    if a:
        db.delete(a)
        db.commit()
        return True
    return False
