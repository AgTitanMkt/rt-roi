"""
Extractors: Centraliza extração de campos de requisições Redtrack.

Responsabilidade única: extrair e normalizar dados de diferentes estruturas de API
sem depender de contexto ou lógica de negócio.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def extract_nested_field(obj: dict, *keys: str, default: str = "") -> str:
    """
    Extrai campo aninhado com fallback em cascata.
    
    Exemplo:
        extract_nested_field(row, "campaign", "id")  → row["campaign"]["id"] ou ""
        extract_nested_field(row, "campaign_id", "campaignId", "id")  → primeira encontrada
    """
    if not isinstance(obj, dict):
        return default
    
    for key in keys:
        value = obj.get(key)
        if isinstance(value, dict):
            continue
        
        result = str(value or "").strip() if value is not None else ""
        if result:
            return result
    
    return default


def extract_nested_dict_field(obj: dict, dict_key: str, *field_keys: str, default: str = "") -> str:
    """
    Extrai campo dentro de objeto aninhado.
    
    Exemplo:
        extract_nested_dict_field(row, "campaign", "id", "campaign_id")
        → row["campaign"]["id"] ou row["campaign"]["campaign_id"] ou ""
    """
    nested = obj.get(dict_key)
    if not isinstance(nested, dict):
        return default
    
    for field_key in field_keys:
        value = nested.get(field_key)
        result = str(value or "").strip() if value is not None else ""
        if result:
            return result
    
    return default


def get_campaign_id(row: dict) -> str:
    """Extrai identificador de campanha com prioridade: campaign.id → campaign_id → offer.id → offer_id."""
    # Tenta campaign aninhado
    campaign_id = extract_nested_dict_field(row, "campaign", "id", "campaign_id")
    if campaign_id:
        return campaign_id
    
    # Tenta campos simples
    campaign_id = extract_nested_field(row, "campaign_id", "campaignId")
    if campaign_id:
        return campaign_id
    
    # Fallback para offer
    offer_id = extract_nested_dict_field(row, "offer", "id", "offer_id")
    if offer_id:
        return offer_id
    
    # Tenta offer simples
    offer_id = extract_nested_field(row, "offer_id", "offerId", "oid", "cid")
    if offer_id:
        return offer_id
    
    # Último recurso: qualquer ID encontrado
    return extract_nested_field(
        row,
        "id",
        "offer",
        "campaign",
        default=""
    )


def get_campaign_name(row: dict) -> str:
    """Extrai nome de campanha com prioridade: campaign.name → campaign_name → offer.name."""
    # Tenta campaign aninhado
    campaign_name = extract_nested_dict_field(row, "campaign", "name", "campaign_name")
    if campaign_name:
        return campaign_name
    
    # Tenta campos simples
    campaign_name = extract_nested_field(row, "campaign_name", "campaign")
    if campaign_name:
        return campaign_name
    
    # Fallback para offer
    offer_name = extract_nested_dict_field(row, "offer", "name", "offer_name")
    if offer_name:
        return offer_name
    
    return extract_nested_field(row, "offer_name", "offer", default="")


def get_offer_name(row: dict) -> str:
    """Extrai nome de offer com prioridade: offer.name → offer_name."""
    offer_name = extract_nested_dict_field(row, "offer", "name", "offer_name")
    if offer_name:
        return offer_name
    
    return extract_nested_field(row, "offer_name", "offer", default="")


def get_offer_id(row: dict) -> str | None:
    """Extrai ID de offer com prioridade: offer.id → offer_id."""
    offer_id = extract_nested_dict_field(row, "offer", "id", "offer_id")
    if offer_id:
        return offer_id
    
    offer_id = extract_nested_field(row, "offer_id", "offerId", "oid", default="")
    return offer_id or None


def get_offer_kits(payload: object) -> tuple[str, str, str]:
    """
    Extrai kit 1, kit 2 e kit 3 de uma resposta do endpoint /offer.

    A API pode devolver esses campos em formatos diferentes; por isso, o parser
    percorre estruturas aninhadas e tenta tanto chaves diretas quanto listas de kits.
    """
    kit_keys = (
        ("kit1", "kit_1", "kit 1"),
        ("kit2", "kit_2", "kit 2"),
        ("kit3", "kit_3", "kit 3"),
    )

    def iter_dicts(value: object):
        if isinstance(value, dict):
            yield value
            for nested in value.values():
                if isinstance(nested, (dict, list)):
                    yield from iter_dicts(nested)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, (dict, list)):
                    yield from iter_dicts(item)

    def clean(value: object) -> str:
        return str(value or "").strip() or "unknown"

    kits = ["unknown", "unknown", "unknown"]

    for current in iter_dicts(payload):
        kits_list = current.get("kits")
        if isinstance(kits_list, list):
            for idx, item in enumerate(kits_list[:3]):
                if kits[idx] == "unknown":
                    kits[idx] = clean(item)

        for idx, keys in enumerate(kit_keys):
            if kits[idx] != "unknown":
                continue

            for key in keys:
                if key in current:
                    value = clean(current.get(key))
                    if value != "unknown":
                        kits[idx] = value
                        break

        if all(value != "unknown" for value in kits):
            break

    return kits[0], kits[1], kits[2]


def get_conversion_type(row: dict) -> Optional[str]:
    """
    Extrai e normaliza tipo de conversão.
    
    Valida contra tipos conhecidos (purchase, initiatecheckout).
    Retorna None se tipo não for reconhecido após tentativas de normalização.
    """
    # Usa apenas campos canônicos para evitar falsos positivos em type1..type40.
    candidates: list[str] = []
    for key in ("type", "event", "goal", "conversion_type", "conversionType", "event_type"):
        value = row.get(key)
        if value is None:
            continue
        normalized = str(value).strip().lower()
        if normalized:
            candidates.append(normalized)

    if not candidates:
        return None

    for raw_type in candidates:
        if raw_type == "purchase":
            return "purchase"
        if raw_type == "initiatecheckout":
            return "initiatecheckout"

        # Tentar normalizar variacoes comuns.
        if "purchase" in raw_type:
            return "purchase"
        if "initiate" in raw_type and "checkout" in raw_type:
            return "initiatecheckout"

    return None


def get_event_count(row: dict) -> int:
    """Extrai quantidade de eventos com fallback em cascata."""
    count_keys = (
        "count",
        "event_count",
        "events",
        "conversions",
        "total",
        "value",
        "qty",
        "amount",
    )
    
    for key in count_keys:
        raw = row.get(key)
        if raw is None:
            continue
        try:
            numeric = float(str(raw).strip())
            return max(int(numeric), 0)
        except (TypeError, ValueError):
            continue
    
    return 1


def build_mapping_source_text(*values: str) -> str:
    """
    Combina múltiplas fontes de nome para mapeamento.
    
    Remove duplicatas após normalização, preserva ordem original.
    """
    # Importar aqui para evitar circular import
    from .mappings import normalize_mapping_token
    
    unique_values: list[str] = []
    seen: set[str] = set()
    
    for value in values:
        clean = str(value or "").strip()
        if not clean:
            continue
        
        normalized = normalize_mapping_token(clean)
        if normalized and normalized not in seen:
            unique_values.append(clean)
            seen.add(normalized)
    
    return " | ".join(unique_values)

