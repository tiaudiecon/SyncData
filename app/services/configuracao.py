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
