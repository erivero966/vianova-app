"""Metadatos documentales explícitos (sin inferencia automática por IA).

Cada PDF aprobado se acompaña de un JSON con el mismo nombre:

    corpus/aprobados/guia.pdf
    corpus/aprobados/guia.json  ->  {"titulo": ..., "entidad": ..., "version": ...}
"""

from dataclasses import asdict, dataclass
import json
from pathlib import Path


REQUIRED_FIELDS = ("titulo", "entidad", "version")
OPTIONAL_FIELDS = ("url_origen", "vigencia", "paginas_indice")


class MetadataError(ValueError):
    """Metadatos ausentes o inválidos."""


@dataclass(frozen=True)
class DocumentMetadata:
    titulo: str
    entidad: str
    version: str
    url_origen: str | None = None
    vigencia: str | None = None
    paginas_indice: tuple[int, ...] = ()

    @classmethod
    def from_dict(cls, data: dict) -> "DocumentMetadata":
        if not isinstance(data, dict):
            raise MetadataError("Los metadatos deben ser un objeto JSON.")
        unknown = set(data) - set(REQUIRED_FIELDS) - set(OPTIONAL_FIELDS)
        if unknown:
            raise MetadataError(f"Campos no reconocidos: {', '.join(sorted(unknown))}.")
        values = {}
        for name in REQUIRED_FIELDS:
            value = data.get(name)
            if value is None or not str(value).strip():
                raise MetadataError(f"Falta el metadato obligatorio '{name}'.")
            values[name] = str(value).strip()
        for name in ("url_origen", "vigencia"):
            value = data.get(name)
            values[name] = str(value).strip() if value is not None and str(value).strip() else None
        raw_pages = data.get("paginas_indice", [])
        if not isinstance(raw_pages, list) or any(
            isinstance(page, bool) or not isinstance(page, int) or page < 1 for page in raw_pages
        ):
            raise MetadataError("'paginas_indice' debe ser una lista de enteros positivos.")
        values["paginas_indice"] = tuple(sorted(set(raw_pages)))
        return cls(**values)

    @classmethod
    def from_json(cls, path: str | Path) -> "DocumentMetadata":
        json_path = Path(path)
        if not json_path.is_file():
            raise MetadataError(f"No existe el archivo de metadatos: {json_path}")
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise MetadataError(f"JSON inválido en {json_path.name}: {exc}") from exc
        return cls.from_dict(data)

    def to_dict(self) -> dict:
        return asdict(self)


def default_metadata_path(pdf_path: str | Path) -> Path:
    return Path(pdf_path).with_suffix(".json")
