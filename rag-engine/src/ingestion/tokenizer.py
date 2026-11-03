"""Conteo y corte por tokens, desacoplado del modelo de embeddings.

En producción se usa el tokenizer del propio modelo de embeddings (para ALIA,
el tokenizer SentencePiece de `SINAI/ALIA-MrBERT-es-biomedical-embeddings`):
así `token_count` mide exactamente lo que ALIA procesa. Los tokens especiales
([CLS]/[SEP] o equivalentes) no se cuentan.
"""

from typing import Any, Protocol


class TokenCounter(Protocol):
    name: str

    def count(self, text: str) -> int: ...

    def split(self, text: str, max_tokens: int) -> list[str]: ...


class HFTokenCounter:
    """Adaptador para cualquier tokenizer *fast* de Hugging Face."""

    def __init__(self, tokenizer: Any, name: str) -> None:
        if not getattr(tokenizer, "is_fast", False):
            raise ValueError("Se requiere un tokenizer 'fast' (necesario para offsets).")
        self._tokenizer = tokenizer
        self.name = name

    @classmethod
    def from_pretrained(cls, model_id: str) -> "HFTokenCounter":
        """Carga solo el tokenizer (sin pesos ni GPU), desde la caché de HF."""
        from transformers import AutoTokenizer

        return cls(AutoTokenizer.from_pretrained(model_id), model_id)

    def count(self, text: str) -> int:
        return len(self._encode(text)["input_ids"])

    def split(self, text: str, max_tokens: int) -> list[str]:
        """Corta en tramos de <= max_tokens, retrocediendo a un inicio de palabra."""
        offsets = self._encode(text, offsets=True)["offset_mapping"]
        pieces, start = [], 0
        while start < len(offsets):
            end = _word_boundary(text, offsets, start, min(start + max_tokens, len(offsets)))
            piece = _slice(text, offsets, start, end)
            # Re-tokenizar el tramo aislado puede variar ±1 token en el borde.
            while end - start > 1 and self.count(piece) > max_tokens:
                end -= 1
                piece = _slice(text, offsets, start, end)
            if piece:
                pieces.append(piece)
            start = end
        return pieces

    def _encode(self, text: str, offsets: bool = False) -> dict:
        # verbose=False: el texto puede superar model_max_length solo para contar.
        return self._tokenizer(
            text,
            add_special_tokens=False,
            return_offsets_mapping=offsets,
            return_attention_mask=False,
            verbose=False,
        )


def _slice(text: str, offsets: list[tuple[int, int]], start: int, end: int) -> str:
    char_end = offsets[end][0] if end < len(offsets) else len(text)
    return text[offsets[start][0]:char_end].strip()


def _word_boundary(text: str, offsets: list[tuple[int, int]], start: int, end: int) -> int:
    """Retrocede `end` (como mucho a la mitad del tramo) hasta un token que abra palabra."""
    if end >= len(offsets):
        return end
    for candidate in range(end, start + (end - start) // 2, -1):
        begin = offsets[candidate][0]
        if text[begin:begin + 1].isspace() or begin > 0 and text[begin - 1].isspace():
            return candidate
    return end


class WhitespaceTokenCounter:
    """Contador trivial por palabras para pruebas unitarias (sin descargas)."""

    name = "whitespace"

    def count(self, text: str) -> int:
        return len(text.split())

    def split(self, text: str, max_tokens: int) -> list[str]:
        words = text.split()
        return [" ".join(words[i:i + max_tokens]) for i in range(0, len(words), max_tokens)]
