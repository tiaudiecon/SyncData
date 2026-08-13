import uuid

_JOBS: "dict[str, dict]" = {}


def criar_job(total: int = 0) -> str:
    jid = uuid.uuid4().hex
    _JOBS[jid] = {"fase": "ocr", "atual": 0, "total": total,
                  "conciliacao_id": None, "erro": None}
    return jid


def atualizar(job_id: str, **kw) -> None:
    job = _JOBS.get(job_id)
    if job is not None:
        job.update(kw)


def estado(job_id: str) -> "dict | None":
    return _JOBS.get(job_id)
