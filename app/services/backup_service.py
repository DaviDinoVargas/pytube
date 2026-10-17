import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app import APP_VERSION
from app.domain.errors import StorageError
from app.repositories.base import SCHEMA_VERSION

FORMAT = "dinotube-library"
MAX_BYTES = 64 * 1024 * 1024  # um backup legítimo é bem menor; limita arquivos absurdos
KEEP_AUTOMATIC = 5
_LISTS = ("videos", "categories", "playlists", "video_categories", "playlist_items", "progress")


@dataclass(frozen=True)
class BackupInfo:
    path: Path
    kind: str
    created_at: str
    videos: int
    size: int


def validate_payload(payload):
    """Confere o conteúdo de um backup ANTES de tocar na biblioteca. Levanta StorageError('backup_invalid'|'library_unsupported')."""

    def bad(detail):
        raise StorageError("backup_invalid", detail)

    if not isinstance(payload, dict) or payload.get("format") != FORMAT:
        bad("não é um backup do DinoTube")
    version = payload.get("schema_version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        bad("versão do esquema inválida")
    if version > SCHEMA_VERSION:
        raise StorageError("library_unsupported", f"esquema {version}")
    data = payload.get("data")
    if not isinstance(data, dict):
        bad("dados ausentes")
    for key in _LISTS:
        if not isinstance(data.get(key, []), list):
            bad(f"'{key}' deve ser uma lista")
    ids = {}
    for key in ("videos", "categories", "playlists"):
        seen = set()
        for row in data.get(key, []):
            if not isinstance(row, dict) or not isinstance(row.get("id"), int) or isinstance(row.get("id"), bool):
                bad(f"item de '{key}' sem id inteiro")
            if row["id"] in seen:
                bad(f"id repetido em '{key}'")
            seen.add(row["id"])
        ids[key] = seen
    for row in data.get("videos", []):
        for field in ("source_id", "url"):
            if not isinstance(row.get(field), str) or not row[field]:
                bad(f"vídeo {row['id']} sem '{field}'")
        for field in ("title", "channel", "description", "local_path"):
            if row.get(field) is not None and not isinstance(row[field], str):
                bad(f"vídeo {row['id']}: '{field}' deve ser texto")
    for row in data.get("categories", []) + data.get("playlists", []):
        if not isinstance(row.get("name"), str) or not row["name"].strip():
            bad(f"item {row['id']} sem nome")
    for link in data.get("video_categories", []):
        if not (isinstance(link, list) and len(link) == 2 and link[0] in ids["videos"] and link[1] in ids["categories"]):
            bad("vínculo de categoria aponta para algo que não existe")
    for link in data.get("playlist_items", []):
        if not (isinstance(link, list) and len(link) == 3 and link[0] in ids["playlists"] and link[1] in ids["videos"]
                and isinstance(link[2], int)):
            bad("item de playlist aponta para algo que não existe")
    for row in data.get("progress", []):
        if not isinstance(row, dict) or row.get("video_id") not in ids["videos"]:
            bad("progresso aponta para um vídeo que não existe")
    return data


class BackupService:
    """Cópias de segurança, restauração e exportação dos dados da biblioteca (não dos vídeos)."""

    def __init__(self, library, storage):
        self._library = library
        self._storage = storage

    @property
    def folder(self):
        return self._library.layout.backups

    # -- criar ---------------------------------------------------------------------------
    def _payload(self):
        return {
            "format": FORMAT,
            "app_version": APP_VERSION,
            "schema_version": SCHEMA_VERSION,
            "kind": "",
            "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "data": self._library.store.export_data(),
        }

    def _write(self, path, payload):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)  # gravação atômica
        return path

    def create(self, kind="manual"):
        """Grava um backup em `backups/`. `kind`: manual, auto ou pre-restore."""
        payload = self._payload()
        payload["kind"] = kind
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = self.folder / f"library-{kind}-{stamp}.json"
        n = 2
        while path.exists():  # dois backups no mesmo segundo não se sobrescrevem
            path = self.folder / f"library-{kind}-{stamp}-{n}.json"
            n += 1
        self._write(path, payload)
        if kind != "manual":
            self.rotate(kind)
        return path

    def export_to(self, path):
        """Exporta os dados para um arquivo escolhido pelo usuário (mesmo formato do backup)."""
        payload = self._payload()
        payload["kind"] = "export"
        return self._write(path, payload)

    # -- listar e girar ------------------------------------------------------------------------
    def _info(self, path):
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(payload, dict) or payload.get("format") != FORMAT:
            return None
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        videos = data.get("videos", [])
        return BackupInfo(Path(path), str(payload.get("kind", "")), str(payload.get("exported_at", "")),
                          len(videos) if isinstance(videos, list) else 0, Path(path).stat().st_size)

    def list(self):
        """Backups em `backups/`, do mais recente para o mais antigo. Arquivos que não são backups são ignorados."""
        if not self.folder.is_dir():
            return []
        infos = [i for i in (self._info(p) for p in self.folder.glob("library-*.json")) if i is not None]
        return sorted(infos, key=lambda i: (i.created_at, i.path.name), reverse=True)

    def rotate(self, kind, keep=KEEP_AUTOMATIC):
        """Mantém só os `keep` backups mais recentes do tipo `kind` (backups manuais nunca são apagados)."""
        same = [i for i in self.list() if i.kind == kind]
        for info in same[keep:]:
            info.path.unlink(missing_ok=True)

    def auto_backup_if_due(self, hours=24):
        """Cria um backup automático se o último tem mais de `hours` horas (ou não existe). Ignora biblioteca vazia."""
        if not self._library.ready or self._library.store.is_empty():
            return None
        autos = [i for i in self.list() if i.kind == "auto"]
        if autos:
            try:
                last = datetime.fromisoformat(autos[0].created_at)
                if (datetime.now(timezone.utc) - last).total_seconds() < hours * 3600:
                    return None
            except ValueError:
                pass
        return self.create("auto")

    # -- restaurar -----------------------------------------------------------------------------
    def read(self, path):
        """Lê e valida um arquivo de backup, sem alterar nada. Devolve os dados prontos para importar."""
        path = Path(path)
        try:
            if path.stat().st_size > MAX_BYTES:
                raise StorageError("backup_invalid", "arquivo grande demais")
            payload = json.loads(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise StorageError("backup_unreadable", str(exc)) from exc
        except ValueError as exc:
            raise StorageError("backup_invalid", "JSON ilegível") from exc
        data = validate_payload(payload)
        merged = {key: [] for key in _LISTS}
        merged.update({key: data[key] for key in _LISTS if key in data})
        merged["schema_version"] = payload["schema_version"]
        return merged

    def restore(self, path):
        """Troca a biblioteca pelo conteúdo do backup. Antes, guarda um backup 'pre-restore' do estado atual.

        Devolve a quantidade de itens restaurados. Se algo falhar, a biblioteca atual continua intacta."""
        data = self.read(path)  # valida tudo antes de mexer em qualquer coisa
        safety = self.create("pre-restore") if not self._library.store.is_empty() else None
        try:
            self._library.store.replace_data(data)
        except StorageError:
            raise
        except Exception as exc:
            raise StorageError("backup_invalid", str(exc)) from exc
        self._library.validate_all()  # os arquivos podem não existir neste computador
        self._library.notify()
        return {"videos": len(data["videos"]), "categories": len(data["categories"]),
                "playlists": len(data["playlists"]), "safety_backup": safety}

    # -- exportar lista ------------------------------------------------------------------------
    def export_csv(self, path):
        """Lista da biblioteca em CSV (abre no Excel): título, canal, link, duração, categorias, estado e arquivo."""
        store = self._library.store
        cats = {c.id: c.name for c in store.list_categories()}
        links = {}
        for video_id, category_id in store.list_category_links():
            links.setdefault(video_id, []).append(cats.get(category_id, ""))
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8-sig") as fh:  # BOM: o Excel reconhece os acentos
            writer = csv.writer(fh)
            writer.writerow(["titulo", "canal", "link", "duracao_s", "adicionado_em", "categorias", "estado_arquivo", "arquivo", "qualidade"])
            for v in store.list_videos():
                writer.writerow([_csv_safe(v.title), _csv_safe(v.channel), v.url, v.duration or "", v.added_at,
                                 _csv_safe("; ".join(links.get(v.id, []))), v.local_status, _csv_safe(v.local_path or ""), v.local_quality or ""])
        return path


def _csv_safe(text):
    """Evita 'injeção de fórmula' no Excel: texto que começa com = + - @ vira texto literal."""
    text = text or ""
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text
