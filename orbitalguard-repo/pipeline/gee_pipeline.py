"""
OrbitalGuard — Pipeline Google Earth Engine
Detecta deformação de solo na região de Brumadinho/MG
usando imagens Sentinel-1 SAR (pré/pós desastre 25 jan 2019)
"""

import ee
import geemap
import json
from pathlib import Path

# ─── INICIALIZAR GEE ─────────────────────────────────────────────────────────
ee.Initialize(project="projeto-34-497813")

# ─── ÁREA DE INTERESSE ────────────────────────────────────────────────────────
AOI = ee.Geometry.Rectangle([-44.20, -20.20, -43.90, -20.00])

# ─── CARREGAR IMAGENS SENTINEL-1 ─────────────────────────────────────────────
def carregar_s1(data_inicio, data_fim, label=""):
    colecao = (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filterBounds(AOI)
        .filterDate(data_inicio, data_fim)
        .filter(ee.Filter.eq("instrumentMode", "IW"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
        .select("VV")
    )

    total = colecao.size().getInfo()
    print(f"  [{label}] {total} imagem(ns) encontrada(s) entre {data_inicio} e {data_fim}")

    if total == 0:
        raise ValueError(f"Nenhuma imagem encontrada para o período {data_inicio} → {data_fim}")

    return colecao.mean().clip(AOI)

print("\n📡 Carregando imagens Sentinel-1...")
pre = carregar_s1("2018-12-01", "2019-01-24", "PRÉ-DESASTRE")
pos = carregar_s1("2019-01-26", "2019-02-28", "PÓS-DESASTRE")
print("✅ Imagens carregadas\n")

# ─── CALCULAR DIFERENÇA (PROXY DE DEFORMAÇÃO) ────────────────────────────────
# Diferença em dB entre pré e pós
# Valores negativos = redução de retorno radar = deformação/colapso/inundação
diferenca = pos.subtract(pre).rename("deformacao_dB")
risco     = diferenca.lt(-3).rename("risco_alto")
print("✅ Análise de deformação calculada")

# ─── ESTATÍSTICAS ─────────────────────────────────────────────────────────────
print("\n📊 Calculando estatísticas...")
stats = diferenca.reduceRegion(
    reducer=ee.Reducer.min().combine(ee.Reducer.max(), "", True)
                            .combine(ee.Reducer.mean(), "", True),
    geometry=AOI,
    scale=20,
    maxPixels=1e9,
    bestEffort=True
)
print(json.dumps(stats.getInfo(), indent=2))

# ─── MAPA INTERATIVO ──────────────────────────────────────────────────────────
print("\n🗺️  Gerando mapa interativo...")
mapa = geemap.Map(center=[-20.10, -44.05], zoom=11)

mapa.addLayer(
    pre,
    {"min": -25, "max": 0, "palette": ["black", "white"]},
    "SAR pré-desastre (jan/2019)"
)
mapa.addLayer(
    pos,
    {"min": -25, "max": 0, "palette": ["black", "white"]},
    "SAR pós-desastre (fev/2019)"
)
mapa.addLayer(
    diferenca,
    {"min": -10, "max": 5, "palette": ["#0000FF", "#FFFFFF", "#FF0000"]},
    "Deformação SAR (dB)"
)
mapa.addLayer(
    risco,
    {"min": 0, "max": 1, "palette": ["#FFFFFF00", "#FF0000"]},
    "Área de risco alto"
)

# Marcador da Barragem B1 de Brumadinho
barragem = ee.Geometry.Point([-44.1228, -20.1192])
mapa.addLayer(barragem, {"color": "yellow"}, "Barragem B1 — Brumadinho")

mapa.add_colorbar(
    vis_params={"min": -10, "max": 5, "palette": ["#0000FF", "#FFFFFF", "#FF0000"]},
    label="Deformação SAR (dB) — Azul: subsidência | Vermelho: soerguimento",
    position="bottomright"
)

# ─── SALVAR HTML ──────────────────────────────────────────────────────────────
OUTPUT_DIR = Path("./output")
OUTPUT_DIR.mkdir(exist_ok=True)
mapa_path = OUTPUT_DIR / "orbitalguard_mapa.html"
mapa.save(str(mapa_path))

print(f"✅ Mapa salvo em: {mapa_path}")
print("\n🎉 Pipeline concluído! Abre o arquivo output/orbitalguard_mapa.html no Chrome.")
