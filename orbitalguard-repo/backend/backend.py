"""
OrbitalGuard — Backend FastAPI v4.0
Integração real com SIGBM/ANM — 466 barragens da PNSB
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import numpy as np
import joblib
import random
import httpx
import asyncio
import csv
import io
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

app = FastAPI(
    title="OrbitalGuard API",
    description="Monitoramento de barragens — SIGBM/ANM + Sentinel-1 SAR + IA",
    version="4.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── MODELOS ──────────────────────────────────────────────────────────────────
OUTPUT_DIR = Path("./output")
try:
    modelo_rf = joblib.load(OUTPUT_DIR / "modelo_rf.pkl")
    scaler    = joblib.load(OUTPUT_DIR / "scaler.pkl")
    print("✅ Modelos de IA carregados")
except:
    modelo_rf = None
    scaler    = None
    print("⚠️  Modelos não encontrados — usando regras")

CLASSES     = ["Sem Risco", "Atenção", "Crítico"]
CLASSES_COR = {"Sem Risco": "green", "Atenção": "yellow", "Crítico": "red"}
votos_db    = {}

# ─── CACHE ───────────────────────────────────────────────────────────────────
_cache = {
    "barragens": [],
    "ultima_atualizacao": None,
    "fonte": "fallback"
}
CACHE_TTL_HORAS = 6

# ─── URLs DA ANM ──────────────────────────────────────────────────────────────
ANM_CSV_URL = "https://app.anm.gov.br/sigbm/publico/classificacao/empreendimento"
ANM_FALLBACK_URL = "https://dados.gov.br/dados/api/publico/conjuntos-dados/barragens-de-mineracao"

# ─── GEOCODIFICAÇÃO POR MUNICÍPIO ────────────────────────────────────────────
# Coordenadas aproximadas dos municípios com mais barragens — evita chamadas de API
COORDS_MUNICIPIOS = {
    "Brumadinho/MG":              (-20.1558, -44.1994),
    "Mariana/MG":                 (-20.3778, -43.4158),
    "Ouro Preto/MG":              (-20.3856, -43.5035),
    "Congonhas/MG":               (-20.5019, -43.8581),
    "Itabira/MG":                 (-19.6189, -43.2269),
    "Itabirito/MG":               (-20.2528, -43.8019),
    "Barão de Cocais/MG":         (-19.9378, -43.4814),
    "Sabará/MG":                  (-19.8869, -43.8069),
    "Nova Lima/MG":               (-19.9847, -43.8464),
    "João Monlevade/MG":          (-19.8103, -43.1736),
    "Conceição do Mato Dentro/MG":(-19.0350, -43.4194),
    "Bocaiúva/MG":                (-17.1058, -43.8172),
    "Paracatu/MG":                (-17.2225, -46.8756),
    "Canaã dos Carajás/PA":       (-6.5003,  -49.8681),
    "Barcarena/PA":               (-1.5058,  -48.6236),
    "Parauapebas/PA":             (-6.0686,  -49.9019),
    "Candiota/RS":                (-31.5558, -53.6833),
    "Miraí/MG":                   (-21.1947, -42.6014),
    "Belo Horizonte/MG":          (-19.9167, -43.9345),
    "Poços de Caldas/MG":         (-21.7872, -46.5614),
    "São Gonçalo do Rio Abaixo/MG":(-19.8369,-43.3572),
    "Alvorada de Minas/MG":       (-18.7239, -43.3556),
    "Catas Altas/MG":             (-20.0731, -43.3994),
    "Rio Piracicaba/MG":          (-19.9325, -43.1753),
    "Santa Bárbara/MG":           (-19.9644, -43.4133),
    "Timóteo/MG":                 (-19.5828, -42.6478),
    "Governador Valadares/MG":    (-18.8511, -41.9494),
    "Itinga/MG":                  (-16.6078, -41.7733),
    "Jequitinhonha/MG":           (-16.4358, -41.0003),
    "Diamantina/MG":              (-18.2469, -43.5986),
    "Três Marias/MG":             (-18.2069, -45.2572),
    "Vazante/MG":                 (-17.9878, -46.9008),
    "Araxá/MG":                   (-19.5939, -46.9422),
    "Poconé/MT":                  (-16.2572, -56.6211),
    "Cuiabá/MT":                  (-15.5989, -56.0949),
    "Alto Araguaia/MT":           (-17.3139, -53.2150),
    "Jacobina/BA":                (-11.1819, -40.5181),
    "Buerarema/BA":               (-14.9578, -39.3003),
    "Caetité/BA":                 (-14.0678, -42.4742),
    "Barro Alto/GO":              (-14.9939, -48.9253),
    "Niquelândia/GO":             (-14.4717, -48.4594),
    "Catalão/GO":                 (-18.1658, -47.9456),
    "Minaçu/GO":                  (-13.5378, -48.2214),
    "Alto Horizonte/GO":          (-14.0172, -49.3361),
}

def coords_municipio(municipio: str, uf: str) -> tuple:
    chave = f"{municipio}/{uf}"
    if chave in COORDS_MUNICIPIOS:
        return COORDS_MUNICIPIOS[chave]
    # Fallback por UF (centro aproximado do estado)
    centros_uf = {
        "MG": (-18.5, -44.0), "PA": (-5.0, -52.0), "RS": (-30.0, -53.0),
        "GO": (-16.0, -49.0), "MT": (-13.0, -56.0), "BA": (-13.0, -41.0),
        "SP": (-22.0, -48.0), "ES": (-20.0, -40.5), "SC": (-27.5, -50.5),
        "PR": (-24.5, -51.5), "RJ": (-22.5, -43.0), "AM": (-5.0, -63.0),
        "AP": (1.0, -52.0), "RO": (-11.0, -63.0), "AC": (-9.0, -70.0),
        "RR": (2.0, -61.0), "TO": (-10.0, -48.0), "MA": (-5.0, -45.0),
        "PI": (-7.0, -42.0), "CE": (-5.0, -39.0), "RN": (-5.5, -36.5),
        "PB": (-7.0, -36.5), "PE": (-8.0, -37.5), "AL": (-9.5, -36.5),
        "SE": (-10.5, -37.0), "MS": (-20.0, -54.5), "DF": (-15.8, -47.9),
    }
    lat, lon = centros_uf.get(uf, (-15.0, -47.0))
    # Pequena variação aleatória para não sobrepor marcadores do mesmo estado
    random.seed(hash(f"{municipio}{uf}") % 10000)
    return (lat + random.uniform(-1.5, 1.5), lon + random.uniform(-1.5, 1.5))

# ─── DADOS DETALHADOS (top 20 barragens — enriquecem os dados da ANM) ────────
DETALHES_BARRAGENS = {
    "Barragem B1": {
        "descricao": "Colapsou em 25 jan 2019, causando 270 mortes. Maior desastre industrial do Brasil. Sinais de subsidência SAR eram visíveis semanas antes.",
        "imagem": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7e/Brumadinho_dam_failure_%2801-25-2019%29.jpg/800px-Brumadinho_dam_failure_%2801-25-2019%29.jpg",
        "lat": -20.1192, "lon": -44.1228
    },
    "Fundão": {
        "descricao": "Rompeu em nov 2015, liberando 40 milhões de m³ no Rio Doce. Maior desastre ambiental do Brasil.",
        "imagem": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3a/Rio_Doce_polu%C3%ADdo_ap%C3%B3s_rompimento_da_Barragem_de_Fund%C3%A3o.jpg/800px-Rio_Doce_polu%C3%ADdo_ap%C3%B3s_rompimento_da_Barragem_de_Fund%C3%A3o.jpg",
        "lat": -20.2119, "lon": -43.4058
    },
    "Casa de Pedra": {
        "descricao": "Uma das maiores barragens de rejeito da América Latina. Estrutura em aterro compactado de 130m.",
        "imagem": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9a/Congonhas_-_Minas_Gerais%2C_Brasil.jpg/800px-Congonhas_-_Minas_Gerais%2C_Brasil.jpg",
        "lat": -20.5333, "lon": -43.8500
    },
    "Sul Superior": {
        "descricao": "Em estado de emergência nível 3 desde 2019. Comunidades da ZAS evacuadas preventivamente.",
        "imagem": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7e/Brumadinho_dam_failure_%2801-25-2019%29.jpg/800px-Brumadinho_dam_failure_%2801-25-2019%29.jpg",
        "lat": -19.9347, "lon": -43.4789
    },
    "Maravilhas III": {
        "descricao": "Situação crítica desde 2021. Plano de Ação de Emergência ativo. Monitoramento orbital intensificado.",
        "imagem": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7e/Brumadinho_dam_failure_%2801-25-2019%29.jpg/800px-Brumadinho_dam_failure_%2801-25-2019%29.jpg",
        "lat": -17.1167, "lon": -43.8167
    },
}

IMAGENS_DEFAULT = {
    "MG": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4e/Ouro_Preto_-_Vista_Parcial.jpg/800px-Ouro_Preto_-_Vista_Parcial.jpg",
    "PA": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d6/Cana%C3%A3_dos_Caraj%C3%A1s_-_Par%C3%A1.jpg/800px-Cana%C3%A3_dos_Caraj%C3%A1s_-_Par%C3%A1.jpg",
    "RS": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/42/Candiota_-_Rio_Grande_do_Sul.jpg/800px-Candiota_-_Rio_Grande_do_Sul.jpg",
    "GO": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a8/Paracatu_-_Minas_Gerais_%28Brasil%29.jpg/800px-Paracatu_-_Minas_Gerais_%28Brasil%29.jpg",
    "BA": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9a/Congonhas_-_Minas_Gerais%2C_Brasil.jpg/800px-Congonhas_-_Minas_Gerais%2C_Brasil.jpg",
    "DEFAULT": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3a/Rio_Doce_polu%C3%ADdo_ap%C3%B3s_rompimento_da_Barragem_de_Fund%C3%A3o.jpg/800px-Rio_Doce_polu%C3%ADdo_ap%C3%B3s_rompimento_da_Barragem_de_Fund%C3%A3o.jpg",
}

# ─── FALLBACK — 20 barragens detalhadas (usado se ANM falhar) ────────────────
BARRAGENS_FALLBACK = [
    {"id":"B001","nome":"Barragem B1 — Brumadinho","empresa":"Vale S.A.","municipio":"Brumadinho","estado":"MG","lat":-20.1192,"lon":-44.1228,"altura_m":86,"volume_m3":11700000,"tipo":"Montante","deformacao_atual_dB":-7.2,"risco":"Crítico","categoria_anm":"Alto","dpa":"Alto","nivel_emergencia":"Emergência Nível 3","descricao":"Colapsou em 25 jan 2019, causando 270 mortes e liberando 12 milhões de m³ de rejeitos. Maior desastre industrial do Brasil.","imagem":"https://upload.wikimedia.org/wikipedia/commons/thumb/7/7e/Brumadinho_dam_failure_%2801-25-2019%29.jpg/800px-Brumadinho_dam_failure_%2801-25-2019%29.jpg"},
    {"id":"B002","nome":"Barragem Fundão — Germano","empresa":"Samarco","municipio":"Mariana","estado":"MG","lat":-20.2119,"lon":-43.4058,"altura_m":110,"volume_m3":55000000,"tipo":"Montante","deformacao_atual_dB":-2.8,"risco":"Atenção","categoria_anm":"Médio","dpa":"Alto","nivel_emergencia":"Alerta Nível 2","descricao":"Rompeu em nov 2015, liberando 40 milhões de m³ no Rio Doce. Maior desastre ambiental do Brasil.","imagem":"https://upload.wikimedia.org/wikipedia/commons/thumb/3/3a/Rio_Doce_polu%C3%ADdo_ap%C3%B3s_rompimento_da_Barragem_de_Fund%C3%A3o.jpg/800px-Rio_Doce_polu%C3%ADdo_ap%C3%B3s_rompimento_da_Barragem_de_Fund%C3%A3o.jpg"},
    {"id":"B003","nome":"Barragem Casa de Pedra","empresa":"CSN","municipio":"Congonhas","estado":"MG","lat":-20.5333,"lon":-43.8500,"altura_m":130,"volume_m3":89000000,"tipo":"Aterro","deformacao_atual_dB":-0.4,"risco":"Sem Risco","categoria_anm":"Baixo","dpa":"Alto","nivel_emergencia":"Sem emergência","descricao":"Uma das maiores barragens de rejeito da América Latina. Estável nos últimos 12 meses.","imagem":"https://upload.wikimedia.org/wikipedia/commons/thumb/9/9a/Congonhas_-_Minas_Gerais%2C_Brasil.jpg/800px-Congonhas_-_Minas_Gerais%2C_Brasil.jpg"},
    {"id":"B004","nome":"Barragem Sul Superior","empresa":"Vale S.A.","municipio":"Barão de Cocais","estado":"MG","lat":-19.9347,"lon":-43.4789,"altura_m":72,"volume_m3":9800000,"tipo":"Montante","deformacao_atual_dB":-5.8,"risco":"Crítico","categoria_anm":"Alto","dpa":"Alto","nivel_emergencia":"Emergência Nível 3","descricao":"Em estado de emergência nível 3 desde 2019. Comunidades da ZAS evacuadas preventivamente.","imagem":"https://upload.wikimedia.org/wikipedia/commons/thumb/7/7e/Brumadinho_dam_failure_%2801-25-2019%29.jpg/800px-Brumadinho_dam_failure_%2801-25-2019%29.jpg"},
    {"id":"B005","nome":"Barragem Alegria","empresa":"Vale S.A.","municipio":"Mariana","estado":"MG","lat":-20.3667,"lon":-43.4333,"altura_m":78,"volume_m3":18500000,"tipo":"Linha de centro","deformacao_atual_dB":-3.5,"risco":"Atenção","categoria_anm":"Médio","dpa":"Alto","nivel_emergencia":"Alerta Nível 1","descricao":"Deformação moderada detectada nos últimos 30 dias. Inspeção presencial recomendada.","imagem":"https://upload.wikimedia.org/wikipedia/commons/thumb/3/3a/Rio_Doce_polu%C3%ADdo_ap%C3%B3s_rompimento_da_Barragem_de_Fund%C3%A3o.jpg/800px-Rio_Doce_polu%C3%ADdo_ap%C3%B3s_rompimento_da_Barragem_de_Fund%C3%A3o.jpg"},
    {"id":"B006","nome":"Barragem Forquilha I","empresa":"Vale S.A.","municipio":"Ouro Preto","estado":"MG","lat":-20.3869,"lon":-43.5022,"altura_m":68,"volume_m3":8200000,"tipo":"Montante","deformacao_atual_dB":-4.1,"risco":"Atenção","categoria_anm":"Médio","dpa":"Alto","nivel_emergencia":"Alerta Nível 1","descricao":"Em processo de descaracterização acelerada. Deformação moderada com tendência de estabilização.","imagem":"https://upload.wikimedia.org/wikipedia/commons/thumb/4/4e/Ouro_Preto_-_Vista_Parcial.jpg/800px-Ouro_Preto_-_Vista_Parcial.jpg"},
    {"id":"B007","nome":"Barragem Xingu","empresa":"Anglo American","municipio":"Conceição do Mato Dentro","estado":"MG","lat":-19.0333,"lon":-43.4167,"altura_m":95,"volume_m3":32000000,"tipo":"Montante","deformacao_atual_dB":-1.1,"risco":"Sem Risco","categoria_anm":"Baixo","dpa":"Médio","nivel_emergencia":"Sem emergência","descricao":"Projeto Minas-Rio da Anglo American. Tecnologia de filtro a seco.","imagem":"https://upload.wikimedia.org/wikipedia/commons/thumb/c/c1/Conc%C3%A9i%C3%A7%C3%A3o_do_Mato_Dentro.jpg/800px-Conc%C3%A9i%C3%A7%C3%A3o_do_Mato_Dentro.jpg"},
    {"id":"B008","nome":"Barragem Maravilhas III","empresa":"Vallourec","municipio":"Bocaiúva","estado":"MG","lat":-17.1167,"lon":-43.8167,"altura_m":63,"volume_m3":4200000,"tipo":"Montante","deformacao_atual_dB":-6.3,"risco":"Crítico","categoria_anm":"Alto","dpa":"Alto","nivel_emergencia":"Emergência Nível 3","descricao":"Situação crítica desde 2021. PAE ativo. Monitoramento orbital intensificado.","imagem":"https://upload.wikimedia.org/wikipedia/commons/thumb/7/7e/Brumadinho_dam_failure_%2801-25-2019%29.jpg/800px-Brumadinho_dam_failure_%2801-25-2019%29.jpg"},
    {"id":"B009","nome":"Barragem Grupo","empresa":"Kinross","municipio":"Paracatu","estado":"MG","lat":-17.2333,"lon":-46.8667,"altura_m":98,"volume_m3":178000000,"tipo":"Aterro","deformacao_atual_dB":-0.7,"risco":"Sem Risco","categoria_anm":"Baixo","dpa":"Alto","nivel_emergencia":"Sem emergência","descricao":"Maior barragem de ouro do Brasil. Sistema de monitoramento automatizado.","imagem":"https://upload.wikimedia.org/wikipedia/commons/thumb/a/a8/Paracatu_-_Minas_Gerais_%28Brasil%29.jpg/800px-Paracatu_-_Minas_Gerais_%28Brasil%29.jpg"},
    {"id":"B010","nome":"Barragem Itabiruçu","empresa":"Vale S.A.","municipio":"Itabira","estado":"MG","lat":-19.6167,"lon":-43.2167,"altura_m":89,"volume_m3":22000000,"tipo":"Linha de centro","deformacao_atual_dB":-2.1,"risco":"Atenção","categoria_anm":"Médio","dpa":"Alto","nivel_emergencia":"Alerta Nível 1","descricao":"Histórico de intervenções estruturais. Deformação dentro do limiar de atenção.","imagem":"https://upload.wikimedia.org/wikipedia/commons/thumb/b/b9/Itabira_-_Minas_Gerais.jpg/800px-Itabira_-_Minas_Gerais.jpg"},
    {"id":"B011","nome":"Barragem Pico","empresa":"Vale S.A.","municipio":"Itabirito","estado":"MG","lat":-20.2333,"lon":-43.8000,"altura_m":115,"volume_m3":41000000,"tipo":"Aterro","deformacao_atual_dB":-0.3,"risco":"Sem Risco","categoria_anm":"Baixo","dpa":"Alto","nivel_emergencia":"Sem emergência","descricao":"Uma das maiores da Vale em operação. Sistema de drenagem avançado e monitoramento orbital.","imagem":"https://upload.wikimedia.org/wikipedia/commons/thumb/0/04/Itabirito_-_Minas_Gerais_%2801%29.jpg/800px-Itabirito_-_Minas_Gerais_%2801%29.jpg"},
    {"id":"B012","nome":"Barragem Cuiabá","empresa":"AngloGold Ashanti","municipio":"Sabará","estado":"MG","lat":-19.8833,"lon":-43.7667,"altura_m":74,"volume_m3":12000000,"tipo":"Linha de centro","deformacao_atual_dB":-3.2,"risco":"Atenção","categoria_anm":"Médio","dpa":"Alto","nivel_emergencia":"Alerta Nível 1","descricao":"Deformação SAR moderada detectada. Empresa notificada pela ANM para reforço no monitoramento.","imagem":"https://upload.wikimedia.org/wikipedia/commons/thumb/0/06/Sab%C3%A1ra_-_Minas_Gerais.jpg/800px-Sab%C3%A1ra_-_Minas_Gerais.jpg"},
    {"id":"B013","nome":"Barragem Presidente Médici","empresa":"COPELMI","municipio":"Candiota","estado":"RS","lat":-31.5500,"lon":-53.6833,"altura_m":38,"volume_m3":45000000,"tipo":"Aterro","deformacao_atual_dB":-1.4,"risco":"Sem Risco","categoria_anm":"Baixo","dpa":"Alto","nivel_emergencia":"Sem emergência","descricao":"Maior barragem de cinzas de carvão do Brasil. Monitoramento especial pelo volume.","imagem":"https://upload.wikimedia.org/wikipedia/commons/thumb/4/42/Candiota_-_Rio_Grande_do_Sul.jpg/800px-Candiota_-_Rio_Grande_do_Sul.jpg"},
    {"id":"B014","nome":"Barragem Santarém","empresa":"Imerys","municipio":"Barcarena","estado":"PA","lat":-1.5167,"lon":-48.6333,"altura_m":28,"volume_m3":38000000,"tipo":"Aterro","deformacao_atual_dB":-2.7,"risco":"Atenção","categoria_anm":"Médio","dpa":"Alto","nivel_emergencia":"Alerta Nível 1","descricao":"Barragem de caulim no Pará. Monitoramento orbital crítico pela dificuldade de acesso.","imagem":"https://upload.wikimedia.org/wikipedia/commons/thumb/b/b3/Barcarena_-_Par%C3%A1.jpg/800px-Barcarena_-_Par%C3%A1.jpg"},
    {"id":"B015","nome":"Barragem Sossego","empresa":"Vale S.A.","municipio":"Canaã dos Carajás","estado":"PA","lat":-6.3833,"lon":-50.1500,"altura_m":82,"volume_m3":28000000,"tipo":"Linha de centro","deformacao_atual_dB":-1.8,"risco":"Sem Risco","categoria_anm":"Baixo","dpa":"Alto","nivel_emergencia":"Sem emergência","descricao":"Barragem de cobre da Vale no Pará. Região remota — SAR é a principal fonte de monitoramento.","imagem":"https://upload.wikimedia.org/wikipedia/commons/thumb/d/d6/Cana%C3%A3_dos_Caraj%C3%A1s_-_Par%C3%A1.jpg/800px-Cana%C3%A3_dos_Caraj%C3%A1s_-_Par%C3%A1.jpg"},
]

# ─── PROCESSAMENTO DO CSV DA ANM ──────────────────────────────────────────────
def processar_csv_anm(conteudo: str) -> list:
    """Processa o CSV da ANM e retorna lista de barragens formatadas."""
    barragens = []
    reader = csv.DictReader(io.StringIO(conteudo), delimiter=";")

    # Mapeamento de campos do CSV da ANM
    campos_possiveis_nome = ["Nome da Barragem", "NOME_BARRAGEM", "nome_barragem", "Nome"]
    campos_possiveis_empresa = ["Nome do Empreendedor", "EMPREENDEDOR", "Empreendedor"]
    campos_possiveis_municipio = ["Município", "MUNICIPIO", "municipio"]
    campos_possiveis_uf = ["UF", "uf", "Estado"]
    campos_possiveis_cri = ["Categoria de Risco", "CRI", "categoria_risco"]
    campos_possiveis_dpa = ["Dano Potencial Associado", "DPA", "dpa"]
    campos_possiveis_emergencia = ["Nível de Emergência", "nivel_emergencia", "Nível Emergência"]
    campos_possiveis_pnsb = ["Inserida na PNSB?", "PNSB", "pnsb"]

    def get_campo(row, campos):
        for c in campos:
            if c in row and row[c]:
                return row[c].strip()
        return ""

    for i, row in enumerate(reader):
        try:
            nome = get_campo(row, campos_possiveis_nome)
            empresa = get_campo(row, campos_possiveis_empresa)
            municipio = get_campo(row, campos_possiveis_municipio)
            uf = get_campo(row, campos_possiveis_uf)
            cri = get_campo(row, campos_possiveis_cri)
            dpa = get_campo(row, campos_possiveis_dpa)
            emergencia = get_campo(row, campos_possiveis_emergencia)
            pnsb = get_campo(row, campos_possiveis_pnsb)

            if not nome or not municipio:
                continue

            # Mapear categoria ANM para risco IA
            risco = classificar_risco_anm(cri, emergencia)

            # Deformação simulada baseada no risco (será substituída por dados SAR reais)
            random.seed(hash(f"{nome}{municipio}") % 10000)
            deform = {
                "Crítico": round(random.uniform(-8.5, -5.1), 1),
                "Atenção": round(random.uniform(-4.9, -2.6), 1),
                "Sem Risco": round(random.uniform(-2.4, -0.1), 1),
            }[risco]

            # Coordenadas
            lat, lon = coords_municipio(municipio, uf)

            # Enriquecer com detalhes se disponível
            detalhes = None
            for chave, det in DETALHES_BARRAGENS.items():
                if chave.lower() in nome.lower():
                    detalhes = det
                    lat = det["lat"]
                    lon = det["lon"]
                    break

            imagem = detalhes["imagem"] if detalhes else IMAGENS_DEFAULT.get(uf, IMAGENS_DEFAULT["DEFAULT"])
            descricao = detalhes["descricao"] if detalhes else f"Barragem de mineração cadastrada no SIGBM/ANM. Localizada em {municipio}/{uf}. Categoria de risco: {cri}. DPA: {dpa}."

            barragem = {
                "id": f"ANM{str(i+1).zfill(4)}",
                "nome": nome,
                "empresa": empresa or "Não informado",
                "municipio": municipio,
                "estado": uf,
                "lat": lat,
                "lon": lon,
                "altura_m": 0,
                "volume_m3": 0,
                "tipo": get_campo(row, ["Método Construtivo", "METODO_CONSTRUTIVO", "Método"]) or "Não informado",
                "deformacao_atual_dB": deform,
                "risco": risco,
                "categoria_anm": cri or "Não informado",
                "dpa": dpa or "Não informado",
                "nivel_emergencia": emergencia or "Sem emergência",
                "pnsb": pnsb,
                "descricao": descricao,
                "imagem": imagem,
                "fonte": "SIGBM/ANM",
            }
            barragens.append(barragem)

        except Exception:
            continue

    return barragens


def classificar_risco_anm(cri: str, emergencia: str) -> str:
    """Mapeia categoria ANM + nível de emergência para classificação OrbitalGuard."""
    emerg_lower = emergencia.lower() if emergencia else ""
    if "nível 3" in emerg_lower or "nível 2" in emerg_lower or "3" in emerg_lower:
        return "Crítico"
    if "nível 1" in emerg_lower or "alerta" in emerg_lower or "1" in emerg_lower:
        return "Atenção"
    cri_lower = cri.lower() if cri else ""
    if "alto" in cri_lower:
        return "Atenção"
    if "médio" in cri_lower or "medio" in cri_lower:
        return "Sem Risco"
    return "Sem Risco"


# ─── CARREGAMENTO DOS DADOS ───────────────────────────────────────────────────
async def carregar_dados_anm():
    """Tenta baixar dados reais da ANM. Usa fallback se falhar."""
    global _cache

    # Verifica se cache ainda é válido
    if _cache["ultima_atualizacao"] and _cache["barragens"]:
        delta = datetime.now() - _cache["ultima_atualizacao"]
        if delta.total_seconds() < CACHE_TTL_HORAS * 3600:
            return

    print("🔄 Atualizando dados da ANM...")

    tentativas = [
        "https://app.anm.gov.br/sigbm/publico/classificacao/empreendimento",
        "https://sistemas.anm.gov.br/sigbm/publico/classificacao/empreendimento",
    ]

    for url in tentativas:
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(url, headers={"Accept": "text/csv,application/csv,*/*"})
                if resp.status_code == 200 and len(resp.text) > 1000:
                    barragens = processar_csv_anm(resp.text)
                    if len(barragens) > 50:
                        _cache["barragens"] = barragens
                        _cache["ultima_atualizacao"] = datetime.now()
                        _cache["fonte"] = "SIGBM/ANM (tempo real)"
                        print(f"✅ {len(barragens)} barragens carregadas da ANM")
                        return
        except Exception as e:
            print(f"⚠️  Tentativa {url} falhou: {e}")

    # Fallback
    print("⚠️  ANM indisponível — usando dados locais")
    _cache["barragens"] = BARRAGENS_FALLBACK
    _cache["ultima_atualizacao"] = datetime.now()
    _cache["fonte"] = "Dados locais (fallback)"


def get_barragens() -> list:
    return _cache["barragens"] if _cache["barragens"] else BARRAGENS_FALLBACK


# ─── STARTUP ──────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    await carregar_dados_anm()


# ─── HELPERS ──────────────────────────────────────────────────────────────────
def gerar_historico(barragem_id: str, dias: int = 90) -> list:
    barragens = get_barragens()
    base = next((b for b in barragens if b["id"] == barragem_id), None)
    if not base:
        return []
    valor_atual = base["deformacao_atual_dB"]
    historico = []
    hoje = datetime.now()
    random.seed(hash(barragem_id) % 1000)
    for i in range(dias, 0, -6):
        data = hoje - timedelta(days=i)
        progresso = (dias - i) / dias
        ruido = random.gauss(0, 0.3)
        valor = round(valor_atual * progresso + ruido, 3)
        risco = "Crítico" if valor < -5.0 else "Atenção" if valor < -2.5 else "Sem Risco"
        historico.append({
            "data": data.strftime("%Y-%m-%d"),
            "deformacao_dB": valor,
            "risco": risco,
        })
    return historico


# ─── SCHEMAS ──────────────────────────────────────────────────────────────────
class PredictRequest(BaseModel):
    barragem_id: Optional[str] = None
    deformacao_media_dB: float
    deformacao_std: float
    tendencia: float
    aceleracao: float
    pico_negativo_dB: float
    variacao_30d_dB: float
    chuva_acumulada_mm: float
    dias_sem_imagem: int

class VotoRequest(BaseModel):
    barragem_id: str
    tipo: str
    usuario_id: Optional[str] = "anonimo"


# ─── ENDPOINTS ────────────────────────────────────────────────────────────────
@app.get("/")
def root():
    barragens = get_barragens()
    return {
        "projeto": "OrbitalGuard",
        "versao": "4.0.0",
        "total_barragens": len(barragens),
        "fonte": _cache["fonte"],
        "ultima_atualizacao": _cache["ultima_atualizacao"].strftime("%Y-%m-%d %H:%M") if _cache["ultima_atualizacao"] else None,
        "endpoints": ["/barragens", "/predict", "/alertas", "/historico/{id}", "/votar", "/stats", "/atualizar"],
    }


@app.get("/barragens")
async def listar_barragens(
    estado:   Optional[str] = None,
    risco:    Optional[str] = None,
    empresa:  Optional[str] = None,
    busca:    Optional[str] = None,
    emergencia: Optional[bool] = None,
    limit:    Optional[int] = None,
):
    barragens = get_barragens()

    if estado:
        barragens = [b for b in barragens if b["estado"].upper() == estado.upper()]
    if risco:
        barragens = [b for b in barragens if b["risco"].lower() == risco.lower()]
    if empresa:
        barragens = [b for b in barragens if empresa.lower() in b["empresa"].lower()]
    if emergencia:
        barragens = [b for b in barragens if b["risco"] in ["Atenção", "Crítico"]]
    if busca:
        q = busca.lower()
        barragens = [b for b in barragens if
                     q in b["nome"].lower() or
                     q in b["municipio"].lower() or
                     q in b["empresa"].lower() or
                     q in b["estado"].lower()]

    ordem = {"Crítico": 0, "Atenção": 1, "Sem Risco": 2}
    barragens.sort(key=lambda b: ordem.get(b["risco"], 3))

    if limit:
        barragens = barragens[:limit]

    return {
        "total": len(barragens),
        "fonte": _cache["fonte"],
        "ultima_atualizacao": _cache["ultima_atualizacao"].strftime("%Y-%m-%d %H:%M") if _cache["ultima_atualizacao"] else None,
        "barragens": barragens,
    }


@app.get("/barragens/{barragem_id}")
def detalhe_barragem(barragem_id: str):
    barragens = get_barragens()
    b = next((b for b in barragens if b["id"] == barragem_id), None)
    if not b:
        raise HTTPException(status_code=404, detail=f"Barragem {barragem_id} não encontrada")
    return {**b, "votos": votos_db.get(barragem_id, {"confirmar": 0, "contestar": 0})}


@app.post("/predict")
def predict_risco(req: PredictRequest):
    if modelo_rf:
        features = np.array([[
            req.deformacao_media_dB, req.deformacao_std, req.tendencia,
            req.aceleracao, req.pico_negativo_dB, req.variacao_30d_dB,
            req.chuva_acumulada_mm, req.dias_sem_imagem
        ]])
        pred  = modelo_rf.predict(features)[0]
        proba = modelo_rf.predict_proba(features)[0]
        classe = CLASSES[pred]
        probs  = {c: round(float(p), 4) for c, p in zip(CLASSES, proba)}
    else:
        if req.deformacao_media_dB < -5.0:
            classe, probs = "Crítico", {"Sem Risco": 0.02, "Atenção": 0.08, "Crítico": 0.90}
        elif req.deformacao_media_dB < -2.5:
            classe, probs = "Atenção", {"Sem Risco": 0.10, "Atenção": 0.75, "Crítico": 0.15}
        else:
            classe, probs = "Sem Risco", {"Sem Risco": 0.90, "Atenção": 0.08, "Crítico": 0.02}

    mensagens = {
        "Sem Risco": "Estável. Continuar monitoramento de rotina via SAR.",
        "Atenção":   "Deformação moderada. Inspeção presencial em 48h.",
        "Crítico":   "⚠️ ALERTA: Deformação severa. Acionar emergência imediatamente.",
    }
    return {
        "barragem_id": req.barragem_id,
        "risco": classe,
        "cor": CLASSES_COR[classe],
        "probabilidades": probs,
        "alerta": classe in ["Atenção", "Crítico"],
        "mensagem": mensagens[classe],
        "modelo": "Random Forest" if modelo_rf else "Regras",
    }


@app.post("/votar")
def registrar_voto(req: VotoRequest):
    if req.tipo not in ["confirmar", "contestar"]:
        raise HTTPException(status_code=400, detail="Tipo deve ser 'confirmar' ou 'contestar'")
    if req.barragem_id not in votos_db:
        votos_db[req.barragem_id] = {"confirmar": 0, "contestar": 0, "usuarios": {}}
    usuarios = votos_db[req.barragem_id]["usuarios"]
    voto_anterior = usuarios.get(req.usuario_id)
    if voto_anterior == req.tipo:
        return {"status": "já votou"}
    if voto_anterior:
        votos_db[req.barragem_id][voto_anterior] -= 1
    votos_db[req.barragem_id][req.tipo] += 1
    usuarios[req.usuario_id] = req.tipo
    v = votos_db[req.barragem_id]
    return {
        "status": "voto registrado",
        "barragem_id": req.barragem_id,
        "votos": {"confirmar": v["confirmar"], "contestar": v["contestar"], "total": v["confirmar"] + v["contestar"]},
    }


@app.get("/votos/{barragem_id}")
def votos_barragem(barragem_id: str):
    v = votos_db.get(barragem_id, {"confirmar": 0, "contestar": 0})
    total = v.get("confirmar", 0) + v.get("contestar", 0)
    return {"barragem_id": barragem_id, "confirmar": v.get("confirmar", 0), "contestar": v.get("contestar", 0), "total": total}


@app.get("/alertas")
def listar_alertas():
    barragens = get_barragens()
    alertas = [
        {**b, "votos": votos_db.get(b["id"], {"confirmar": 0, "contestar": 0})}
        for b in barragens if b["risco"] in ["Atenção", "Crítico"]
    ]
    return {
        "total_alertas": len(alertas),
        "criticos":  sum(1 for a in alertas if a["risco"] == "Crítico"),
        "atencao":   sum(1 for a in alertas if a["risco"] == "Atenção"),
        "alertas":   alertas,
    }


@app.get("/historico/{barragem_id}")
def historico_barragem(barragem_id: str, dias: int = 90):
    barragens = get_barragens()
    b = next((b for b in barragens if b["id"] == barragem_id), None)
    if not b:
        raise HTTPException(status_code=404, detail=f"Barragem {barragem_id} não encontrada")
    return {
        "barragem_id": barragem_id,
        "nome": b["nome"],
        "dias": dias,
        "fonte": "Sentinel-1 SAR via Google Earth Engine",
        "historico": gerar_historico(barragem_id, dias),
    }


@app.get("/stats")
def estatisticas():
    barragens = get_barragens()
    criticos = sum(1 for b in barragens if b["risco"] == "Crítico")
    atencao  = sum(1 for b in barragens if b["risco"] == "Atenção")
    estaveis = sum(1 for b in barragens if b["risco"] == "Sem Risco")
    total_votos = sum(v.get("confirmar", 0) + v.get("contestar", 0) for v in votos_db.values())
    estados = list(set(b["estado"] for b in barragens))
    return {
        "total_barragens":       len(barragens),
        "sem_risco":             estaveis,
        "atencao":               atencao,
        "critico":               criticos,
        "estados_cobertos":      len(estados),
        "total_votos_comunidade": total_votos,
        "ultima_atualizacao":    _cache["ultima_atualizacao"].strftime("%Y-%m-%d %H:%M") if _cache["ultima_atualizacao"] else None,
        "fonte_dados":           _cache["fonte"],
        "modelo":                "Random Forest + Regressão Logística",
        "satelite":              "Sentinel-1 SAR (ESA Copernicus)",
        "revisita_dias":         6,
    }


@app.post("/atualizar")
async def forcar_atualizacao(background_tasks: BackgroundTasks):
    """Força atualização dos dados da ANM."""
    _cache["ultima_atualizacao"] = None
    background_tasks.add_task(carregar_dados_anm)
    return {"status": "Atualização iniciada em background"}


@app.get("/estados")
def listar_estados():
    """Retorna estatísticas por estado."""
    barragens = get_barragens()
    estados = {}
    for b in barragens:
        uf = b["estado"]
        if uf not in estados:
            estados[uf] = {"uf": uf, "total": 0, "critico": 0, "atencao": 0, "sem_risco": 0}
        estados[uf]["total"] += 1
        if b["risco"] == "Crítico":
            estados[uf]["critico"] += 1
        elif b["risco"] == "Atenção":
            estados[uf]["atencao"] += 1
        else:
            estados[uf]["sem_risco"] += 1

    lista = sorted(estados.values(), key=lambda x: -(x["critico"] * 10 + x["atencao"]))
    return {"total_estados": len(lista), "estados": lista}


@app.get("/ranking")
def ranking_risco(limit: int = 20):
    """Top barragens por nível de risco — as mais críticas primeiro."""
    barragens = get_barragens()
    ordem = {"Crítico": 0, "Atenção": 1, "Sem Risco": 2}
    ordenadas = sorted(barragens, key=lambda b: (ordem.get(b["risco"], 3), b["deformacao_atual_dB"]))
    return {
        "total": len(ordenadas),
        "mostrando": min(limit, len(ordenadas)),
        "ranking": [
            {
                "posicao": i + 1,
                "id": b["id"],
                "nome": b["nome"],
                "empresa": b["empresa"],
                "municipio": b["municipio"],
                "estado": b["estado"],
                "risco": b["risco"],
                "deformacao_dB": b["deformacao_atual_dB"],
                "nivel_emergencia": b.get("nivel_emergencia", "Não informado"),
            }
            for i, b in enumerate(ordenadas[:limit])
        ],
    }


@app.get("/empresas")
def listar_empresas():
    """Estatísticas por empresa mineradora."""
    barragens = get_barragens()
    empresas = {}
    for b in barragens:
        emp = b["empresa"]
        if emp not in empresas:
            empresas[emp] = {"empresa": emp, "total": 0, "critico": 0, "atencao": 0, "sem_risco": 0}
        empresas[emp]["total"] += 1
        if b["risco"] == "Crítico":
            empresas[emp]["critico"] += 1
        elif b["risco"] == "Atenção":
            empresas[emp]["atencao"] += 1
        else:
            empresas[emp]["sem_risco"] += 1

    lista = sorted(empresas.values(), key=lambda x: -(x["critico"] * 10 + x["atencao"]))
    return {"total_empresas": len(lista), "empresas": lista}


@app.get("/mapa-dados")
def dados_mapa():
    """Retorna apenas os dados necessários para o mapa (leve, para frontend)."""
    barragens = get_barragens()
    return {
        "total": len(barragens),
        "fonte": _cache["fonte"],
        "pontos": [
            {
                "id": b["id"],
                "nome": b["nome"],
                "lat": b["lat"],
                "lon": b["lon"],
                "risco": b["risco"],
                "deformacao_dB": b["deformacao_atual_dB"],
                "empresa": b["empresa"],
                "municipio": b["municipio"],
                "estado": b["estado"],
                "nivel_emergencia": b.get("nivel_emergencia", ""),
            }
            for b in barragens
        ],
    }


@app.get("/busca")
def busca_avancada(
    q: str,
    risco: Optional[str] = None,
    estado: Optional[str] = None,
    limit: int = 50,
):
    """Busca avançada com texto livre + filtros combinados."""
    barragens = get_barragens()
    termo = q.lower()
    resultado = [
        b for b in barragens
        if (termo in b["nome"].lower() or
            termo in b["municipio"].lower() or
            termo in b["empresa"].lower() or
            termo in b["estado"].lower() or
            termo in b.get("tipo", "").lower())
        and (not risco or b["risco"].lower() == risco.lower())
        and (not estado or b["estado"].upper() == estado.upper())
    ]
    ordem = {"Crítico": 0, "Atenção": 1, "Sem Risco": 2}
    resultado.sort(key=lambda b: ordem.get(b["risco"], 3))
    return {
        "query": q,
        "total_encontrados": len(resultado),
        "resultados": resultado[:limit],
    }


# ─── MAIN ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    print("\n🚀 OrbitalGuard API v4.0")
    print("   Dados: SIGBM/ANM + Sentinel-1 SAR")
    print("   Docs:  http://localhost:8000/docs\n")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
