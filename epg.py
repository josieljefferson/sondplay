# epg.py
import gzip
import shutil
import requests
import xml.etree.ElementTree as ET
from pathlib import Path
import json
import time

# =============================
# CONFIGURAÇÃO
# =============================

EPG_SOURCES = [
    "https://m3u4u.com/epg/jq2zy9epr3bwxmgwyxr5",
    "https://m3u4u.com/epg/3wk1y24kx7uzdevxygz7",
    "https://m3u4u.com/epg/782dyqdrqkh1xegen4zp",
    "https://www.open-epg.com/files/brazil1.xml.gz",
    "https://www.open-epg.com/files/brazil2.xml.gz",
    "https://www.open-epg.com/files/brazil3.xml.gz",
    "https://www.open-epg.com/files/brazil4.xml.gz",
    "https://www.open-epg.com/files/portugal1.xml.gz",
    "https://www.open-epg.com/files/portugal2.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_BR1.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_PT1.xml.gz"
]

OUTPUT = Path("epg.xml")
TMP = Path("tmp_epg")
TMP.mkdir(exist_ok=True)

# =============================
# CARREGAR IDs TVG USADOS
# =============================

def load_used_tvg_ids():
    """Carrega os IDs TVG dos canais que usamos"""
    try:
        # Primeiro, tentar do arquivo gerado pelo app.py
        if Path('used_tvg_ids.txt').exists():
            with open('used_tvg_ids.txt', 'r') as f:
                ids = [line.strip() for line in f if line.strip()]
            print(f"📋 Carregados {len(ids)} IDs TVG do arquivo")
            return set(ids)
        
        # Se não existir, carregar do JSON diretamente
        with open('channels.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        ids = set()
        for channel in data.get('channels', []):
            tvg_id = channel.get('tvg-id')
            if tvg_id:
                ids.add(tvg_id)
        
        # Adicionar canais YouTube especiais
        ids.update(['tvassembleia', 'tv_cancao_nova'])
        
        print(f"📋 Carregados {len(ids)} IDs TVG do JSON")
        return ids
        
    except Exception as e:
        print(f"❌ Erro ao carregar IDs TVG: {e}")
        # Lista padrão como fallback
        return {
            'tvassembleia', 'tv_cancao_nova', 
            'CancaoNova(Portuguese).br', 'TVAntena10(Portuguese).br',
            'SBT(Portuguese).br', 'Cultura(Portuguese).br'
        }

# =============================
# BAIXAR E PROCESSAR EPG
# =============================

def download_and_process():
    """Baixa e processa todas as fontes EPG"""
    USED_CHANNELS = load_used_tvg_ids()
    print(f"🎯 Buscando EPG para {len(USED_CHANNELS)} canais")
    
    root = ET.Element("tv")
    channels_added = set()
    programmes_added = 0
    
    for idx, src in enumerate(EPG_SOURCES, 1):
        try:
            name = src.split("/")[-1]
            gz_path = TMP / name
            xml_path = TMP / name.replace(".gz", "")
            
            print(f"\n[{idx}/{len(EPG_SOURCES)}] ⬇️ Baixando {src}")
            
            # Baixar arquivo
            r = requests.get(src, timeout=30)
            r.raise_for_status()
            gz_path.write_bytes(r.content)
            
            # Descompactar se for .gz
            if src.endswith('.gz'):
                with gzip.open(gz_path, "rb") as f_in, open(xml_path, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
            else:
                xml_path.write_bytes(r.content)
            
            # Processar XML
            try:
                tree = ET.parse(xml_path)
                tv = tree.getroot()
                
                # Adicionar canais
                for ch in tv.findall("channel"):
                    ch_id = ch.attrib.get("id")
                    if ch_id in USED_CHANNELS and ch_id not in channels_added:
                        root.append(ch)
                        channels_added.add(ch_id)
                
                # Adicionar programas
                for pr in tv.findall("programme"):
                    pr_channel = pr.attrib.get("channel")
                    if pr_channel in USED_CHANNELS:
                        root.append(pr)
                        programmes_added += 1
                
                print(f"   ✅ Processado: {len(channels_added)} canais, {programmes_added} programas")
                
            except ET.ParseError as e:
                print(f"   ⚠️ Erro ao parsear XML: {e}")
                continue
                
        except Exception as e:
            print(f"   ❌ Erro ao processar fonte: {e}")
            continue
    
    return root, len(channels_added), programmes_added

# =============================
# CRIAR EPG PARA CANAIS SEM DADOS
# =============================

def create_fallback_epg(root, channels_added):
    """Cria entradas básicas para canais sem EPG"""
    USED_CHANNELS = load_used_tvg_ids()
    
    for ch_id in USED_CHANNELS:
        if ch_id not in channels_added:
            # Criar canal básico
            channel_elem = ET.Element("channel", {"id": ch_id})
            
            display_name = ET.SubElement(channel_elem, "display-name")
            display_name.text = ch_id
            
            icon_elem = ET.SubElement(channel_elem, "icon")
            icon_elem.set("src", "")
            
            root.append(channel_elem)
            
            # Criar programa placeholder
            programme_elem = ET.Element("programme", {
                "channel": ch_id,
                "start": "20240101000000 +0000",
                "stop": "20300101000000 +0000"
            })
            
            title_elem = ET.SubElement(programme_elem, "title")
            title_elem.text = "Programação Indisponível"
            
            desc_elem = ET.SubElement(programme_elem, "desc")
            desc_elem.text = "Informações de programação não disponíveis para este canal."
            
            root.append(programme_elem)
    
    return root

# =============================
# FUNÇÃO PRINCIPAL
# =============================

def main():
    """Função principal"""
    print("=" * 60)
    print("📡 GERADOR DE EPG INTEGRADO")
    print("=" * 60)
    
    start_time = time.time()
    
    # Baixar e processar EPG
    root, channels_count, programmes_count = download_and_process()
    
    # Adicionar fallback para canais sem dados
    root = create_fallback_epg(root, set())
    
    # Salvar arquivo final
    ET.ElementTree(root).write(
        OUTPUT,
        encoding="utf-8",
        xml_declaration=True,
        short_empty_elements=False
    )
    
    elapsed = time.time() - start_time
    
    print("\n" + "=" * 60)
    print("✅ EPG GERADO COM SUCESSO!")
    print("=" * 60)
    print(f"📊 Estatísticas:")
    print(f"   • Canais com EPG: {channels_count}")
    print(f"   • Programas: {programmes_count}")
    print(f"   • Arquivo: {OUTPUT} ({OUTPUT.stat().st_size / 1024:.1f} KB)")
    print(f"   • Tempo total: {elapsed:.1f} segundos")
    print(f"   • Fontes processadas: {len(EPG_SOURCES)}")
    print("=" * 60)
    print("\n📌 Para usar no IPTV Player:")
    print(f"   URL do EPG: http://seu-servidor/epg.xml")
    print("\n🔄 Para atualizar periodicamente, execute:")
    print("   python epg.py")
    print("=" * 60)

# =============================
# EXECUTAR
# =============================

if __name__ == "__main__":
    main()