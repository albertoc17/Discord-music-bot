from __future__ import annotations

from typing import Any

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

API_URL = "https://www.thesportsdb.com/api/v1/json/3"
TIMEOUT = aiohttp.ClientTimeout(total=12)


class SportsAPIError(Exception):
    """The sports data provider could not answer the request."""


async def _request(endpoint: str, params: dict[str, str]) -> dict[str, Any]:
    try:
        async with (
            aiohttp.ClientSession(timeout=TIMEOUT) as session,
            session.get(f"{API_URL}/{endpoint}", params=params) as response,
        ):
            if response.status == 429:
                raise SportsAPIError("Límite de consultas alcanzado; prueba de nuevo en un minuto.")
            if response.status != 200:
                raise SportsAPIError("El proveedor deportivo no está disponible por ahora.")
            payload = await response.json(content_type=None)
    except (aiohttp.ClientError, TimeoutError) as exc:
        raise SportsAPIError("No pude conectarme al proveedor de resultados.") from exc
    if not isinstance(payload, dict):
        raise SportsAPIError("El proveedor devolvió una respuesta inesperada.")
    return payload


async def _list(endpoint: str, key: str, params: dict[str, str]) -> list[dict[str, Any]]:
    payload = await _request(endpoint, params)
    return [item for item in (payload.get(key) or []) if isinstance(item, dict)]


async def search_events(query: str) -> list[dict[str, Any]]:
    return await _list("searchevents.php", "event", {"e": query})


async def search_leagues(query: str) -> list[dict[str, Any]]:
    return await _list("search_all_leagues.php", "countries", {"s": "Soccer", "c": query})


async def league_table(league_id: str, season: str | None) -> list[dict[str, Any]]:
    params = {"l": league_id}
    if season:
        params["s"] = season
    return await _list("lookuptable.php", "table", params)


async def league_events(league_id: str, upcoming: bool) -> list[dict[str, Any]]:
    endpoint = "eventsnextleague.php" if upcoming else "eventspastleague.php"
    return await _list(endpoint, "events", {"id": league_id})


async def search_players(query: str) -> list[dict[str, Any]]:
    return await _list("searchplayers.php", "player", {"p": query})


def _text(item: dict[str, Any], key: str, fallback: str = "Sin dato") -> str:
    value = item.get(key)
    return str(value).strip() if value not in (None, "") else fallback


def _event_embed(event: dict[str, Any]) -> discord.Embed:
    home = _text(event, "strHomeTeam", "Local")
    away = _text(event, "strAwayTeam", "Visita")
    home_score, away_score = event.get("intHomeScore"), event.get("intAwayScore")
    score = (
        f"{home_score}-{away_score}" if home_score is not None and away_score is not None else "vs."
    )
    embed = discord.Embed(title=f"{home} {score} {away}", color=discord.Color.green())
    league = _text(event, "strLeague", "Competición sin especificar")
    round_name = event.get("intRound")
    embed.description = f"**{league}**" + (f" · Jornada {round_name}" if round_name else "")
    embed.add_field(name="Estado", value=_text(event, "strStatus", "Programado"), inline=True)
    date = _text(event, "dateEvent", "Sin fecha")
    embed.add_field(name="Fecha", value=f"{date} {event.get('strTime') or ''}".strip(), inline=True)
    if event.get("strVenue"):
        embed.add_field(name="Estadio", value=str(event["strVenue"]), inline=False)
    return embed


def _table_embed(rows: list[dict[str, Any]], league: str, season: str | None) -> discord.Embed:
    lines = []
    for row in rows[:20]:
        rank = _text(row, "intRank", "-")
        name = discord.utils.escape_markdown(_text(row, "strTeam", "Equipo"))
        played = _text(row, "intPlayed", "-")
        goal_difference = _text(row, "intGoalDifference", "-")
        points = _text(row, "intPoints", "-")
        lines.append(
            f"`{rank:>2}` **{name}** · PJ {played} · DG {goal_difference} · **{points} pts**"
        )
    description = f"Temporada {season}" if season else "Temporada actual"
    return discord.Embed(
        title=f"Tabla · {league}",
        description=description + "\n" + "\n".join(lines),
        color=discord.Color.blue(),
    )


