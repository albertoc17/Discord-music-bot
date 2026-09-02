from __future__ import annotations

from random import choice

_SEARCHING = (
    "Buscando el tema, dame un segundo... 🔎",
    "Ya po, estoy viendo qué weá pillo... 🔎",
    "Déjame cachar dónde anda ese temazo... 🔎",
    "Aguanta un poquito, estoy buscando la canción... 🔎",
    "Espérate un cachito, estoy revolviendo internet por tu tema... 🕵️",
    "Voy al toque a buscar esa joyita, no te me desesperís. 🔍",
    "Dame una vuelta y te pillo esa canción altiro. 🎧",
    "Ya, déjamelo a mí. Estoy rastreando ese tema... 📡",
    "Buscando entre los rincones más turbios de internet... 🔦",
    "A ver, a ver... ¿dónde se escondió esa canción? 👀",
    "Estoy haciendo la pega, aguanta unos segundos, po. 🛠️",
    "Activando el radar musical de Arturo... 📻",
    "Buena elección. Déjame encontrarla antes que se acabe el carrete. 🍻",
    "Calmao, voy volando a buscar ese temazo. 💨",
)

_NOT_FOUND = (
    "No encontré tu tema, qlo 😔. Prueba con otro nombre o pega una URL.",
    "Pucha, no pillé ni una weá con esa búsqueda. Intenta escribirla distinto.",
    "Ese tema anda más perdido que el Teniente Bello. Prueba con otro nombre.",
    "No apareció ni por si acaso. Revisa el nombre y tírame otra búsqueda. 🤷",
    "Internet se hizo el leso y no me entregó nada. Prueba con una URL.",
    "Ese tema parece inventado, compadre. Escríbelo de otra forma. 🫥",
    "Busqué hasta debajo de las piedras y nada. Dame otra pista. 🪨",
    "No hubo caso, esa canción se me arrancó. Intenta con el artista también.",
    "Cero resultados, jefe. Capaz que el nombre esté escrito como las weas. 😅",
    "Ese temazo no quiso aparecer. Mándame un enlace y lo arreglamos.",
    "Quedé más perdido que tú: no encontré nada con esa búsqueda. 🧭",
    "La canción está jugando a las escondidas y ganó. Prueba de nuevo. 🙈",
    "No pillé nada reproducible. Cambia la búsqueda o pega el enlace directo.",
)

_TRACK_QUEUED = (
    "Wena, pillé **{title}** ({duration}) y quedó en la cola. 🎶",
    "Ya po, agregué **{title}** ({duration}) a la cola.",
    "Listoco: **{title}** ({duration}) quedó esperando su turno.",
    "Anotado: **{title}** ({duration}) se suma al carrete. 🍻",
    "Buena, **{title}** ({duration}) quedó guardadito en la fila.",
    "Marchando **{title}** ({duration}); sonará cuando le toque. 🫡",
    "La máquina aceptó **{title}** ({duration}). Ya está en cola. ⚙️",
    "De una: **{title}** ({duration}) quedó listo para sonar. 🔊",
    "Temazo asegurado: **{title}** ({duration}) entró a la cola. ✅",
    "Ya quedó **{title}** ({duration}); ahora a esperar como persona civilizada.",
    "Le hice un espacio a **{title}** ({duration}) en la fila. 🎟️",
    "Arturo confirma: **{title}** ({duration}) fue agregado correctamente. 👑",
    "Se viene **{title}** ({duration}). Lo dejé esperando su momento. ⏳",
)

_PLAYLIST_QUEUED = (
    "Quedaron **{count} temas** en la cola. Se viene bueno esto. 🔥",
    "Ya po, agregué **{count} canciones** de una (límite: {limit}).",
    "Wena, pillé **{count} temas** y los mandé derechito a la cola.",
    "Playlist lista: entraron **{count} temas** de un paraguazo. 🎶",
    "Ya quedó la fiesta armada con **{count} canciones** (límite: {limit}). 🪩",
    "Procesé la playlist y mandé **{count} temas** a la fila. Impeque.",
    "Cargamento recibido: **{count} canciones** listas para sonar. 📦",
    "Se sumaron **{count} temas**. Con esto tenemos música para rato. 🔥",
    "Arturo hizo la magia: **{count} canciones** agregadas (máximo: {limit}). 👑",
    "La playlist venía cargadita: guardé **{count} temas** en la cola.",
    "Operación exitosa, cabros: **{count} canciones** quedaron esperando. ✅",
    "Metí **{count} temas** de una. El límite por playlist es **{limit}**.",
    "Cola abastecida con **{count} canciones**. Que no pare la música. 🔊",
)

