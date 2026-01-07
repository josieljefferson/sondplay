# app.py
from flask import Flask, Response, redirect, request, jsonify
from flask import send_file
import subprocess
import re
import os
import json
from datetime import datetime

app = Flask(__name__)

# ===============================
# CONFIGURAÇÕES GERAIS
# ===============================

PORT = int(os.environ.get("PORT", 8080))
HOST = "0.0.0.0"

def server_url():
    """Retorna a URL base do servidor"""
    return os.environ.get(
        "SERVER_URL",
        request.host_url.rstrip("/") if request.host_url else "http://localhost:8080"
    )

# ===============================
# CARREGAR CANAIS DO JSON
# ===============================

def load_channels_from_json():
    """Carrega todos os canais do arquivo channels.json"""
    try:
        with open('channels.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        channels = {}
        used_tvg_ids = set()  # Para evitar duplicatas
        
        # Processar cada canal do JSON
        for channel in data.get('channels', []):
            # Gerar ID único baseado no nome
            name = channel.get('name', '')
            key = re.sub(r"[^a-z0-9]", "_", name.lower()).strip('_')
            
            # Evitar duplicatas
            if not key or key in channels:
                continue
            
            # Extrair informações
            url = channel.get('url', '')
            tvg_id = channel.get('tvg-id', key)
            
            # Marcar tvg-id como usado para o EPG
            used_tvg_ids.add(tvg_id)
            
            # Determinar tipo de stream
            stream_type = "youtube" if "youtube.com" in url or "youtu.be" in url else "direct"
            
            channels[key] = {
                "id": key,
                "name": name,
                "url": url,
                "tvg_id": tvg_id,
                "logo": channel.get('tvg-logo', ''),
                "group": channel.get('group-title', 'GERAL'),
                "type": stream_type,
                "source": "json"  # Marcar que veio do JSON
            }
        
        print(f"✅ Carregados {len(channels)} canais do JSON")
        return channels, list(used_tvg_ids)
        
    except Exception as e:
        print(f"❌ Erro ao carregar channels.json: {e}")
        return {}, []

# Carregar canais uma vez ao iniciar
JSON_CHANNELS, USED_TVG_IDS = load_channels_from_json()

# ===============================
# CANAIS YOUTUBE ESPECIAIS (manter compatibilidade)
# ===============================

CANAIS_YT = {
    "tvassembleia": {
        "name": "TV Assembleia PI",
        "url": "https://www.youtube.com/@tvassembleia-pi/live",
        "group": "YOUTUBE",
        "tvg_id": "tvassembleia"
    },
    "tv_cancao_nova": {
        "name": "TV Canção Nova",
        "url": "https://www.youtube.com/user/tvcancaonova/live",
        "group": "YOUTUBE",
        "tvg_id": "tv_cancao_nova"
    }
}

# Adicionar IDs especiais ao conjunto de IDs usados
USED_TVG_IDS.extend(["tvassembleia", "tv_cancao_nova"])

# ===============================
# COMBINAR TODOS OS CANAIS
# ===============================

ALL_CHANNELS = {**CANAIS_YT, **JSON_CHANNELS}

# ===============================
# HOME PAGE
# ===============================

@app.route("/")
def index():
    """Página inicial com lista de canais"""
    
    # Calcular estatísticas
    yt_count = len(CANAIS_YT)
    json_count = len(JSON_CHANNELS)
    total_count = len(ALL_CHANNELS)
    tvg_count = len(set(USED_TVG_IDS))
    server_url_value = server_url()
    date = datetime.now().strftime("%d/%m/%Y")
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>📺 Servidor IPTV Integrado</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
            .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            h1 {{ color: #333; border-bottom: 2px solid #4CAF50; padding-bottom: 10px; }}
            .stats {{ background: #e8f5e9; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
            .channels-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 15px; }}
            .channel-card {{ background: white; border: 1px solid #ddd; border-radius: 8px; padding: 15px; transition: transform 0.2s; }}
            .channel-card:hover {{ transform: translateY(-3px); box-shadow: 0 5px 15px rgba(0,0,0,0.1); }}
            .channel-logo {{ max-width: 60px; max-height: 60px; margin-right: 15px; float: left; }}
            .channel-name {{ font-weight: bold; margin-bottom: 5px; }}
            .channel-group {{ color: #666; font-size: 0.9em; }}
            .channel-actions {{ margin-top: 10px; }}
            .btn {{ display: inline-block; padding: 8px 15px; background: #4CAF50; color: white; text-decoration: none; border-radius: 4px; margin-right: 10px; }}
            .btn:hover {{ background: #45a049; }}
            .footer {{ margin-top: 30px; text-align: center; color: #666; }}
            .filter {{ margin-bottom: 20px; }}
            .filter input {{ padding: 10px; width: 100%; box-sizing: border-box; border: 1px solid #ddd; border-radius: 4px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📺 Servidor IPTV Integrado</h1>
            
            <div class="stats">
                <strong>📊 Estatísticas:</strong><br>
                • Canais YouTube: {yt_count}<br>
                • Canais do JSON: {json_count}<br>
                • Total de Canais: {total_count}<br>
                • IDs TVG para EPG: {tvg_count}
            </div>
            
            <div class="filter">
                <input type="text" id="search" placeholder="🔍 Buscar canal por nome ou grupo..." onkeyup="filterChannels()">
            </div>
            
            <h2>Canais Disponíveis ({total_count})</h2>
            <div class="channels-grid" id="channels-grid">
    """
    
    # Adicionar cards para cada canal
    for key, channel in ALL_CHANNELS.items():
        logo_html = f'<img src="{channel.get("logo", "")}" class="channel-logo" alt="Logo" onerror="this.style.display=\'none\'">' if channel.get("logo") else ''
        html += f"""
                <div class="channel-card" data-name="{channel['name'].lower()}" data-group="{channel.get('group', '').lower()}">
                    {logo_html}
                    <div class="channel-name">{channel['name']}</div>
                    <div class="channel-group">📁 {channel.get('group', 'GERAL')}</div>
                    <div class="channel-group">🔗 {channel.get('type', 'direct').upper()}</div>
                    <div class="channel-actions">
                        <a href="/{key}" class="btn" target="_blank">▶ Assistir</a>
                        <a href="/play/{key}" class="btn" style="background: #2196F3;">📺 Player</a>
                    </div>
                </div>
        """
    
    html += f"""
            </div>
            
            <div style="margin-top: 30px; padding: 20px; background: #e3f2fd; border-radius: 8px;">
                <h3>📋 Links Úteis</h3>
                <p>
                    <a href="/playlist.m3u" class="btn">📥 Playlist M3U</a>
                    <a href="/channels" class="btn" style="background: #9C27B0;">📊 API JSON</a>
                    <a href="/epg.xml" class="btn" style="background: #FF9800;">📺 Guia de Programação (EPG)</a>
                    <a href="/health" class="btn" style="background: #607D8B;">🩺 Health Check</a>
                </p>
                <p style="margin-top: 15px;">
                    <strong>Para usar no IPTV Player:</strong><br>
                    URL da Playlist: <code>{server_url_value}/playlist.m3u</code><br>
                    URL do EPG: <code>{server_url_value}/epg.xml</code>
                </p>
            </div>
            
            <div class="footer">
                <p>Servidor IPTV • {date} • Total de canais: {total_count}</p>
                <p><a href="https://github.com/seu-usuario/seu-repo" target="_blank">📁 Ver no GitHub</a></p>
            </div>
        </div>
        
        <script>
            function filterChannels() {{
                var input = document.getElementById('search');
                var filter = input.value.toLowerCase();
                var cards = document.querySelectorAll('.channel-card');
                
                for (var i = 0; i < cards.length; i++) {{
                    var name = cards[i].getAttribute('data-name');
                    var group = cards[i].getAttribute('data-group');
                    
                    if (name.includes(filter) || group.includes(filter)) {{
                        cards[i].style.display = 'block';
                    }} else {{
                        cards[i].style.display = 'none';
                    }}
                }}
            }}
        </script>
    </body>
    </html>
    """
    
    return html

# ===============================
# PLAYER DE VÍDEO EMBUTIDO
# ===============================

@app.route("/play/<canal>")
def player(canal):
    """Player de vídeo embutido"""
    if canal not in ALL_CHANNELS:
        return "Canal não encontrado", 404
    
    channel = ALL_CHANNELS[canal]
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Player: {channel['name']}</title>
        <style>
            body {{ margin: 0; padding: 0; background: #000; }}
            .player-container {{ position: fixed; top: 0; left: 0; right: 0; bottom: 0; }}
            .video-container {{ width: 100%; height: 100%; }}
            .controls {{ position: fixed; bottom: 0; left: 0; right: 0; background: rgba(0,0,0,0.8); padding: 15px; display: flex; justify-content: space-between; align-items: center; }}
            .channel-info {{ color: white; }}
            .btn {{ background: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; margin: 0 5px; }}
        </style>
    </head>
    <body>
        <div class="player-container">
            <div class="video-container">
                <iframe 
                    src="/{canal}" 
                    width="100%" 
                    height="100%" 
                    frameborder="0" 
                    allowfullscreen
                    allow="autoplay; encrypted-media"
                ></iframe>
            </div>
            <div class="controls">
                <div class="channel-info">
                    <h3 style="margin: 0; color: white;">{channel['name']}</h3>
                    <p style="margin: 5px 0 0 0; color: #ccc;">{channel.get('group', 'GERAL')}</p>
                </div>
                <div>
                    <a href="/" class="btn">🏠 Voltar</a>
                    <a href="/{canal}" target="_blank" class="btn" style="background: #2196F3;">🔗 Abrir Direto</a>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html

# ===============================
# STREAM DE VÍDEO
# ===============================

def yt_stream(url):
    """Extrai stream URL do YouTube usando yt-dlp"""
    try:
        stream_url = subprocess.check_output(
            ["yt-dlp", "-f", "best", "--get-url", url],
            stderr=subprocess.DEVNULL,
            text=True
        ).splitlines()[0]
        return redirect(stream_url)
    except Exception as e:
        print(f"❌ Erro yt-dlp para {url}: {e}")
        # Fallback para o URL original
        return redirect(url)

@app.route("/<canal>")
def stream(canal):
    """Rota principal para streaming"""
    if canal in CANAIS_YT:
        return yt_stream(CANAIS_YT[canal]["url"])
    
    if canal in JSON_CHANNELS:
        ch = JSON_CHANNELS[canal]
        if ch["type"] == "youtube":
            return yt_stream(ch["url"])
        else:
            return redirect(ch["url"])
    
    return "Canal não encontrado", 404

# ===============================
# PLAYLIST M3U
# ===============================

@app.route("/playlist.m3u")
def playlist():
    """Gera playlist M3U8"""
    base = server_url()
    out = f"""#EXTM3U x-tvg-url="{base}/epg.xml"
#PLAYLISTV: pltv-logo="https://cdn-icons-png.flaticon.com/256/25/25231.png" pltv-name="Servidor IPTV Integrado" pltv-description="Canais do JSON + YouTube" pltv-cover="https://images.icon-icons.com/2407/PNG/512/gitlab_icon_146171.png" pltv-author="Sistema Integrado" pltv-site="{base}"

"""
    
    # Adicionar canais YouTube especiais
    for key, channel in CANAIS_YT.items():
        out += f'#EXTINF:-1 tvg-id="{channel["tvg_id"]}" tvg-logo="" group-title="{channel["group"]}",{channel["name"]}\n'
        out += f'{base}/{key}\n\n'
    
    # Adicionar canais do JSON
    for key, channel in JSON_CHANNELS.items():
        logo = channel.get("logo", "")
        group = channel.get("group", "GERAL")
        
        out += f'#EXTINF:-1 tvg-id="{channel["tvg_id"]}" tvg-logo="{logo}" group-title="{group}",{channel["name"]}\n'
        
        if channel["type"] == "youtube":
            out += f'{base}/{key}\n\n'
        else:
            out += f'{channel["url"]}\n\n'
    
    return Response(out, mimetype="audio/x-mpegurl")

# ===============================
# API JSON
# ===============================

@app.route("/channels")
def channels_api():
    """API JSON com todos os canais"""
    channels_list = []
    
    # Adicionar canais YouTube
    for key, channel in CANAIS_YT.items():
        channels_list.append({
            "id": key,
            "name": channel["name"],
            "url": f"{server_url()}/{key}",
            "tvg_id": channel["tvg_id"],
            "logo": channel.get("logo", ""),
            "group": channel["group"],
            "type": "youtube",
            "source": "youtube_special"
        })
    
    # Adicionar canais do JSON
    for key, channel in JSON_CHANNELS.items():
        channels_list.append({
            "id": key,
            "name": channel["name"],
            "url": channel["url"] if channel["type"] == "direct" else f"{server_url()}/{key}",
            "tvg_id": channel["tvg_id"],
            "logo": channel.get("logo", ""),
            "group": channel.get("group", "GERAL"),
            "type": channel["type"],
            "source": "json"
        })
    
    return jsonify({
        "metadata": {
            "server": server_url(),
            "total_channels": len(channels_list),
            "generated_at": datetime.now().isoformat(),
            "youtube_special": len(CANAIS_YT),
            "from_json": len(JSON_CHANNELS)
        },
        "channels": channels_list
    })

# ===============================
# EPG ENDPOINT
# ===============================

@app.route("/epg.xml")
def epg():
    """Serve o arquivo EPG gerado"""
    try:
        return send_file("epg.xml", mimetype="application/xml", as_attachment=False)
    except:
        return "EPG não disponível. Execute epg.py primeiro.", 404

# ===============================
# HEALTH CHECK
# ===============================

@app.route("/health")
def health():
    """Endpoint de saúde da aplicação"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "channels": {
            "youtube_special": len(CANAIS_YT),
            "from_json": len(JSON_CHANNELS),
            "total": len(ALL_CHANNELS)
        },
        "epg_channels": len(set(USED_TVG_IDS)),
        "server_url": server_url()
    })

# ===============================
# MAIN
# ===============================

if __name__ == "__main__":
    print("=" * 50)
    print("🚀 Servidor IPTV Integrado")
    print("=" * 50)
    print(f"📊 Canais carregados: {len(ALL_CHANNELS)}")
    print(f"📺 IDs TVG para EPG: {len(set(USED_TVG_IDS))}")
    print(f"🌐 URL: http://{HOST}:{PORT}")
    print("=" * 50)
    
    # Salvar lista de IDs TVG para o EPG
    with open('used_tvg_ids.txt', 'w') as f:
        f.write('\n'.join(set(USED_TVG_IDS)))
    
    app.run(host=HOST, port=PORT, debug=False)