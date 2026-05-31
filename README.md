# 🛰️ OrbitalGuard
### Monitoramento Inteligente de Barragens via Radar Orbital SAR + IA

[![FIAP Global Solution 2026](https://img.shields.io/badge/FIAP-Global%20Solution%202026-red)](https://www.fiap.com.br)
[![Python 3.11](https://img.shields.io/badge/Python-3.11-blue)](https://python.org)
[![React 18](https://img.shields.io/badge/React-18-61dafb)](https://reactjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104-009688)](https://fastapi.tiangolo.com)
[![Sentinel-1 SAR](https://img.shields.io/badge/Sentinel--1-SAR-orange)](https://sentinel.esa.int)
[![Google Earth Engine](https://img.shields.io/badge/Google-Earth%20Engine-4285F4)](https://earthengine.google.com)

> Sistema que usa imagens de radar orbital do satélite **Sentinel-1 (ESA/Copernicus)** combinadas com modelos de **Machine Learning** para detectar micro-deformações no solo ao redor de barragens de mineração, emitindo alertas com até 72h de antecedência.

---

## 📋 Contexto

O Brasil possui **816 barragens de mineração** cadastradas no SIGBM/ANM. Os desastres de **Mariana (2015)** e **Brumadinho (2019)** — que juntos causaram mais de 270 mortes e liberaram bilhões de litros de rejeitos — demonstraram que inspeções manuais periódicas são insuficientes.

O OrbitalGuard automatiza esse monitoramento usando dados SAR gratuitos que revisitam qualquer ponto do Brasil a cada **6 dias**, com resolução de **10 metros**, funcionando inclusive sob nuvens — crítico para regiões tropicais.

---

## 🏗️ Arquitetura

```
┌─────────────────────────────────────────────────┐
│              ORBITALGUARD SYSTEM                 │
├──────────────┬──────────────┬───────────────────┤
│   SENTINEL-1 │  GOOGLE EE   │    ANM/SIGBM      │
│   SAR Data   │  Processing  │    Real Data       │
└──────┬───────┴──────┬───────┴────────┬──────────┘
       │              │                │
       ▼              ▼                ▼
┌─────────────────────────────────────────────────┐
│              FASTAPI BACKEND                     │
│   • Modelo IA (Random Forest + Logistic)         │
│   • Endpoints REST                               │
│   • Sistema de votação comunitária               │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│           REACT DASHBOARD                        │
│   • Mapa interativo (Leaflet)                    │
│   • Cards com foto + descrição                   │
│   • Busca + filtros por risco                    │
│   • Gráfico histórico SAR                        │
│   • Validação comunitária                        │
└─────────────────────────────────────────────────┘
```

---

## 📁 Estrutura do Repositório

```
orbitalguard/
├── backend/
│   └── backend.py          # FastAPI — API REST + modelo IA
├── dashboard/
│   ├── src/
│   │   ├── App.jsx         # Dashboard React principal
│   │   ├── index.css       # Estilos (tema espacial escuro)
│   │   └── index.js
│   ├── public/
│   │   └── index.html
│   └── package.json
├── pipeline/
│   ├── sentinel_pipeline.py  # Busca imagens Sentinel-1 (Copernicus)
│   └── gee_pipeline.py       # Processamento SAR via Google Earth Engine
├── ml/
│   └── OrbitalGuard_MLAM.ipynb  # Notebook ML (Google Colab)
├── docs/
│   └── architecture.png
├── .gitignore
└── README.md
```

---

## 🤖 Modelos de Machine Learning

O notebook está disponível no Google Colab:

[![Abrir no Colab](https://colab.research.google.com/assets/colab-badge.svg)](SEU_LINK_DO_COLAB_AQUI)

### Modelos implementados

| Modelo | Tipo | Acurácia | F1-Score |
|--------|------|----------|----------|
| Regressão Logística | Classificação | ~95% | ~0.95 |
| Random Forest | Classificação | 100% | 1.000 |
| Regressão Linear | Regressão | — | R²~0.98 |
| LSTM (PyTorch) | Classificação | 100% | 1.000 |

### Features utilizadas (dados SAR)

| Feature | Descrição |
|---------|-----------|
| `deformacao_media_dB` | Média de variação radar no período |
| `deformacao_std` | Desvio padrão (instabilidade) |
| `tendencia` | Coeficiente angular da série temporal |
| `aceleracao` | Taxa de mudança da deformação |
| `pico_negativo_dB` | Valor mínimo de dB observado |
| `variacao_30d_dB` | Variação nos últimos 30 dias |
| `chuva_acumulada_mm` | Chuva acumulada (proxy de saturação) |
| `dias_sem_imagem` | Gap na série temporal SAR |

### Classes de risco

- 🟢 **Sem Risco** — deformação < -2.5 dB, estrutura estável
- 🟡 **Atenção** — deformação entre -2.5 e -5.0 dB, inspeção recomendada
- 🔴 **Crítico** — deformação > -5.0 dB, ação imediata necessária

---

## 🚀 Como Rodar

### Pré-requisitos

- Python 3.11+
- Node.js 18+
- Conta no [Copernicus Data Space](https://dataspace.copernicus.eu)
- Conta no [Google Earth Engine](https://earthengine.google.com)

### 1. Backend (FastAPI)

```bash
cd backend
pip install fastapi uvicorn httpx pydantic joblib scikit-learn
python backend.py
```

API disponível em: `http://localhost:8000`
Docs interativos: `http://localhost:8000/docs`

### 2. Dashboard (React)

```bash
cd dashboard
npm install
npm start
```

Dashboard disponível em: `http://localhost:3000`

### 3. Pipeline SAR (Google Earth Engine)

```bash
cd pipeline
pip install earthengine-api geemap folium
python -c "import ee; ee.Authenticate(auth_mode='notebook')"
python gee_pipeline.py
```

### 4. Notebook ML (Google Colab)

Acessa o link do Colab acima e executa todas as células em ordem.

---

## 🛰️ Dados Utilizados

| Fonte | Dados | Acesso |
|-------|-------|--------|
| ESA Copernicus / Sentinel-1 | Imagens SAR (radar) | Gratuito |
| Google Earth Engine | Processamento em nuvem | Gratuito (conta acadêmica) |
| ANM / SIGBM | Cadastro de barragens | Dados abertos |

---

## 📊 Endpoints da API

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET | `/barragens` | Lista barragens (filtros: estado, risco, empresa) |
| GET | `/barragens/{id}` | Detalhe de uma barragem |
| POST | `/predict` | Classifica risco com IA |
| GET | `/alertas` | Barragens em Atenção ou Crítico |
| GET | `/historico/{id}` | Série histórica de deformação SAR |
| POST | `/votar` | Validação comunitária (confirmar/contestar) |
| GET | `/votos/{id}` | Votos de uma barragem |
| GET | `/stats` | Estatísticas gerais do sistema |

---

## 🎯 ODS Alinhados

- **ODS 11** — Cidades e comunidades sustentáveis
- **ODS 13** — Ação contra a mudança global do clima
- **ODS 9** — Indústria, inovação e infraestrutura

---

## 👥 Equipe

Desenvolvido para a **Global Solution FIAP 2026.1 — Space Connect**

| Nome | Curso | GitHub |
|------|-------|--------|
| Natalia Alcantara | Ciência da Computação / IA | @nataliaalcantara |
| Izabely dos Santos | Ciência da Computação / IA | @usuario |

---

## 📄 Licença

MIT License — livre para uso acadêmico e educacional.
