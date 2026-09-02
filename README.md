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
5. Concede solamente **View Channels**, **Send Messages**, **Connect**, **Speak**
   y **Set Voice Channel Status**. Copia el enlace de instalacion, abrelo y
   elige tu servidor.
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

### Música
- `/play [búsqueda]`: busca o agrega una canción, URL o playlist a la cola.
- `/pause`: pausa la música actual.
- `/resume`: continúa la música pausada.
- `/skip`: salta a la siguiente canción.
- `/stop`: detiene la música y vacía la cola.
- `/queue`: muestra la canción actual y hasta 10 próximas.
- `/nowplaying`: muestra los detalles de la canción actual.
- `/leave`: desconecta el bot del canal de voz.

### Configuración
- `/volume [nivel]`: ajusta el volumen de 0 a 100 (defecto: 70%).
- `/quality [bitrate]`: cambia la calidad de audio (64k, 96k, 128k, 192k, 256k).
- `/ping`: muestra la latencia del bot.
- `/status`: muestra la version desplegada y el consumo de CPU y memoria del bot.
- `/help`: lista todos los comandos disponibles.

Al conectarse con `/play`, Arturo publica un panel que se mantiene al final del chat con:
- Título y enlace de la canción actual
- **Barra de progreso** que se actualiza en tiempo real (se muestra cada 1 segundo)
- Duración actual / total
- Quién pidió la canción
- Número de canciones en cola
- Miniatura de la portada

Los botones permiten reproducir/pausar (⏯️), detener (⏹️) y pasar a la siguiente canción (⏭️).
Solo los usuarios en el mismo canal de voz pueden usarlos.

Mientras reproduce, el estado del canal de voz muestra el nombre de la canción actual. Si
queda inactivo, el bot se despide y se desconecta solo después de cinco minutos. Este
tiempo, el volumen, el bitrate de audio, el límite de una playlist y la ruta a FFmpeg se
pueden cambiar en `.env`; revisa `.env.example`.

En cada canción hay un 5% de probabilidad de que Arturo putee, en un momento aleatorio,
a una persona del canal de voz. El nombre se muestra como texto y no genera una mención.

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
