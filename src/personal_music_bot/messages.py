from __future__ import annotations

from random import choice

_SEARCHING = (
    "Buscando el tema, dame un segundo... 🔎",
    "Ya po, estoy viendo qué weá pillo... 🔎",
    "Déjame cachar dónde anda ese temazo... 🔎",
    "Aguanta un poquito, estoy buscando la canción... 🔎",
)

_NOT_FOUND = (
    "No encontré tu tema, qlo 😔. Prueba con otro nombre o pega una URL.",
    "Pucha, no pillé ni una weá con esa búsqueda. Intenta escribirla distinto.",
    "Ese tema anda más perdido que el Teniente Bello. Prueba con otro nombre.",
)

_TRACK_QUEUED = (
    "Wena, pillé **{title}** ({duration}) y quedó en la cola. 🎶",
    "Ya po, agregué **{title}** ({duration}) a la cola.",
    "Listoco: **{title}** ({duration}) quedó esperando su turno.",
)

_PLAYLIST_QUEUED = (
    "Quedaron **{count} temas** en la cola. Se viene bueno esto. 🔥",
    "Ya po, agregué **{count} canciones** de una (límite: {limit}).",
    "Wena, pillé **{count} temas** y los mandé derechito a la cola.",
)

_NOW_PLAYING = (
    "Ahora suena **{title}**, pedido por {requester}. 🎵",
    "Sube el volumen: está sonando **{title}** — la pidió {requester}.",
    "Ya cabros, vamos con **{title}**, cortesía de {requester}.",
)

_PLAYBACK_FAILED = (
    "Se fue a la chucha **{title}** y no lo pude reproducir. Voy con el siguiente.",
    "Pucha, **{title}** no quiso sonar. Probemos con el que sigue.",
    "Ese tema se puso mañoso: no pude reproducir **{title}**.",
)


def searching_message() -> str:
    return choice(_SEARCHING)


def not_found_message() -> str:
    return choice(_NOT_FOUND)


def track_queued_message(title: str, duration: str) -> str:
    return choice(_TRACK_QUEUED).format(title=title, duration=duration)


def playlist_queued_message(count: int, limit: int) -> str:
    return choice(_PLAYLIST_QUEUED).format(count=count, limit=limit)


def now_playing_message(title: str, requester: str) -> str:
    return choice(_NOW_PLAYING).format(title=title, requester=requester)


def playback_failed_message(title: str) -> str:
    return choice(_PLAYBACK_FAILED).format(title=title)
