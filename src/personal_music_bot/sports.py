from __future__ import annotations

from typing import Any

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

API_URL = "https://v3.football.api-sports.io"
TIMEOUT = aiohttp.ClientTimeout(total=15)
CHILE_LEAGUE = "Primera Division"


class SportsAPIError(Exception):
    """The football data provider could not answer the request."""


class Sports(commands.Cog):
    """Football data backed by API-Football (API-Sports)."""

    def __init__(self, bot: commands.Bot, settings: Any) -> None:
        self.bot = bot
        self.api_key = settings.api_football_key

    async def _get(self, endpoint: str, params: dict[str, str]) -> list[dict[str, Any]]:
        if not self.api_key:
            raise SportsAPIError(
                "Falta configurar API_FOOTBALL_KEY. Crea una cuenta gratuita en "
                "dashboard.api-football.com y agrega la clave al .env del servidor."
            )
        try:
            async with (
                aiohttp.ClientSession(
                    timeout=TIMEOUT,
                    headers={"x-apisports-key": self.api_key},
                ) as session,
                session.get(f"{API_URL}/{endpoint}", params=params) as response,
            ):
                if response.status == 429:
                    raise SportsAPIError("Se alcanzó el límite diario de la API deportiva.")
                if response.status in (401, 403):
                    raise SportsAPIError(
                        "La API key deportiva no es válida o no tiene acceso. "
                        "Revisa API_FOOTBALL_KEY."
                    )
                if response.status != 200:
                    raise SportsAPIError(f"La API deportiva respondió HTTP {response.status}.")
                payload = await response.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise SportsAPIError("No pude conectarme a API-Football.") from exc
        errors = payload.get("errors") if isinstance(payload, dict) else None
        if errors:
            raise SportsAPIError(f"API-Football: {errors}")
        response_data = payload.get("response", []) if isinstance(payload, dict) else []
        return [item for item in response_data if isinstance(item, dict)]

    async def _league(self, name: str, season: str) -> dict[str, Any] | None:
        matches = await self._get("leagues", {"name": name, "country": "Chile", "season": season})
        return matches[0] if matches else None

    async def _team(self, name: str) -> dict[str, Any] | None:
        matches = await self._get("teams", {"search": name, "country": "Chile"})
        if not matches:
            return None
        normalized = name.casefold().replace("-", " ").strip()
        return next(
            (
                row
                for row in matches
                if normalized in str(row.get("team", {}).get("name", "")).casefold()
            ),
            matches[0],
        )

    @staticmethod
    def _error_embed(error: str) -> discord.Embed:
        return discord.Embed(description=error, color=discord.Color.red())

    @app_commands.command(name="tabla", description="Tabla de la liga chilena")
    @app_commands.describe(temporada="Año de temporada, por ejemplo 2026")
    async def tabla(self, interaction: discord.Interaction, temporada: str = "2026") -> None:
        await interaction.response.defer(thinking=True)
        try:
            league = await self._league(CHILE_LEAGUE, temporada)
            if not league:
                await interaction.followup.send("No encontré la liga chilena para esa temporada.")
                return
            standings = await self._get(
                "standings",
                {"league": str(league["league"]["id"]), "season": temporada},
            )
        except (SportsAPIError, KeyError, TypeError) as exc:
            await interaction.followup.send(embed=self._error_embed(str(exc)))
            return
        groups = standings[0].get("league", {}).get("standings", []) if standings else []
        rows = groups[0] if groups else []
        if not rows:
            await interaction.followup.send("No hay tabla disponible para esa temporada.")
            return
        lines = [
            f"`{row.get('rank', '-'):>2}` "
            f"**{discord.utils.escape_markdown(row.get('team', {}).get('name', '?'))}** "
            f"PJ {row.get('all', {}).get('played', '-')} · DG {row.get('goalsDiff', '-')} · "
            f"**{row.get('points', '-')} pts**"
            for row in rows[:20]
        ]
        embed = discord.Embed(
            title=f"Liga de Primera de Chile · {temporada}",
            description="\n".join(lines),
            color=discord.Color.blue(),
        )
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="goleadores", description="Máximos goleadores de la liga chilena")
    @app_commands.describe(temporada="Año de temporada, por ejemplo 2026")
    async def goleadores(self, interaction: discord.Interaction, temporada: str = "2026") -> None:
        await interaction.response.defer(thinking=True)
        try:
            league = await self._league(CHILE_LEAGUE, temporada)
            if not league:
                await interaction.followup.send("No encontré la liga chilena para esa temporada.")
                return
            scorers = await self._get(
                "players/topscorers",
                {"league": str(league["league"]["id"]), "season": temporada},
            )
        except (SportsAPIError, KeyError, TypeError) as exc:
            await interaction.followup.send(embed=self._error_embed(str(exc)))
            return
        if not scorers:
            await interaction.followup.send("No hay goleadores disponibles para esa temporada.")
            return
        lines = []
        for position, item in enumerate(scorers[:15], 1):
            player = item.get("player", {})
            stats = (item.get("statistics") or [{}])[0]
            goals = stats.get("goals", {})
            team = stats.get("team", {}).get("name", "Sin equipo")
            lines.append(
                f"`{position:>2}` **{player.get('name', '?')}** · {team} · "
                f"{goals.get('total', 0)} goles"
            )
        embed = discord.Embed(
            title=f"Goleadores · Liga de Primera {temporada}",
            description="\n".join(lines),
            color=discord.Color.gold(),
        )
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="equipo", description="Ficha y rendimiento de un equipo chileno")
    @app_commands.describe(nombre="Ejemplo: Colo-Colo", temporada="Año de temporada")
    async def equipo(
        self, interaction: discord.Interaction, nombre: str, temporada: str = "2026"
    ) -> None:
        await interaction.response.defer(thinking=True)
        try:
            found = await self._team(nombre.strip())
            if not found:
                await interaction.followup.send(f"No encontré el equipo **{nombre}**.")
                return
            team, venue = found.get("team", {}), found.get("venue", {})
            league = await self._league(CHILE_LEAGUE, temporada)
            if not league:
                await interaction.followup.send("No encontré la liga chilena para esa temporada.")
                return
            stats = await self._get(
                "teams/statistics",
                {
                    "team": str(team["id"]),
                    "league": str(league["league"]["id"]),
                    "season": temporada,
                },
            )
        except (SportsAPIError, KeyError, TypeError) as exc:
            await interaction.followup.send(embed=self._error_embed(str(exc)))
            return
        data = stats[0] if stats else {}
        fixtures = data.get("fixtures", {})
        played = fixtures.get("played", {}).get("total", "-")
        won = fixtures.get("wins", {}).get("total", "-")
        drawn = fixtures.get("draws", {}).get("total", "-")
        lost = fixtures.get("loses", {}).get("total", "-")
        goals = data.get("goals", {})
        scored = goals.get("for", {}).get("total", {}).get("total", "-")
        conceded = goals.get("against", {}).get("total", {}).get("total", "-")
        embed = discord.Embed(
            title=team.get("name", nombre),
            description=f"Liga de Primera de Chile · temporada {temporada}",
            color=discord.Color.red(),
            url=team.get("url"),
        )
        embed.add_field(name="Balance", value=f"PJ {played} · G {won} · E {drawn} · P {lost}")
        embed.add_field(name="Goles", value=f"A favor {scored} · En contra {conceded}")
        if venue:
            embed.add_field(
                name="Estadio",
                value=f"{venue.get('name', 'Sin dato')} · {venue.get('city', 'Sin ciudad')}",
                inline=False,
            )
        if team.get("logo"):
            embed.set_thumbnail(url=team["logo"])
        embed.set_footer(text=f"Fundado: {team.get('founded') or 'Sin dato'} · País: Chile")
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="jugador", description="Busca un jugador de fútbol")
    @app_commands.describe(nombre="Nombre del jugador", temporada="Año de temporada")
    async def jugador(
        self, interaction: discord.Interaction, nombre: str, temporada: str = "2026"
    ) -> None:
        await interaction.response.defer(thinking=True)
        try:
            players = await self._get("players", {"search": nombre, "season": temporada})
        except SportsAPIError as exc:
            await interaction.followup.send(embed=self._error_embed(str(exc)))
            return
        if not players:
            await interaction.followup.send(f"No encontré al jugador **{nombre}**.")
            return
        player = players[0].get("player", {})
        stat = (players[0].get("statistics") or [{}])[0]
        embed = discord.Embed(
            title=player.get("name", nombre),
            description=(
                f"{stat.get('team', {}).get('name', 'Equipo sin dato')} · "
                f"{stat.get('league', {}).get('name', 'Liga sin dato')}"
            ),
            color=discord.Color.gold(),
        )
        embed.add_field(name="Posición", value=stat.get("games", {}).get("position") or "Sin dato")
        embed.add_field(name="Edad", value=player.get("age") or "Sin dato")
        embed.add_field(name="Nacionalidad", value=player.get("nationality") or "Sin dato")
        goals = stat.get("goals", {})
        embed.add_field(
            name="Temporada",
            value=f"Goles {goals.get('total', 0)} · Asistencias {goals.get('assists', 0)}",
        )
        if player.get("photo"):
            embed.set_thumbnail(url=player["photo"])
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="partido", description="Busca partidos de un equipo chileno")
    @app_commands.describe(equipo="Ejemplo: Colo-Colo", temporada="Año de temporada")
    async def partido(
        self, interaction: discord.Interaction, equipo: str, temporada: str = "2026"
    ) -> None:
        await interaction.response.defer(thinking=True)
        try:
            found = await self._team(equipo.strip())
            if not found:
                await interaction.followup.send(f"No encontré el equipo **{equipo}**.")
                return
            league = await self._league(CHILE_LEAGUE, temporada)
            if not league:
                await interaction.followup.send("No encontré la liga chilena para esa temporada.")
                return
            fixtures = await self._get(
                "fixtures",
                {
                    "team": str(found["team"]["id"]),
                    "league": str(league["league"]["id"]),
                    "season": temporada,
                    "last": "5",
                },
            )
        except (SportsAPIError, KeyError, TypeError) as exc:
            await interaction.followup.send(embed=self._error_embed(str(exc)))
            return
        embeds = []
        for result in fixtures[:5]:
            fixture = result.get("fixture", {})
            teams = result.get("teams", {})
            goals = result.get("goals", {})
            embed = discord.Embed(
                title=(
                    f"{teams.get('home', {}).get('name', '?')} "
                    f"{goals.get('home', '-')} - {goals.get('away', '-')} "
                    f"{teams.get('away', {}).get('name', '?')}"
                ),
                description=(
                    f"{fixture.get('date', '')} · {fixture.get('status', {}).get('long', '')}"
                ),
                color=discord.Color.green(),
            )
            embeds.append(embed)
        if not embeds:
            await interaction.followup.send("No hay partidos recientes para ese equipo.")
        else:
            await interaction.followup.send(embeds=embeds)

    @app_commands.command(name="calendario", description="Próximos partidos de la liga chilena")
    @app_commands.describe(temporada="Año de temporada, por ejemplo 2026")
    async def calendario(self, interaction: discord.Interaction, temporada: str = "2026") -> None:
        await interaction.response.defer(thinking=True)
        try:
            league = await self._league(CHILE_LEAGUE, temporada)
            if not league:
                await interaction.followup.send("No encontré la liga chilena para esa temporada.")
                return
            fixtures = await self._get(
                "fixtures",
                {
                    "league": str(league["league"]["id"]),
                    "season": temporada,
                    "next": "5",
                },
            )
        except (SportsAPIError, KeyError, TypeError) as exc:
            await interaction.followup.send(embed=self._error_embed(str(exc)))
            return
        embeds = []
        for result in fixtures[:5]:
            fixture, teams = result.get("fixture", {}), result.get("teams", {})
            embeds.append(
                discord.Embed(
                    title=(
                        f"{teams.get('home', {}).get('name', '?')} vs "
                        f"{teams.get('away', {}).get('name', '?')}"
                    ),
                    description=(
                        f"{fixture.get('date', '')} · {fixture.get('venue', {}).get('name', '')}"
                    ),
                    color=discord.Color.blue(),
                )
            )
        if not embeds:
            await interaction.followup.send("No hay próximos partidos disponibles.")
        else:
            await interaction.followup.send(embeds=embeds)
