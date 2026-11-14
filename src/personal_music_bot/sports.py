from __future__ import annotations

import re
from datetime import UTC, datetime
from html import unescape
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
        def find_entries(value: Any) -> list[dict[str, Any]]:
            if isinstance(value, dict):
                standings = value.get("standings")
                if isinstance(standings, dict) and isinstance(standings.get("entries"), list):
                    return [row for row in standings["entries"] if isinstance(row, dict)]
                entries = value.get("entries")
                if (
                    isinstance(entries, list)
                    and entries
                    and all(isinstance(row, dict) and "team" in row for row in entries)
                ):
                    return entries
                for key in ("children", "groups", "standings"):
                    found = find_entries(value.get(key))
                    if found:
                        return found
            elif isinstance(value, list):
                for item in value:
                    found = find_entries(item)
                    if found:
                        return found
            return []

        return find_entries(payload)

    async def _get_text(self, url: str) -> str:
        try:
            async with (
                aiohttp.ClientSession(timeout=TIMEOUT) as session,
                session.get(url) as response,
            ):
                if response.status != 200:
                    raise SportsAPIError(f"ESPN respondió HTTP {response.status}.")
                return await response.text()
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise SportsAPIError("No pude conectarme a ESPN.") from exc

    async def _get_url(self, url: str) -> dict[str, Any]:
        url = url.replace("sports.core.api.espn.pvt", "sports.core.api.espn.com")
        try:
            async with (
                aiohttp.ClientSession(timeout=TIMEOUT) as session,
                session.get(url) as response,
            ):
                if response.status != 200:
                    raise SportsAPIError(f"ESPN respondió HTTP {response.status}.")
                payload = await response.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise SportsAPIError("No pude conectarme a ESPN.") from exc
        if not isinstance(payload, dict):
            raise SportsAPIError("ESPN devolvió una respuesta inesperada.")
        return payload

    @staticmethod
    def _stat_values(payload: dict[str, Any]) -> dict[str, str]:
        result: dict[str, str] = {}
        for category in payload.get("splits", {}).get("categories", []):
            for stat in category.get("stats", []):
                if isinstance(stat, dict):
                    result[stat.get("name", "")] = str(
                        stat.get("displayValue", stat.get("value", "-"))
                    )
        return result

    @staticmethod
    def _local_match_date(value: str) -> str:
        try:
            kickoff = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return kickoff.astimezone().strftime("%d/%m · %H:%M")
        except (ValueError, TypeError):
            return value or "Fecha por confirmar"

    @staticmethod
    def _scorer_rows(page: str) -> list[list[str]]:
        rows = re.findall(r"<tr[^>]*data-idx=\"\d+\"[^>]*>(.*?)</tr>", page, re.S)
        parsed = []
        for row in rows:
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
            values = [unescape(re.sub(r"<[^>]+>", "", cell)).strip() for cell in cells]
            if len(values) >= 5:
                parsed.append(values)
        return parsed

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
    def _score(competitor: dict[str, Any]) -> str:
        value = competitor.get("score", "-")
        if isinstance(value, dict):
            value = value.get("displayValue", value.get("value", "-"))
        return str(value)

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
            rank = stats.get("rank", "-")
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
                        f"{self._score(home)} - {self._score(away)} "
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
                f"site/v2/sports/soccer/{LEAGUE}/teams/{team_id}/schedule",
                {"season": temporada},
            )
        except SportsAPIError as exc:
            await interaction.followup.send(embed=self._error_embed(str(exc)))
            return
        events = [event for event in payload.get("events", []) if isinstance(event, dict)]
        now_played = [
            event
            for event in events
            if (event.get("competitions") or [{}])[0]
            .get("status", {})
            .get("type", {})
            .get("completed")
        ]
        chosen = sorted(
            now_played or events,
            key=lambda event: event.get("date", ""),
            reverse=bool(now_played),
        )[:5]
        embeds = []
        for event in chosen:
            competition = (event.get("competitions") or [{}])[0]
            competitors = competition.get("competitors", [])
            home = next((team for team in competitors if team.get("homeAway") == "home"), {})
            away = next((team for team in competitors if team.get("homeAway") == "away"), {})
            embeds.append(
                discord.Embed(
                    title=(
                        f"{home.get('team', {}).get('displayName', '?')} "
                        f"{self._score(home)} - {self._score(away)} "
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
            page = await self._get_text(
                f"https://www.espn.com/soccer/stats/_/league/{LEAGUE}/view/scoring?season={temporada}"
            )
        except SportsAPIError as exc:
            await interaction.followup.send(embed=self._error_embed(str(exc)))
            return
        rows = self._scorer_rows(page)
        if not rows:
            await interaction.followup.send("ESPN no publicó goleadores para esa temporada.")
            return
        lines = [
            f"`{row[0]:>2}` **{discord.utils.escape_markdown(row[1])}** · "
            f"{discord.utils.escape_markdown(row[2])} · {row[-1]} goles ({row[-2]} PJ)"
            for row in rows[:15]
        ]
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
            schedule = await self._get(
                f"site/v2/sports/soccer/{LEAGUE}/teams/{team_id}/schedule",
                {"season": temporada},
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
        embed.add_field(
            name="Posición en la tabla",
            value=f"Puesto {stats.get('rank', '-')} · {stats.get('points', '-')} puntos",
            inline=False,
        )
        record = detail_team.get("record") or {}
        if record:
            embed.add_field(name="Récord", value=str(record.get("summary", "Sin dato")))
        upcoming = []
        now = datetime.now(UTC)
        for event in schedule.get("events", []):
            try:
                kickoff = datetime.fromisoformat(event.get("date", "").replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue
            competition = (event.get("competitions") or [{}])[0]
            if kickoff <= now or competition.get("status", {}).get("type", {}).get("completed"):
                continue
            upcoming.append((kickoff, event, competition))
        upcoming.sort(key=lambda item: item[0])
        next_matches = []
        for _, event, competition in upcoming[:3]:
            competitors = competition.get("competitors", [])
            opponent = next(
                (
                    competitor
                    for competitor in competitors
                    if str(competitor.get("team", {}).get("id")) != str(team_id)
                ),
                {},
            )
            home = next(
                (competitor for competitor in competitors if competitor.get("homeAway") == "home"),
                {},
            )
            opponent_name = opponent.get("team", {}).get("displayName", "Rival por confirmar")
            venue = competition.get("venue", {})
            venue_name = venue.get("fullName", "Estadio por confirmar")
            versus = "vs" if str(home.get("team", {}).get("id")) == str(team_id) else "en"
            next_matches.append(
                f"• **{self._local_match_date(event.get('date', ''))}** {versus} "
                f"**{discord.utils.escape_markdown(opponent_name)}**\n  🏟️ {venue_name}"
            )
        embed.add_field(
            name="Próximos partidos",
            value="\n".join(next_matches)
            if next_matches
            else "ESPN aún no informa próximos partidos.",
            inline=False,
        )
        await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="jugador", description="Busca la ficha y estadísticas de un jugador chileno"
    )
    @app_commands.describe(nombre="Nombre del jugador")
    async def jugador(self, interaction: discord.Interaction, nombre: str) -> None:
        await interaction.response.defer(thinking=True)
        try:
            search = await self._get(
                "search/v2", {"region": "us", "lang": "en", "query": nombre, "limit": "10"}
            )
            players = [
                player
                for result in search.get("results", [])
                if result.get("type") == "player"
                for player in result.get("contents", [])
            ]
            query = nombre.casefold()
            player = next(
                (item for item in players if item.get("displayName", "").casefold() == query),
                players[0] if players else None,
            )
            uid = player.get("uid", "") if player else ""
            athlete_id_match = re.search(r"~a:(\d+)", uid)
            if not athlete_id_match:
                await interaction.followup.send(f"No encontré al jugador **{nombre}** en ESPN.")
                return
            athlete_id = athlete_id_match.group(1)
            athlete = await self._get_url(
                f"https://sports.core.api.espn.com/v2/sports/soccer/leagues/{LEAGUE}/athletes/{athlete_id}?lang=en&region=us"
            )
            stats_ref = athlete.get("statistics", {}).get("$ref")
            stats_payload = await self._get_url(stats_ref) if stats_ref else {}
            team_ref = athlete.get("defaultTeam", {}).get("$ref")
            player_team = await self._get_url(team_ref) if team_ref else {}
        except SportsAPIError as exc:
            await interaction.followup.send(embed=self._error_embed(str(exc)))
            return
        stats = self._stat_values(stats_payload)
        position = athlete.get("position", {}).get("displayName", "Sin posición")
        team_name = player_team.get("displayName", "Equipo sin dato")
        nationality = athlete.get("citizenship") or athlete.get("citizenshipCountry", {}).get(
            "name"
        )
        embed = discord.Embed(
            title=athlete.get("displayName", nombre),
            description=f"{team_name} · {position}",
            color=discord.Color.gold(),
        )
        if athlete.get("headshot", {}).get("href"):
            embed.set_thumbnail(url=athlete["headshot"]["href"])
        embed.add_field(name="Edad", value=str(athlete.get("age", "Sin dato")), inline=True)
        embed.add_field(name="Nacionalidad", value=nationality or "Sin dato", inline=True)
        embed.add_field(name="Dorsal", value=str(athlete.get("jersey", "Sin dato")), inline=True)
        embed.add_field(
            name="Temporada",
            value=(
                f"PJ {stats.get('appearances', '—')} · Goles {stats.get('totalGoals', '—')} · "
                f"Asistencias {stats.get('goalAssists', '—')}"
            ),
            inline=False,
        )
        embed.add_field(
            name="Minutos y tarjetas",
            value=(
                f"Min {stats.get('minutes', '—')} · Amarillas {stats.get('yellowCards', '—')} · "
                f"Rojas {stats.get('redCards', '—')}"
            ),
            inline=False,
        )
        await interaction.followup.send(embed=embed)