class Sports(commands.Cog):
    """Consultas de fútbol: partidos, tablas, calendario y jugadores."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _resolve_league(self, query: str) -> dict[str, Any] | None:
        leagues = await search_leagues(query)
        if not leagues:
            return None
        normalized = query.casefold()
        return next(
            (row for row in leagues if _text(row, "strLeague").casefold() == normalized),
            leagues[0],
        )

    @app_commands.command(name="partido", description="Busca partidos por equipo o encuentro")
    @app_commands.describe(consulta="Ejemplo: Arsenal vs Chelsea")
    async def partido(self, interaction: discord.Interaction, consulta: str) -> None:
        await interaction.response.defer(thinking=True)
        try:
            events = await search_events(consulta.strip())
        except SportsAPIError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return
        if not events:
            await interaction.followup.send("No encontré ese partido.", ephemeral=True)
            return
        await interaction.followup.send(
            content=f"Partidos para **{discord.utils.escape_markdown(consulta)}** (hasta 5):",
            embeds=[_event_embed(event) for event in events[:5]],
        )

    @app_commands.command(name="tabla", description="Muestra la tabla de posiciones de una liga")
    @app_commands.describe(
        liga="Ejemplo: English Premier League",
        temporada="Opcional, formato 2025-2026",
    )
    async def tabla(
        self, interaction: discord.Interaction, liga: str, temporada: str | None = None
    ) -> None:
        await interaction.response.defer(thinking=True)
        try:
            found = await self._resolve_league(liga.strip())
            if not found:
                await interaction.followup.send(f"No encontré la liga **{liga}**.", ephemeral=True)
                return
            rows = await league_table(str(found.get("idLeague", "")), temporada)
        except SportsAPIError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return
        if not rows:
            await interaction.followup.send(
                "No hay tabla para esa liga o temporada en la fuente gratuita.", ephemeral=True
            )
            return
        await interaction.followup.send(
            embed=_table_embed(rows, _text(found, "strLeague", liga), temporada)
        )

    @app_commands.command(name="calendario", description="Muestra próximos partidos o resultados")
    @app_commands.describe(liga="Nombre de la liga", anteriores="Mostrar partidos anteriores")
    async def calendario(
        self, interaction: discord.Interaction, liga: str, anteriores: bool = False
    ) -> None:
        await interaction.response.defer(thinking=True)
        try:
            found = await self._resolve_league(liga.strip())
            if not found:
                await interaction.followup.send(f"No encontré la liga **{liga}**.", ephemeral=True)
                return
            events = await league_events(str(found.get("idLeague", "")), not anteriores)
        except SportsAPIError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return
        if not events:
            await interaction.followup.send(
                "No hay partidos disponibles para esa liga.", ephemeral=True
            )
            return
        heading = "Resultados recientes" if anteriores else "Próximos partidos"
        await interaction.followup.send(
            content=f"{heading} · {_text(found, 'strLeague', liga)}",
            embeds=[_event_embed(event) for event in events[:5]],
        )

    @app_commands.command(name="jugador", description="Busca la ficha de un jugador")
    @app_commands.describe(nombre="Nombre del jugador")
    async def jugador(self, interaction: discord.Interaction, nombre: str) -> None:
        await interaction.response.defer(thinking=True)
        try:
            players = await search_players(nombre.strip())
        except SportsAPIError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return
        if not players:
            await interaction.followup.send(f"No encontré al jugador **{nombre}**.", ephemeral=True)
            return
        player = players[0]
        embed = discord.Embed(
            title=_text(player, "strPlayer", nombre),
            description="Ficha de jugador",
            color=discord.Color.gold(),
        )
        for label, key in (
            ("Equipo", "strTeam"),
            ("Posición", "strPosition"),
            ("Nacionalidad", "strNationality"),
            ("Nacimiento", "dateBorn"),
        ):
            if player.get(key):
                embed.add_field(name=label, value=str(player[key]), inline=True)
        embed.set_footer(text="Las estadísticas de temporada pueden no estar disponibles.")
        await interaction.followup.send(embed=embed)