_NOW_PLAYING = (
    "Ahora suena **{title}**, pedido por {requester}. 🎵",
    "Sube el volumen: está sonando **{title}** — la pidió {requester}.",
    "Ya cabros, vamos con **{title}**, cortesía de {requester}.",
    "Turno de **{title}**. La selección viene de parte de {requester}. 🎧",
    "Se acabó la espera: suena **{title}**, pedido por {requester}. 🔊",
    "Arturo presenta **{title}**, una humilde petición de {requester}. 👑",
    "A mover la patita con **{title}**, elegida por {requester}. 🕺",
    "En los parlantes: **{title}**. Échenle la culpa a {requester}. 😎",
    "Que corra la música: ahora va **{title}**, cortesía de {requester}. 🍻",
    "Siguiente parada: **{title}**, solicitada por {requester}. 🚂",
    "Ya está sonando **{title}** porque {requester} lo quiso así. 🎶",
    "Silencio los de atrás: comienza **{title}**, pedida por {requester}. 🤫",
    "Directo al oído: **{title}**, seleccionada por {requester}. 🎼",
)

_PLAYBACK_FAILED = (
    "Se fue a la chucha **{title}** y no lo pude reproducir. Voy con el siguiente.",
    "Pucha, **{title}** no quiso sonar. Probemos con el que sigue.",
    "Ese tema se puso mañoso: no pude reproducir **{title}**.",
    "**{title}** se hizo el interesante y falló. Saltando al próximo. 🙄",
    "No hubo mano con **{title}**. Que pase el siguiente de la fila.",
    "Algo se rompió intentando tocar **{title}**. Seguimos nomás. 🔧",
    "**{title}** quedó debiendo: la fuente no quiso cooperar. Próximo tema.",
    "Se cayó **{title}** antes de empezar. Voy a probar con la siguiente. 💥",
    "La tecnología perdió esta batalla contra **{title}**. Continuemos. 🤖",
    "No pude sacar audio de **{title}** ni a palos. Vamos con otra.",
    "**{title}** salió fallada de fábrica. La salto para no matar el ambiente.",
    "El enlace de **{title}** no respondió. No queda otra que seguir. 📵",
    "F por **{title}**: no se pudo reproducir. Pasemos al siguiente. 🫡",
)

_LEAVING = (
    "Chao, giles culiaos. 👋",
    "Ya cabros, me fui. Pórtense como las weas nomás.",
    "Me aburrí de ustedes, me viro. Chao pescao. 🐟",
    "Hasta aquí llegó el carrete, manga de weones. Nos vimos.",
    "No queda música, así que cierro por fuera. Chao, cabros. 🚪",
    "Arturo abandona el canal. Fue un honor, manga de ordinarios. 👑",
    "Me retiro con la dignidad que ustedes nunca tuvieron. Nos vimos. 🎩",
    "Hasta aquí nomás llegamos. Me llaman cuando vuelva el carrete. 🍻",
    "Quedó todo más silencioso que velorio, así que me voy. Chao. ⚰️",
    "Se acabó la música y también mi paciencia. Me viro. 👋",
    "Ya nadie pesca esta weá. Desconectando en tres, dos, uno... 📴",
    "Me voy antes de que alguien ponga reguetón del malo. Suerte. 🏃",
    "Arturo se retira a sus aposentos. No rompan nada mientras tanto. 🏰",
    "Cierro la fonda por hoy, cabros. Vuelvan cuando tengan más temazos. 🎪",
)

_RANDOM_INSULTS = (
    "{member}, chupa el pico. Con cariño, Arturo. ❤️",
    "Oye {member}, ¿siempre eri así de aweonao o hoy te estai esforzando?",
    "{member}, tenís menos ritmo que una lavadora con ladrillos.",
    "Atención: {member} acaba de perder otra oportunidad de quedarse callado.",
    "{member}, hasta el modo aleatorio toma mejores decisiones que voh.",
    "Un saludo para {member}, orgullo nacional de las malas ideas. 🇨🇱",
    "{member}, eri más lento que descargar música con internet del campo.",
    "Oye {member}, súbele a la música para que no se escuchen tus opiniones.",
    "{member}, te quiero caleta, pero estai hablando puras weas.",
    "Se informa que {member} sigue sin poner un tema decente. Qué sorpresa.",
    "{member}, tenís la coordinación de un carrito de supermercado malo.",
    "Arturo ha revisado los antecedentes y confirma que {member} es entero perkin.",
    "{member}, si la vergüenza diera plata ya seríai millonario.",
    "Último minuto: {member} volvió a dar la cacha. Ampliaremos. 📰",
    "{member}, menos mal que eri simpático, porque pa elegir música no servís.",
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


def leaving_message() -> str:
    return choice(_LEAVING)


def random_insult_message(member: str) -> str:
    return choice(_RANDOM_INSULTS).format(member=member)
