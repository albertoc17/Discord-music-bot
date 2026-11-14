from __future__ import annotations

from typing import Any

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

API_URL = "https://site.api.espn.com/apis"
LEAGUE = "chi.1"
TIMEOUT = aiohttp.ClientTimeout(total=15)


class SportsAPIError(Exception):
    """ESPN data could not be retrieved or parsed."""


class Sports(commands.Cog):
    """Chile Primera Division queries using ESPN's public JSON endpoints."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _get(self, path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        try:
            async with (
                aiohttp.ClientSession(timeout=TIMEOUT) as session,
                session.get(f"{API_URL}/{path.lstrip('/')}", params=params) as response,
            ):
                if response.status == 429:
                    raise SportsAPIError(
                        "ESPN limitó las consultas; espera un momento e inténtalo de nuevo."
                    )
                if response.status != 200:
                    raise SportsAPIError(f"ESPN respondió HTTP {response.status}.")
                payload = await response.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise SportsAPIError("No pude conectarme al servicio de datos de ESPN.") from exc
        if not isinstance(payload, dict):
            raise SportsAPIError("ESPN devolvió una respuesta inesperada.")
        return payload

    async def _standings(self, season: str) -> dict[str, Any]:
        return await self._get(f"v2/sports/soccer/{LEAGUE}/standings", {"season": season})

    @staticmethod
    def _groups(payload: dict[str, Any]) -> list[dict[str, Any]]:
        standings = payload.get("standings", {})
        if isinstance(standings, dict):
            return [row for row in standings.get("entries", []) if isinstance(row, dict)]
        if isinstance(standings, list):
            return [
                row
                for group in standings
                if isinstance(group, dict)
                for row in group.get("entries", [])
                if isinstance(row, dict)
            ]
        return []

    @staticmethod
    def _stats(row: dict[str, Any]) -> dict[str, Any]:
        stats = row.get("stats", [])
        return {
            item.get("name"): item.get("displayValue", item.get("value", "-"))
            for item in stats
            if isinstance(item, dict)
        }

    @staticmethod
    def _team_name(row: dict[str, Any]) -> str:
        team = row.get("team", {})
        return str(team.get("displayName") or team.get("name") or "Equipo")

    @staticmethod
    def _error_embed(error: str) -> discord.Embed:
        return discord.Embed(description=error, color=discord.Color.red())

    async def _team_row(self, name: str, season: str) -> dict[str, Any] | None:
        rows = self._groups(await self._standings(season))
        needle = name.casefold().replace("-", " ").strip()
        return next(
            (row for row in rows if needle in self._team_name(row).casefold()),
            None,
        )

    @app_commands.command(
        name="tabla", description="Tabla de posiciones de la Primera División de Chile"
    )
    @app_commands.describe(temporada="Año de temporada, por ejemplo 2026")
    async def tabla(self, interaction: discord.Interaction, temporada: str = "2026") -> None:
        await interaction.response.defer(thinking=True)
        try:
            rows = self._groups(await self._standings(temporada))
        except SportsAPIError as exc:
            await interaction.followup.send(embed=self._error_embed(str(exc)))
            return
        if not rows:
            await interaction.followup.send("ESPN no publicó la tabla para esa temporada.")
            return
        lines = []
        for row in rows[:20]:
            stats = self._stats(row)
            rank = row.get("rank", "-")
            played = stats.get("gamesPlayed", stats.get("played", "-"))
            diff = stats.get("pointDifferential", stats.get("goalDifference", "-"))
            points = stats.get("points", "-")
            lines.append(
                f"`{rank:>2}` **{discord.utils.escape_markdown(self._team_name(row))}** "
                f"· PJ {played} · DG {diff} · **{points} pts**"
            )
        await interaction.followup.send(
            embed=discord.Embed(
                title=f"Primera División de Chile · {temporada}",
                description="\n".join(lines),
                color=discord.Color.blue(),
            )
        )

    @app_commands.command(name="calendario", description="Partidos y resultados de la liga chilena")
    @app_commands.describe(temporada="Año de temporada", fecha="Fecha YYYYMMDD opcional")
    async def calendario(
        self, interaction: discord.Interaction, temporada: str = "2026", fecha: str | None = None
    ) -> None:
        await interaction.response.defer(thinking=True)
        params = {"limit": "20", "season": temporada}
        if fecha:
            params["dates"] = fecha
        try:
            payload = await self._get(f"site/v2/sports/soccer/{LEAGUE}/scoreboard", params)
        except SportsAPIError as exc:
            await interaction.followup.send(embed=self._error_embed(str(exc)))
            return
        events = [event for event in payload.get("events", []) if isinstance(event, dict)]
        if not events:
            await interaction.followup.send("No hay partidos disponibles para esos filtros.")
            return
        embeds = []
        for event in events[:10]:
            competition = (event.get("competitions") or [{}])[0]
            competitors = competition.get("competitors", [])
            home = next((team for team in competitors if team.get("homeAway") == "home"), {})
            away = next((team for team in competitors if team.get("homeAway") == "away"), {})
            embeds.append(
                discord.Embed(
                    title=(
                        f"{home.get('team', {}).get('displayName', '?')} "
                        f"{home.get('score', '-')} - {away.get('score', '-')} "
                        f"{away.get('team', {}).get('displayName', '?')}"
                    ),
                    description=(
                        f"{event.get('date', '')} · "
                        f"{competition.get('status', {}).get('type', {}).get('detail', '')}"
                    ),
                    color=discord.Color.green(),
                )
            )
        await interaction.followup.send(embeds=embeds)

    @app_commands.command(
        name="partido", description="Busca los partidos recientes de un equipo chileno"
    )
    @app_commands.describe(equipo="Ejemplo: Colo-Colo", temporada="Año de temporada")
    async def partido(
        self, interaction: discord.Interaction, equipo: str, temporada: str = "2026"
    ) -> None:
        await interaction.response.defer(thinking=True)
        try:
            rows = self._groups(await self._standings(temporada))
            row = next(
                (item for item in rows if equipo.casefold() in self._team_name(item).casefold()),
                None,
            )
            team_id = row.get("team", {}).get("id") if row else None
            if not team_id:
                await interaction.followup.send(f"No encontré **{equipo}** en esa temporada.")
                return
            payload = await self._get(
                f"site/v2/sports/soccer/{LEAGUE}/scoreboard",
                {"limit": "100", "season": temporada, "team": str(team_id)},
            )
        except SportsAPIError as exc:
            await interaction.followup.send(embed=self._error_embed(str(exc)))
            return
        events = [event for event in payload.get("events", []) if isinstance(event, dict)]
        embeds = []
        for event in events[:5]:
            competition = (event.get("competitions") or [{}])[0]
            competitors = competition.get("competitors", [])
            home = next((team for team in competitors if team.get("homeAway") == "home"), {})
            away = next((team for team in competitors if team.get("homeAway") == "away"), {})
            embeds.append(
                discord.Embed(
                    title=(
                        f"{home.get('team', {}).get('displayName', '?')} "
                        f"{home.get('score', '-')} - {away.get('score', '-')} "
                        f"{away.get('team', {}).get('displayName', '?')}"
                    ),
                    description=(
                        f"{event.get('date', '')} · "
                        f"{competition.get('status', {}).get('type', {}).get('detail', '')}"
                    ),
                )
            )
        if embeds:
            await interaction.followup.send(embeds=embeds)
        else:
            await interaction.followup.send("No encontré partidos para ese equipo.")

    @app_commands.command(name="goleadores", description="Máximos goleadores de la liga chilena")
    @app_commands.describe(temporada="Año de temporada, por ejemplo 2026")
    async def goleadores(self, interaction: discord.Interaction, temporada: str = "2026") -> None:
        await interaction.response.defer(thinking=True)
        try:
            payload = await self._get(
                f"site/v2/sports/soccer/{LEAGUE}/leaders", {"season": temporada}
            )
        except SportsAPIError as exc:
            await interaction.followup.send(embed=self._error_embed(str(exc)))
            return
        categories = payload.get("leaders", [])
        goals = next(
            (
                category
                for category in categories
                if category.get("name") in {"totalGoals", "goals"}
            ),
            categories[0] if categories else {},
        )
        leaders = goals.get("leaders", [])
        if not leaders:
            await interaction.followup.send("ESPN no publicó goleadores para esa temporada.")
            return
        lines = []
        for index, leader in enumerate(leaders[:15], 1):
            athlete = leader.get("athlete", {})
            team = leader.get("team", {})
            lines.append(
                f"`{index:>2}` **{athlete.get('displayName', '?')}** · "
                f"{team.get('displayName', 'Sin equipo')} · {leader.get('displayValue', '?')} goles"
            )
        await interaction.followup.send(
            embed=discord.Embed(
                title=f"Goleadores · Primera División {temporada}",
                description="\n".join(lines),
                color=discord.Color.gold(),
            )
        )

    @app_commands.command(
        name="equipo", description="Información y rendimiento de un equipo chileno"
    )
    @app_commands.describe(nombre="Ejemplo: Colo-Colo", temporada="Año de temporada")
    async def equipo(
        self, interaction: discord.Interaction, nombre: str, temporada: str = "2026"
    ) -> None:
        await interaction.response.defer(thinking=True)
        try:
            rows = self._groups(await self._standings(temporada))
            row = next(
                (item for item in rows if nombre.casefold() in self._team_name(item).casefold()),
                None,
            )
            if not row:
                await interaction.followup.send(f"No encontré **{nombre}** en esa temporada.")
                return
            team = row.get("team", {})
            team_id = team.get("id")
            details = await self._get(
                f"site/v2/sports/soccer/{LEAGUE}/teams/{team_id}", {"season": temporada}
            )
        except SportsAPIError as exc:
            await interaction.followup.send(embed=self._error_embed(str(exc)))
            return
        stats = self._stats(row)
        detail_team = details.get("team", details)
        logos = detail_team.get("logos", [])
        embed = discord.Embed(
            title=self._team_name(row),
            description=f"Primera División de Chile · temporada {temporada}",
            color=discord.Color.red(),
        )
        embed.add_field(
            name="Campaña",
            value=(
                f"PJ {stats.get('gamesPlayed', '-')} · G {stats.get('wins', '-')} · "
                f"E {stats.get('ties', '-')} · P {stats.get('losses', '-')}"
            ),
        )
        embed.add_field(
            name="Goles",
            value=(
                f"A favor {stats.get('pointsFor', '-')} · "
                f"En contra {stats.get('pointsAgainst', '-')} · "
                f"DG {stats.get('pointDifferential', '-')}"
            ),
        )
        if logos:
            embed.set_thumbnail(url=logos[0].get("href"))
        record = detail_team.get("record") or {}
        if record:
            embed.add_field(name="Récord", value=str(record.get("summary", "Sin dato")))
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="jugador", description="Busca un jugador de la liga chilena")
    @app_commands.describe(nombre="Nombre del jugador")
    async def jugador(self, interaction: discord.Interaction, nombre: str) -> None:
        await interaction.response.defer(thinking=True)
        try:
            payload = await self._get(
                f"site/v2/sports/soccer/{LEAGUE}/athletes", {"search": nombre, "limit": "10"}
            )
        except SportsAPIError as exc:
            await interaction.followup.send(embed=self._error_embed(str(exc)))
            return
        athletes = payload.get("items", payload.get("athletes", []))
        if not athletes:
            await interaction.followup.send(f"No encontré al jugador **{nombre}**.")
            return
        athlete = athletes[0]
        embed = discord.Embed(
            title=athlete.get("displayName", nombre),
            description=athlete.get("position", {}).get("displayName", "Jugador"),
            color=discord.Color.gold(),
        )
        if athlete.get("headshot", {}).get("href"):
            embed.set_thumbnail(url=athlete["headshot"]["href"])
        for label, key in (
            ("Edad", "age"),
            ("Nacionalidad", "citizenship"),
            ("Altura", "displayHeight"),
        ):
            if athlete.get(key):
                embed.add_field(name=label, value=str(athlete[key]), inline=True)
        await interaction.followup.send(embed=embed)
