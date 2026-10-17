"""Página do player incorporado do YouTube e a ponte entre o JavaScript dela e o Python."""

import json
import re

from PySide6.QtCore import QFile, QIODevice, QObject, Signal, Slot

IFRAME_API_URL = "https://www.youtube.com/iframe_api"
ORIGIN = "https://dinotube.local"  # origem declarada ao YouTube (a página é carregada com este baseUrl)
EMBED_HOST = "https://www.youtube-nocookie.com"
_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")

# Códigos de erro do player do YouTube -> código estável do aplicativo
_ERROR_MAP = {
    2: "failed",  # parâmetro inválido
    5: "failed",  # erro do player HTML5
    100: "unavailable",  # removido ou privado
    101: "embed_blocked",  # dono não permite incorporar
    150: "embed_blocked",
    153: "embed_blocked",  # configuração do player / referência ausente
}

# Estados do YouTube (YT.PlayerState)
STATE_ENDED, STATE_PLAYING, STATE_PAUSED, STATE_BUFFERING = 0, 1, 2, 3


def map_error(code):
    return _ERROR_MAP.get(int(code), "failed")


def webchannel_source():
    """Conteúdo do qwebchannel.js (recurso do Qt). Vai embutido no HTML: uma página https não lê 'qrc:'."""
    import PySide6.QtWebChannel  # noqa: F401  registra o recurso

    resource = QFile(":/qtwebchannel/qwebchannel.js")
    if not resource.open(QIODevice.ReadOnly):
        raise RuntimeError("qwebchannel.js não encontrado no Qt")
    try:
        return bytes(resource.readAll()).decode("utf-8")
    finally:
        resource.close()


def build_html(video_id, start=0, api_script=None, webchannel_js=None):
    """HTML do player. `api_script` (JavaScript) substitui o carregamento da API real; usado nos testes."""
    if not _ID.match(video_id or ""):
        raise ValueError("id de vídeo inválido")
    start = max(0, int(start))
    api = f"<script>{api_script}</script>" if api_script is not None else f'<script src="{IFRAME_API_URL}" async></script>'
    channel = f"<script>{webchannel_js}</script>" if webchannel_js is not None else '<script src="qrc:///qtwebchannel/qwebchannel.js"></script>'
    return f"""<!doctype html>
<html><head><meta charset="utf-8">
<meta name="referrer" content="strict-origin-when-cross-origin">
<style>html,body{{margin:0;height:100%;background:#000;overflow:hidden}}
#player{{position:absolute;top:0;left:0;width:100%;height:100%;border:0}}</style>
{channel}
</head><body><div id="player"></div>
<script>
var bridge = null, player = null, ready = false, queue = [];
function send(kind, payload) {{
  if (!bridge) {{ queue.push([kind, payload]); return; }}
  bridge.message(kind, JSON.stringify(payload || {{}}));
}}
new QWebChannel(qt.webChannelTransport, function (channel) {{
  bridge = channel.objects.bridge;
  queue.forEach(function (item) {{ send(item[0], item[1]); }});
  queue = [];
  send('channel', {{}});
}});
function poll() {{
  if (!ready) return;
  send('time', {{
    t: player.getCurrentTime(), d: player.getDuration(), q: player.getPlaybackQuality(),
    levels: player.getAvailableQualityLevels(), v: player.getVolume(), m: player.isMuted(),
    r: player.getPlaybackRate(), s: player.getPlayerState()
  }});
}}
function onYouTubeIframeAPIReady() {{
  player = new YT.Player('player', {{
    videoId: '{video_id}',
    playerVars: {{ enablejsapi: 1, origin: '{ORIGIN}', rel: 0, playsinline: 1, controls: 0, disablekb: 1,
                   fs: 0, modestbranding: 1, iv_load_policy: 3, start: {start}, autoplay: 1 }},
    host: '{EMBED_HOST}',
    events: {{
      onReady: function () {{ ready = true; send('ready', {{}}); poll(); setInterval(poll, 500); }},
      onStateChange: function (e) {{ send('state', {{ state: e.data }}); }},
      onError: function (e) {{ send('error', {{ code: e.data }}); }},
      onPlaybackQualityChange: function (e) {{ send('quality', {{ level: e.data }}); }},
      onPlaybackRateChange: function (e) {{ send('rate', {{ rate: e.data }}); }}
    }}
  }});
}}
window.dino = {{
  play: function () {{ if (ready) player.playVideo(); }},
  pause: function () {{ if (ready) player.pauseVideo(); }},
  seek: function (t) {{ if (ready) player.seekTo(t, true); }},
  quality: function (q) {{
    if (!ready) return;
    if (player.setPlaybackQualityRange) player.setPlaybackQualityRange(q, q);
    player.setPlaybackQuality(q);
  }},
  rate: function (r) {{ if (ready) player.setPlaybackRate(r); }},
  volume: function (v) {{ if (ready) player.setVolume(v); }},
  mute: function (m) {{ if (!ready) return; if (m) player.mute(); else player.unMute(); }}
}};
</script>
{api}
</body></html>"""


class EmbedBridge(QObject):
    """Recebe as mensagens da página (via QWebChannel) e as transforma em sinais tipados."""

    ready = Signal()
    state_changed = Signal(int)
    time_changed = Signal(float, float)  # posição, duração (s)
    quality_changed = Signal(str, list)  # nível atual, níveis disponíveis
    status_changed = Signal(float, bool, float)  # volume (0-100), mudo, velocidade
    error = Signal(str, int)  # código estável, código do YouTube
    channel_ready = Signal()

    @Slot(str, str)
    def message(self, kind, payload):
        try:
            data = json.loads(payload or "{}")
        except ValueError:
            return
        if kind == "channel":
            self.channel_ready.emit()
        elif kind == "ready":
            self.ready.emit()
        elif kind == "state":
            self.state_changed.emit(int(data.get("state", -1)))
        elif kind == "time":
            self.time_changed.emit(float(data.get("t") or 0), float(data.get("d") or 0))
            self.quality_changed.emit(str(data.get("q") or ""), list(data.get("levels") or []))
            self.status_changed.emit(float(data.get("v") or 0), bool(data.get("m")), float(data.get("r") or 1))
            if data.get("s") is not None:
                self.state_changed.emit(int(data["s"]))
        elif kind == "quality":
            self.quality_changed.emit(str(data.get("level") or ""), [])
        elif kind == "error":
            code = int(data.get("code", 0))
            self.error.emit(map_error(code), code)
