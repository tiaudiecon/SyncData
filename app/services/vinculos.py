from app.models import Vinculo
from app.services.normalizacao import so_digitos


def mapa(db, competencia):
    """{(cnpj_norm, numero_norm) da NOTA: {sp_cnpj, sp_numero, sp_valor, obs}}."""
    if not competencia:
        return {}
    linhas = db.query(Vinculo).filter(Vinculo.competencia == competencia).all()
    return {(so_digitos(v.cnpj), so_digitos(v.numero)): {
        "sp_cnpj": so_digitos(v.sp_cnpj), "sp_numero": so_digitos(v.sp_numero),
        "sp_valor": v.sp_valor, "obs": v.observacao or ""} for v in linhas}


def salvar(db, competencia, cnpj, numero, nome, sp_cnpj, sp_numero, sp_valor, observacao):
    cn, nn = so_digitos(cnpj), so_digitos(numero)
    if not (competencia and cn and nn):
        return None
    v = (db.query(Vinculo).filter(Vinculo.competencia == competencia,
                                  Vinculo.cnpj == cn, Vinculo.numero == nn).first())
    if v:
        v.sp_cnpj, v.sp_numero, v.sp_valor = so_digitos(sp_cnpj), so_digitos(sp_numero), float(sp_valor or 0.0)
        v.observacao = observacao or ""
        if nome:
            v.nome = nome
    else:
        v = Vinculo(competencia=competencia, cnpj=cn, numero=nn,
                    sp_cnpj=so_digitos(sp_cnpj), sp_numero=so_digitos(sp_numero),
                    sp_valor=float(sp_valor or 0.0), nome=nome or "", observacao=observacao or "")
        db.add(v)
    db.commit()
    return v


def remover(db, competencia, cnpj, numero):
    cn, nn = so_digitos(cnpj), so_digitos(numero)
    v = (db.query(Vinculo).filter(Vinculo.competencia == competencia,
                                  Vinculo.cnpj == cn, Vinculo.numero == nn).first())
    if v:
        db.delete(v); db.commit(); return True
    return False
