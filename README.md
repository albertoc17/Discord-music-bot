# Arturo: asistente personal para Discord

**Arturo** es un asistente personal para un servidor privado de Discord. En esta
primera etapa reproduce musica desde una busqueda, una URL o una playlist,
mantiene una cola por servidor y se controla con comandos slash.
Responde con distintas frases chilenas mientras busca, agrega y reproduce temas.

## Requisitos

- Python 3.11 o posterior.
- [FFmpeg](https://ffmpeg.org/download.html) instalado y disponible como `ffmpeg` en el `PATH`.
- Para compatibilidad completa con YouTube, un runtime de JavaScript compatible con `yt-dlp`, como [Deno](https://docs.deno.com/runtime/getting_started/installation/) (recomendado por el proyecto) o Node.js.
- Una aplicacion/bot creada en el [Discord Developer Portal](https://discord.com/developers/applications).

## Preparacion

1. Abre el [Discord Developer Portal](https://discord.com/developers/applications),
   pulsa **New Application**, escribe `Arturo` y crea la aplicacion.
2. En **Bot**, pulsa **Reset Token**, copia el token y guardalo en `DISCORD_TOKEN`
   dentro de `.env`. El token funciona como una contrasena: no lo pegues en el
   chat ni lo subas a Git.
3. En **Installation**, habilita **Guild Install** y selecciona
   **Discord Provided Link**.
4. En **Default Install Settings > Guild Install**, agrega los scopes `bot` y
   `applications.commands`.
5. Concede solamente **View Channels**, **Send Messages**, **Connect** y
   **Speak**. Copia el enlace de instalacion, abrelo y elige tu servidor.
6. En Discord, activa **Ajustes de usuario > Avanzado > Modo desarrollador**.
   Haz clic derecho sobre tu servidor, selecciona **Copiar ID del servidor** y
   guardalo en `DISCORD_GUILD_ID` dentro de `.env`.
7. Instala el proyecto en un entorno virtual:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

8. Si todavia no existe `.env`, copia el ejemplo. Pega el token y el ID del
   servidor; este ultimo hace que los comandos aparezcan inmediatamente durante
   el desarrollo.

```powershell
Copy-Item .env.example .env
```

Nunca publiques el archivo `.env` ni el token del bot.

## Ejecutar

```powershell
python -m personal_music_bot
```

Tambien queda instalado el comando `discord-music-bot`.

## Comandos

- `/play busqueda`: reproduce o agrega una busqueda, URL o playlist.
- `/pause` y `/resume`: pausa y continua.
- `/skip`: salta la pista actual.
- `/stop`: detiene y limpia la cola.
- `/queue`: muestra la pista actual y hasta 10 pendientes.
- `/nowplaying`: muestra los detalles de la pista actual.
- `/leave`: limpia la cola y desconecta el bot.

Si queda inactivo, el bot se desconecta solo después de cinco minutos. Este tiempo, el volumen, el limite de una playlist y la ruta a FFmpeg se pueden cambiar en `.env`; revisa `.env.example`.

## Calidad

```powershell
ruff check .
pytest
```

## Nota sobre las fuentes de audio

`yt-dlp` resuelve las fuentes en tiempo de reproduccion y debe mantenerse actualizado cuando un proveedor cambia su sitio:

```powershell
python -m pip install --upgrade "yt-dlp[default]"
```

Usa el bot respetando las condiciones del servicio de cada fuente y solo con contenido que tengas derecho a reproducir.
