"""
Mappings: Centraliza lógica de normalização e mapeamento de dimensões.

Responsabilidade única: converter valores brutos em valores canônicos,
usando exclusivamente arrays de settings.
"""
import unicodedata

from .settings import (
    CHECKOUT_MAPPINGS,
    PRODUCT_MAPPINGS,
    SQUAD_MAPPINGS,
    UNKNOWN_DIMENSION,
)


def normalize_mapping_token(value: str | None) -> str:
    """
    Normaliza string para matching estável.

    Aplica: lowercase, trim, remove acentos, unifica espaços/hífens.
    """
    raw = str(value or "").strip().lower()
    if not raw:
        return ""

    # Remove acentos
    no_accents = "".join(
        ch for ch in unicodedata.normalize("NFKD", raw)
        if not unicodedata.combining(ch)
    )

    # Unifica separadores
    compact = no_accents.replace("_", " ").replace("-", " ")

    return " ".join(compact.split())


def resolve_from_mappings(
    raw_text: str | None,
    mappings: list[dict[str, object]],
    *,
    fallback: str = UNKNOWN_DIMENSION,
) -> str:
    """
    Resolve valor canônico procurando aliases no texto completo.

    Prioridade: match exato > match em substring > fallback
    """
    normalized_text = normalize_mapping_token(raw_text)
    if not normalized_text:
        return fallback

    padded_text = f" {normalized_text} "

    for entry in mappings:
        canonical = str(entry.get("value") or "").strip()
        if not canonical:
            continue

        aliases = entry.get("aliases")
        candidates = [canonical]
        if isinstance(aliases, list):
            candidates.extend(str(alias) for alias in aliases)

        for candidate in candidates:
            normalized_candidate = normalize_mapping_token(candidate)
            if not normalized_candidate:
                continue

            # Match exato (melhor prioridade)
            if normalized_text == normalized_candidate:
                return canonical

            # Match em substring com espaçamento (evita colisão)
            if f" {normalized_candidate} " in padded_text:
                return canonical

    return fallback


def resolve_squad(text: str | None) -> str:
    """Resolve squad para valor canônico usando SQUAD_MAPPINGS."""
    return resolve_from_mappings(text, SQUAD_MAPPINGS)


def resolve_checkout(text: str | None) -> str:
    """Resolve checkout para valor canônico usando CHECKOUT_MAPPINGS."""
    return resolve_from_mappings(text, CHECKOUT_MAPPINGS)


def resolve_product(text: str | None) -> str:
    """Resolve product para valor canônico usando PRODUCT_MAPPINGS."""
    return resolve_from_mappings(text, PRODUCT_MAPPINGS)


