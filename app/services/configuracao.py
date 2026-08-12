from app.models import Config
from app.services.normalizacao import so_digitos


def obter_config(db):
    cfg = db.query(Config).first()
    if cfg is None:
        cfg = Config(cnpj_cliente="", configurado=False)
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


def esta_configurado(db) -> bool:
    cfg = db.query(Config).first()
    return bool(cfg and cfg.configurado and cfg.cnpj_cliente)


def salvar_config(db, cnpj, razao_social):
    cfg = obter_config(db)
    cfg.cnpj_cliente = so_digitos(cnpj)
    cfg.razao_social = (razao_social or "").strip() or None
    cfg.configurado = bool(cfg.cnpj_cliente)
    db.commit()
    db.refresh(cfg)
    return cfg


def formatar_cnpj(cnpj):
    """00000000000000 -> 00.000.000/0000-00 (devolve o original se não tiver 14)."""
    d = "".join(c for c in (cnpj or "") if c.isdigit())
    if len(d) == 14:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    return cnpj or ""


def contexto_cliente(db):
    """Dados do cliente ativo para o rodapé da barra lateral (base.html)."""
    cfg = obter_config(db)
    return {
        "cliente_nome": cfg.razao_social or "Cliente",
        "cliente_cnpj": formatar_cnpj(cfg.cnpj_cliente),
    }
