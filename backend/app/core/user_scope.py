"""Regras de escopo de dados por usuário (setor/squads)."""

USERNAME_ADMIN = "Admin"

USER_SECTOR_SCOPE: dict[str, str] = {
    "native": "nt",
    "youtube": "yt",
    "facebook": "fb",
}

USER_SECTOR_SQUADS: dict[str, tuple[str, ...]] = {
    "nt": ("NTE",),
    "yt": ("YTS", "YTF"),
    "fb": ("FB",),
}


def resolve_user_sector(username: str | None) -> str | None:
    """Resolve o setor canônico a partir do username (ou do próprio setor)."""
    normalized = str(username or "").strip().lower()
    if not normalized or normalized == USERNAME_ADMIN.lower():
        return None

    if normalized in USER_SECTOR_SQUADS:
        return normalized

    return USER_SECTOR_SCOPE.get(normalized)


def resolve_user_squad_scope(username_or_sector: str | None) -> tuple[str, ...] | None:
    """Retorna a lista de squads permitidos para o setor/usuário informado."""
    sector = resolve_user_sector(username_or_sector)
    if not sector:
        return None
    return USER_SECTOR_SQUADS.get(sector)

