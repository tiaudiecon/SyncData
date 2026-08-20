"""Exceções de fornecedor para a regra de recálculo (item 6).

Um fornecedor na lista de exceções tem a divergência de impostos considerada
ESPERADA (grupo dispensado de recolhimento). Vale por CNPJ, para todas as
conciliações — inclusive as futuras.
"""
from app.models import ExcecaoFornecedor
from app.services.normalizacao import so_digitos


def listar(db):
    return (db.query(ExcecaoFornecedor)
              .order_by(ExcecaoFornecedor.nome.asc()).all())


def mapa_cnpjs(db):
    """{cnpj_normalizado: observacao} — para marcar as notas rapidamente."""
    return {so_digitos(e.cnpj): (e.observacao or "") for e in db.query(ExcecaoFornecedor).all()}


def obter(db, id_):
    return db.query(ExcecaoFornecedor).filter(ExcecaoFornecedor.id == id_).first()


def salvar(db, cnpj, nome, observacao):
    """Cria ou atualiza a exceção do CNPJ (idempotente por CNPJ)."""
    c = so_digitos(cnpj)
    if not c:
        return None
    e = db.query(ExcecaoFornecedor).filter(ExcecaoFornecedor.cnpj == c).first()
    if e:
        e.observacao = observacao or ""
        if nome:
            e.nome = nome
    else:
        e = ExcecaoFornecedor(cnpj=c, nome=nome or "", observacao=observacao or "")
        db.add(e)
    db.commit()
    return e


def atualizar(db, id_, nome, observacao):
    e = obter(db, id_)
    if e:
        e.nome = nome or e.nome
        e.observacao = observacao or ""
        db.commit()
    return e


def remover(db, id_):
    e = obter(db, id_)
    if e:
        db.delete(e)
        db.commit()
        return True
    return False
