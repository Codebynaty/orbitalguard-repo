import React, { useState, useEffect, useMemo } from 'react';
import { MapContainer, TileLayer, CircleMarker, Tooltip, useMap } from 'react-leaflet';
import { AreaChart, Area, XAxis, YAxis, Tooltip as RTooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import 'leaflet/dist/leaflet.css';

const API = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const MOCK_BARRAGENS = [
  { id:'B001', nome:'Barragem B1 — Brumadinho', empresa:'Vale S.A.', municipio:'Brumadinho', estado:'MG', lat:-20.1192, lon:-44.1228, altura_m:86, volume_m3:11700000, tipo:'Montante', deformacao_atual_dB:-7.2, risco:'Crítico',
    descricao:'Colapsou em 25 de janeiro de 2019, causando 270 mortes e liberando 12 milhões de m³ de rejeitos. Tornou-se o maior desastre industrial do Brasil e símbolo da urgência no monitoramento de barragens com tecnologia orbital.',
    imagem:'https://upload.wikimedia.org/wikipedia/commons/thumb/2/2e/Brumadinho_dam_failure_aerial_photo_%282019%29.jpg/640px-Brumadinho_dam_failure_aerial_photo_%282019%29.jpg' },
  { id:'B002', nome:'Barragem Germano', empresa:'Samarco', municipio:'Mariana', estado:'MG', lat:-20.2833, lon:-43.6167, altura_m:110, volume_m3:55000000, tipo:'Montante', deformacao_atual_dB:-2.8, risco:'Atenção',
    descricao:'Rompeu em novembro de 2015, liberando 40 milhões de m³ no Rio Doce — o maior desastre ambiental do Brasil. O rio levou meses para se recuperar parcialmente e comunidades ribeirinhas foram afetadas por centenas de km.',
    imagem:'https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Rio_doce_pluma.jpg/640px-Rio_doce_pluma.jpg' },
  { id:'B003', nome:'Barragem Casa de Pedra', empresa:'CSN', municipio:'Congonhas', estado:'MG', lat:-20.5333, lon:-43.8500, altura_m:130, volume_m3:89000000, tipo:'Aterro', deformacao_atual_dB:-0.4, risco:'Sem Risco',
    descricao:'Uma das maiores barragens de rejeito da América Latina, operada pela CSN em Congonhas. Estrutura em aterro de 130 metros com monitoramento instrumentado. Atualmente estável dentro dos parâmetros normais de operação.',
    imagem:'https://upload.wikimedia.org/wikipedia/commons/thumb/c/c9/Mina_Casa_de_Pedra_-_Congonhas_MG.jpg/640px-Mina_Casa_de_Pedra_-_Congonhas_MG.jpg' },
  { id:'B004', nome:'Barragem Xingu', empresa:'Anglo American', municipio:'Conceição do Mato Dentro', estado:'MG', lat:-19.0333, lon:-43.4167, altura_m:95, volume_m3:32000000, tipo:'Montante', deformacao_atual_dB:-1.1, risco:'Sem Risco',
    descricao:'Parte do Projeto Minas-Rio da Anglo American, integrada ao maior mineroduto do mundo com 529 km. Utiliza tecnologia de filtro a seco, considerada mais segura que o alteamento a montante tradicional.',
    imagem:'https://upload.wikimedia.org/wikipedia/commons/thumb/8/8b/Mina_de_Alegria_%28Mariana%2C_MG%29.jpg/640px-Mina_de_Alegria_%28Mariana%2C_MG%29.jpg' },
  { id:'B005', nome:'Barragem Alegria', empresa:'Vale S.A.', municipio:'Mariana', estado:'MG', lat:-20.3667, lon:-43.4333, altura_m:78, volume_m3:18500000, tipo:'Linha de centro', deformacao_atual_dB:-3.5, risco:'Atenção',
    descricao:'Barragem da Vale próxima ao complexo de Germano. Dados SAR indicam deformação moderada nos últimos 30 dias, com tendência de queda na reflectância radar — sinal que requer atenção reforçada e inspeção presencial.',
    imagem:'https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Rio_doce_pluma.jpg/640px-Rio_doce_pluma.jpg' },
];

function gerarHistorico(barragem, dias=90) {
  const data=[]; const hoje=new Date(); const vf=barragem.deformacao_atual_dB;
  for(let i=dias;i>=0;i-=6){
    const d=new Date(hoje); d.setDate(d.getDate()-i);
    const p=(dias-i)/dias, r=(Math.random()-0.5)*0.5;
    data.push({data:d.toISOString().slice(0,10), deformacao_dB:parseFloat((vf*p+r).toFixed(2))});
  }
  return data;
}

const RISK_COLOR = {'Sem Risco':'green','Atenção':'yellow','Crítico':'red'};
const RISK_HEX   = {'Sem Risco':'#48bb78','Atenção':'#ecc94b','Crítico':'#fc8181'};
const RISK_ORDER = {'Crítico':0,'Atenção':1,'Sem Risco':2};
const fmt = n => n>=1e6?(n/1e6).toFixed(1)+'M m³':n>=1e3?(n/1e3).toFixed(0)+'K m³':n+' m³';

function FlyTo({center}){
  const map=useMap();
  useEffect(()=>{if(center)map.flyTo(center,12,{duration:1.2});},[center,map]);
  return null;
}

function CustomTooltip({active,payload,label}){
  if(!active||!payload?.length)return null;
  const v=payload[0].value;
  return(
    <div style={{background:'#0a0f1e',border:'1px solid rgba(99,179,237,0.2)',borderRadius:6,padding:'8px 12px'}}>
      <div style={{fontFamily:'Space Mono,monospace',fontSize:10,color:'#94a3b8'}}>{label}</div>
      <div style={{fontFamily:'Space Mono,monospace',fontSize:13,fontWeight:700,color:v<-5?'#fc8181':v<-2.5?'#ecc94b':'#48bb78'}}>{v} dB</div>
    </div>
  );
}

// ── POPUP LATERAL ────────────────────────────────────────────────────────────
function MapPopup({ barragem, historico, votos, onVotar, onClose, imgError, setImgError }) {
  if (!barragem) return null;
  const cor = RISK_HEX[barragem.risco];
  const v = votos[barragem.id] || { confirmar: 0, contestar: 0 };
  const total = v.confirmar + v.contestar;
  const pctConfirmar = total > 0 ? Math.round((v.confirmar / total) * 100) : 0;
  const pctContestar = total > 0 ? Math.round((v.contestar / total) * 100) : 0;
  const meuVoto = v.meuVoto;

  return (
    <div style={{
      position:'absolute', top:12, right:12, zIndex:500,
      width:300, background:'#0a0f1e',
      border:`1px solid ${cor}40`,
      borderRadius:12, overflow:'hidden',
      boxShadow:`0 8px 32px rgba(0,0,0,0.6), 0 0 24px ${cor}20`,
      animation:'slideIn 0.25s ease',
    }}>
      <style>{`@keyframes slideIn{from{opacity:0;transform:translateX(16px)}to{opacity:1;transform:translateX(0)}}`}</style>

      {/* FOTO */}
      <div style={{height:140,position:'relative',background:'#050810',overflow:'hidden'}}>
        {!imgError[barragem.id] ? (
          <img src={barragem.imagem} alt={barragem.nome}
            onError={()=>setImgError(p=>({...p,[barragem.id]:true}))}
            style={{width:'100%',height:'100%',objectFit:'cover',filter:'brightness(0.7) saturate(0.7)'}}/>
        ):(
          <div style={{width:'100%',height:'100%',display:'flex',alignItems:'center',justifyContent:'center',flexDirection:'column',gap:8,background:'linear-gradient(135deg,#0a0f1e,#151d35)'}}>
            <div style={{fontSize:36}}>🛰️</div>
            <div style={{fontFamily:'Space Mono,monospace',fontSize:10,color:'#4a5568'}}>Imagem SAR</div>
          </div>
        )}
        {/* badges */}
        <div style={{position:'absolute',top:8,left:8,background:'rgba(0,0,0,0.7)',border:`1px solid ${cor}`,borderRadius:5,padding:'3px 8px',fontFamily:'Space Mono,monospace',fontSize:10,fontWeight:700,color:cor,backdropFilter:'blur(4px)'}}>
          {barragem.risco==='Crítico'?'⚠️ ':barragem.risco==='Atenção'?'⚡ ':'✅ '}{barragem.risco}
        </div>
        <button onClick={onClose} style={{position:'absolute',top:8,right:8,background:'rgba(0,0,0,0.6)',border:'1px solid rgba(255,255,255,0.2)',borderRadius:4,color:'#94a3b8',width:24,height:24,cursor:'pointer',fontSize:12,display:'flex',alignItems:'center',justifyContent:'center',backdropFilter:'blur(4px)'}}>✕</button>
        <div style={{position:'absolute',bottom:0,left:0,right:0,background:'linear-gradient(transparent,rgba(0,0,0,0.8))',padding:'16px 12px 8px'}}>
          <div style={{fontSize:13,fontWeight:600,color:'#e2e8f0',lineHeight:1.3}}>{barragem.nome}</div>
          <div style={{fontFamily:'Space Mono,monospace',fontSize:10,color:'#94a3b8'}}>{barragem.empresa} · {barragem.municipio}/{barragem.estado}</div>
        </div>
      </div>

      <div style={{padding:12}}>
        {/* DESCRIÇÃO */}
        <div style={{fontSize:11,color:'#94a3b8',lineHeight:1.6,marginBottom:12,borderLeft:`2px solid ${cor}`,paddingLeft:8}}>
          {barragem.descricao}
        </div>

        {/* MÉTRICAS */}
        <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:6,marginBottom:12}}>
          {[['Altura',barragem.altura_m+'m'],['Volume',fmt(barragem.volume_m3)],['SAR',barragem.deformacao_atual_dB+' dB']].map(([k,v])=>(
            <div key={k} style={{background:'#050810',borderRadius:6,padding:'6px 8px',textAlign:'center'}}>
              <div style={{fontFamily:'Space Mono,monospace',fontSize:12,fontWeight:700,color:k==='SAR'?cor:'#e2e8f0'}}>{v}</div>
              <div style={{fontSize:9,color:'#4a5568',textTransform:'uppercase',letterSpacing:'0.06em',marginTop:1}}>{k}</div>
            </div>
          ))}
        </div>

        {/* GRÁFICO */}
        {historico.length>0&&(
          <div style={{marginBottom:12}}>
            <div style={{fontFamily:'Space Mono,monospace',fontSize:9,color:'#4a5568',textTransform:'uppercase',letterSpacing:'0.08em',marginBottom:4}}>Deformação SAR — 90 dias</div>
            <ResponsiveContainer width="100%" height={70}>
              <AreaChart data={historico} margin={{top:4,right:4,bottom:0,left:-28}}>
                <defs>
                  <linearGradient id="grad2" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={cor} stopOpacity={0.3}/>
                    <stop offset="95%" stopColor={cor} stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <XAxis dataKey="data" hide/>
                <YAxis tick={{fontSize:8,fill:'#4a5568',fontFamily:'Space Mono'}}/>
                <RTooltip content={<CustomTooltip/>}/>
                <ReferenceLine y={-2.5} stroke="#ecc94b" strokeDasharray="3 3" strokeWidth={1}/>
                <ReferenceLine y={-5.0} stroke="#fc8181" strokeDasharray="3 3" strokeWidth={1}/>
                <Area type="monotone" dataKey="deformacao_dB" stroke={cor} strokeWidth={2} fill="url(#grad2)" dot={false}/>
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* SISTEMA DE VOTAÇÃO */}
        <div style={{background:'#050810',borderRadius:8,padding:10,border:'1px solid rgba(99,179,237,0.1)'}}>
          <div style={{fontFamily:'Space Mono,monospace',fontSize:9,color:'#63b3ed',textTransform:'uppercase',letterSpacing:'0.08em',marginBottom:8}}>
            👥 Validação Comunitária
          </div>

          {/* BOTÕES DE VOTO */}
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:6,marginBottom:8}}>
            <button onClick={()=>onVotar(barragem.id,'confirmar')} style={{
              padding:'7px 0', borderRadius:6, cursor:'pointer', fontSize:11,
              fontFamily:'Space Mono,monospace', fontWeight:700, transition:'all 0.15s',
              background: meuVoto==='confirmar'?'rgba(252,129,129,0.2)':'transparent',
              border: `1px solid ${meuVoto==='confirmar'?'#fc8181':'rgba(252,129,129,0.3)'}`,
              color: meuVoto==='confirmar'?'#fc8181':'#94a3b8',
            }}>⚠️ Confirmar</button>
            <button onClick={()=>onVotar(barragem.id,'contestar')} style={{
              padding:'7px 0', borderRadius:6, cursor:'pointer', fontSize:11,
              fontFamily:'Space Mono,monospace', fontWeight:700, transition:'all 0.15s',
              background: meuVoto==='contestar'?'rgba(72,187,120,0.2)':'transparent',
              border: `1px solid ${meuVoto==='contestar'?'#48bb78':'rgba(72,187,120,0.3)'}`,
              color: meuVoto==='contestar'?'#48bb78':'#94a3b8',
            }}>✅ Contestar</button>
          </div>

          {/* BARRA DE VOTOS */}
          {total > 0 ? (
            <div>
              <div style={{display:'flex',justifyContent:'space-between',marginBottom:4}}>
                <span style={{fontFamily:'Space Mono,monospace',fontSize:9,color:'#fc8181'}}>⚠️ {v.confirmar} ({pctConfirmar}%)</span>
                <span style={{fontFamily:'Space Mono,monospace',fontSize:9,color:'#48bb78'}}>✅ {v.contestar} ({pctContestar}%)</span>
              </div>
              <div style={{height:6,borderRadius:3,background:'#151d35',overflow:'hidden'}}>
                <div style={{height:'100%',width:`${pctConfirmar}%`,background:'linear-gradient(90deg,#fc8181,#f56565)',borderRadius:3,transition:'width 0.4s ease'}}/>
              </div>
              <div style={{fontFamily:'Space Mono,monospace',fontSize:9,color:'#4a5568',marginTop:4,textAlign:'center'}}>{total} voto{total!==1?'s':''} registrado{total!==1?'s':''}</div>
            </div>
          ):(
            <div style={{fontFamily:'Space Mono,monospace',fontSize:9,color:'#4a5568',textAlign:'center'}}>Seja o primeiro a validar este alerta</div>
          )}

          {meuVoto && (
            <div style={{marginTop:6,fontFamily:'Space Mono,monospace',fontSize:9,color:'#63b3ed',textAlign:'center'}}>
              Seu voto: {meuVoto==='confirmar'?'⚠️ Risco confirmado':'✅ Falso positivo contestado'}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── APP PRINCIPAL ─────────────────────────────────────────────────────────────
export default function App() {
  const [barragens, setBarragens] = useState(MOCK_BARRAGENS);
  const [selected,  setSelected]  = useState(null);
  const [historico, setHistorico] = useState([]);
  const [apiOk,     setApiOk]     = useState(false);
  const [busca,     setBusca]     = useState('');
  const [filtroRisco, setFiltroRisco] = useState('Todos');
  const [view,      setView]      = useState('mapa');
  const [imgError,  setImgError]  = useState({});
  const [votos,     setVotos]     = useState({});

  useEffect(()=>{
    fetch(`${API}/barragens`).then(r=>r.json())
      .then(d=>{setBarragens(d.barragens.map((b,i)=>({...MOCK_BARRAGENS[i],...b})));setApiOk(true);})
      .catch(()=>setApiOk(false));
  },[]);

  useEffect(()=>{
    if(!selected)return;
    fetch(`${API}/historico/${selected.id}`).then(r=>r.json())
      .then(d=>setHistorico(d.historico))
      .catch(()=>setHistorico(gerarHistorico(selected)));
  },[selected]);

  const handleVotar = (id, tipo) => {
    setVotos(prev => {
      const atual = prev[id] || { confirmar:0, contestar:0, meuVoto:null };
      if (atual.meuVoto === tipo) return prev; // já votou
      const novo = { ...atual };
      if (atual.meuVoto) novo[atual.meuVoto]--; // desfaz voto anterior
      novo[tipo]++;
      novo.meuVoto = tipo;
      return { ...prev, [id]: novo };
    });
  };

  const filtradas = useMemo(()=>
    barragens
      .filter(b=>{ const q=busca.toLowerCase(); return b.nome.toLowerCase().includes(q)||b.municipio.toLowerCase().includes(q)||b.empresa.toLowerCase().includes(q)||b.estado.toLowerCase().includes(q); })
      .filter(b=>filtroRisco==='Todos'||b.risco===filtroRisco)
      .sort((a,b)=>RISK_ORDER[a.risco]-RISK_ORDER[b.risco]),
  [barragens,busca,filtroRisco]);

  const criticos = barragens.filter(b=>b.risco==='Crítico').length;
  const atencao  = barragens.filter(b=>b.risco==='Atenção').length;
  const estavel  = barragens.filter(b=>b.risco==='Sem Risco').length;

  return (
    <div className="app">
      {/* HEADER */}
      <header className="header">
        <div className="header-logo">
          <div className="logo-icon">🛰️</div>
          <div>
            <div className="logo-text">ORBITALGUARD</div>
            <div className="logo-sub">Sentinel-1 SAR · IA · Validação Comunitária</div>
          </div>
        </div>
        <div style={{display:'flex',gap:16,alignItems:'center'}}>
          {!apiOk&&<div style={{fontFamily:'Space Mono,monospace',fontSize:10,color:'#ecc94b',background:'rgba(236,201,75,0.1)',padding:'4px 10px',borderRadius:4,border:'1px solid rgba(236,201,75,0.3)'}}>MODO DEMO</div>}
          <div style={{display:'flex',background:'#0a0f1e',border:'1px solid rgba(99,179,237,0.15)',borderRadius:6,overflow:'hidden'}}>
            {['mapa','card'].map(v=>(
              <button key={v} onClick={()=>setView(v)} style={{padding:'5px 14px',fontSize:11,fontFamily:'Space Mono,monospace',background:view===v?'rgba(99,179,237,0.15)':'transparent',color:view===v?'#63b3ed':'#94a3b8',border:'none',cursor:'pointer',textTransform:'uppercase',letterSpacing:'0.05em'}}>
                {v==='mapa'?'🗺 Mapa':'📋 Cards'}
              </button>
            ))}
          </div>
          <div className="header-status"><div className="pulse"/>SISTEMA ATIVO · {new Date().toLocaleString('pt-BR')}</div>
        </div>
      </header>

      <main className="main">
        {/* SIDEBAR */}
        <aside className="sidebar">
          <div className="stats-bar">
            {[['Crítico',criticos,'#fc8181'],['Atenção',atencao,'#ecc94b'],['Estável',estavel,'#48bb78']].map(([label,val,cor])=>(
              <div key={label} className="stat-item" onClick={()=>setFiltroRisco(filtroRisco===(label==='Estável'?'Sem Risco':label)?'Todos':(label==='Estável'?'Sem Risco':label))} style={{cursor:'pointer'}}>
                <div className="stat-value" style={{color:cor}}>{val}</div>
                <div className="stat-label">{label}</div>
              </div>
            ))}
          </div>

          {/* BUSCA */}
          <div style={{padding:'10px 12px',borderBottom:'1px solid rgba(99,179,237,0.12)',display:'flex',flexDirection:'column',gap:8}}>
            <input value={busca} onChange={e=>setBusca(e.target.value)} placeholder="🔍  Buscar barragem, município..."
              style={{background:'#0a0f1e',border:'1px solid rgba(99,179,237,0.2)',borderRadius:6,padding:'8px 10px',color:'#e2e8f0',fontFamily:'DM Sans,sans-serif',fontSize:13,width:'100%',outline:'none'}}/>
            <div style={{display:'flex',gap:6}}>
              {['Todos','Crítico','Atenção','Sem Risco'].map(r=>(
                <button key={r} onClick={()=>setFiltroRisco(r)} style={{flex:1,padding:'4px 0',fontSize:10,fontFamily:'Space Mono,monospace',background:filtroRisco===r?'rgba(99,179,237,0.15)':'transparent',color:filtroRisco===r?'#63b3ed':r==='Crítico'?'#fc8181':r==='Atenção'?'#ecc94b':r==='Sem Risco'?'#48bb78':'#94a3b8',border:`1px solid ${filtroRisco===r?'rgba(99,179,237,0.4)':'rgba(99,179,237,0.1)'}`,borderRadius:4,cursor:'pointer',whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis'}}>
                  {r==='Sem Risco'?'Estável':r}
                </button>
              ))}
            </div>
            <div style={{fontFamily:'Space Mono,monospace',fontSize:10,color:'#4a5568'}}>{filtradas.length} de {barragens.length} barragens</div>
          </div>

          {/* LIST */}
          <div className="barragem-list">
            {filtradas.length===0?(
              <div style={{padding:24,textAlign:'center',color:'#4a5568',fontFamily:'Space Mono,monospace',fontSize:12}}>Nenhuma barragem encontrada</div>
            ):filtradas.map(b=>(
              <div key={b.id} className={`barragem-item ${selected?.id===b.id?'active':''}`} onClick={()=>{setSelected(b);setView('mapa');}}>
                <div className={`risk-dot ${RISK_COLOR[b.risco]}`}/>
                <div className="barragem-info">
                  <div className="barragem-name">{b.nome}</div>
                  <div className="barragem-meta">{b.municipio}/{b.estado} · {b.deformacao_atual_dB} dB</div>
                </div>
                <div className={`risk-badge ${RISK_COLOR[b.risco]}`}>{b.risco}</div>
              </div>
            ))}
          </div>

          {/* MINI CHART */}
          {selected&&historico.length>0&&(
            <div className="detail-panel">
              <div className="detail-title">📍 {selected.id} — Histórico SAR</div>
              <ResponsiveContainer width="100%" height={80}>
                <AreaChart data={historico} margin={{top:4,right:4,bottom:0,left:-20}}>
                  <defs>
                    <linearGradient id="grad1" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={RISK_HEX[selected.risco]} stopOpacity={0.3}/>
                      <stop offset="95%" stopColor={RISK_HEX[selected.risco]} stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="data" hide/>
                  <YAxis tick={{fontSize:9,fill:'#4a5568',fontFamily:'Space Mono'}}/>
                  <RTooltip content={<CustomTooltip/>}/>
                  <ReferenceLine y={-2.5} stroke="#ecc94b" strokeDasharray="3 3" strokeWidth={1}/>
                  <ReferenceLine y={-5.0} stroke="#fc8181" strokeDasharray="3 3" strokeWidth={1}/>
                  <Area type="monotone" dataKey="deformacao_dB" stroke={RISK_HEX[selected.risco]} strokeWidth={2} fill="url(#grad1)" dot={false}/>
                </AreaChart>
              </ResponsiveContainer>
              <div style={{display:'flex',gap:12,marginTop:4}}>
                <span style={{fontSize:9,color:'#ecc94b',fontFamily:'Space Mono'}}>— atenção (-2.5 dB)</span>
                <span style={{fontSize:9,color:'#fc8181',fontFamily:'Space Mono'}}>— crítico (-5.0 dB)</span>
              </div>
            </div>
          )}
        </aside>

        {/* CONTENT */}
        <div style={{flex:1,position:'relative',overflow:view==='card'?'auto':'hidden'}}>

          {/* MAP VIEW */}
          {view==='mapa'&&(
            <>
              <MapContainer center={[-20.2,-43.9]} zoom={8} style={{height:'100%',width:'100%'}}>
                <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="© OpenStreetMap"/>
                <FlyTo center={selected?[selected.lat,selected.lon]:null}/>
                {barragens.map(b=>(
                  <CircleMarker key={b.id} center={[b.lat,b.lon]}
                    radius={b.risco==='Crítico'?14:b.risco==='Atenção'?10:8}
                    pathOptions={{color:RISK_HEX[b.risco],fillColor:RISK_HEX[b.risco],fillOpacity:b.risco==='Crítico'?0.8:0.5,weight:b.id===selected?.id?3:1.5}}
                    eventHandlers={{click:()=>setSelected(b)}}>
                    <Tooltip permanent={b.risco==='Crítico'} direction="top" offset={[0,-10]}>
                      <div style={{fontFamily:'Space Mono,monospace',fontSize:11}}>
                        <strong>{b.id}</strong> — {b.risco}<br/>{b.deformacao_atual_dB} dB
                      </div>
                    </Tooltip>
                  </CircleMarker>
                ))}
              </MapContainer>

              {/* POPUP LATERAL */}
              <MapPopup
                barragem={selected}
                historico={historico}
                votos={votos}
                onVotar={handleVotar}
                onClose={()=>setSelected(null)}
                imgError={imgError}
                setImgError={setImgError}
              />

              {/* ALERTA BANNER */}
              {criticos>0&&!selected&&(
                <div className="alert-banner">
                  <div className="alert-banner-title">⚠️ ALERTA CRÍTICO ATIVO</div>
                  {barragens.filter(b=>b.risco==='Crítico').map(b=>(
                    <div key={b.id} style={{marginTop:4,cursor:'pointer'}} onClick={()=>setSelected(b)}>{b.nome}<br/>{b.deformacao_atual_dB} dB</div>
                  ))}
                </div>
              )}
            </>
          )}

          {/* CARDS VIEW */}
          {view==='card'&&(
            <div style={{padding:24,display:'grid',gridTemplateColumns:'repeat(auto-fill,minmax(340px,1fr))',gap:20}}>
              {filtradas.map(b=>{
                const cor=RISK_HEX[b.risco];
                const v=votos[b.id]||{confirmar:0,contestar:0,meuVoto:null};
                const total=v.confirmar+v.contestar;
                const pctC=total>0?Math.round((v.confirmar/total)*100):0;
                return(
                  <div key={b.id} style={{background:'#0a0f1e',border:`1px solid ${b.id===selected?.id?cor:'rgba(99,179,237,0.12)'}`,borderRadius:12,overflow:'hidden',boxShadow:b.risco==='Crítico'?`0 0 20px rgba(252,129,129,0.15)`:'none',transition:'transform 0.15s'}}
                    onMouseEnter={e=>e.currentTarget.style.transform='translateY(-2px)'}
                    onMouseLeave={e=>e.currentTarget.style.transform='none'}>

                    {/* FOTO */}
                    <div style={{height:160,position:'relative',background:'#050810',overflow:'hidden'}}>
                      {!imgError[b.id]?(
                        <img src={b.imagem} alt={b.nome} onError={()=>setImgError(p=>({...p,[b.id]:true}))}
                          style={{width:'100%',height:'100%',objectFit:'cover',filter:'brightness(0.7) saturate(0.7)'}}/>
                      ):(
                        <div style={{width:'100%',height:'100%',display:'flex',alignItems:'center',justifyContent:'center',flexDirection:'column',gap:8,background:'linear-gradient(135deg,#0a0f1e,#151d35)'}}>
                          <div style={{fontSize:32}}>🛰️</div>
                          <div style={{fontFamily:'Space Mono,monospace',fontSize:10,color:'#4a5568'}}>Imagem SAR</div>
                        </div>
                      )}
                      <div style={{position:'absolute',top:8,left:8,background:'rgba(0,0,0,0.7)',border:`1px solid ${cor}`,borderRadius:5,padding:'3px 8px',fontFamily:'Space Mono,monospace',fontSize:10,fontWeight:700,color:cor,backdropFilter:'blur(4px)'}}>
                        {b.risco==='Crítico'?'⚠️ ':b.risco==='Atenção'?'⚡ ':'✅ '}{b.risco}
                      </div>
                      <div style={{position:'absolute',bottom:0,left:0,right:0,background:'linear-gradient(transparent,rgba(0,0,0,0.8))',padding:'16px 12px 8px'}}>
                        <div style={{fontSize:13,fontWeight:600,color:'#e2e8f0',lineHeight:1.3}}>{b.nome}</div>
                        <div style={{fontFamily:'Space Mono,monospace',fontSize:10,color:'#94a3b8'}}>{b.empresa} · {b.municipio}/{b.estado}</div>
                      </div>
                    </div>

                    <div style={{padding:14}}>
                      <div style={{fontSize:12,color:'#94a3b8',lineHeight:1.6,marginBottom:12,borderLeft:`2px solid ${cor}`,paddingLeft:8}}>{b.descricao}</div>

                      {/* MÉTRICAS */}
                      <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:6,marginBottom:12}}>
                        {[['Altura',b.altura_m+'m'],['Volume',fmt(b.volume_m3)],['SAR',b.deformacao_atual_dB+' dB']].map(([k,val])=>(
                          <div key={k} style={{background:'#050810',borderRadius:6,padding:'6px 8px',textAlign:'center'}}>
                            <div style={{fontFamily:'Space Mono,monospace',fontSize:12,fontWeight:700,color:k==='SAR'?cor:'#e2e8f0'}}>{val}</div>
                            <div style={{fontSize:9,color:'#4a5568',textTransform:'uppercase',letterSpacing:'0.06em',marginTop:1}}>{k}</div>
                          </div>
                        ))}
                      </div>

                      {/* VOTAÇÃO NO CARD */}
                      <div style={{background:'#050810',borderRadius:8,padding:10,border:'1px solid rgba(99,179,237,0.1)',marginBottom:10}}>
                        <div style={{fontFamily:'Space Mono,monospace',fontSize:9,color:'#63b3ed',textTransform:'uppercase',letterSpacing:'0.08em',marginBottom:8}}>👥 Validação Comunitária</div>
                        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:6,marginBottom:total>0?8:0}}>
                          {[['confirmar','⚠️ Confirmar','#fc8181'],['contestar','✅ Contestar','#48bb78']].map(([tipo,label,c])=>(
                            <button key={tipo} onClick={()=>handleVotar(b.id,tipo)} style={{padding:'6px 0',borderRadius:6,cursor:'pointer',fontSize:10,fontFamily:'Space Mono,monospace',fontWeight:700,transition:'all 0.15s',background:v.meuVoto===tipo?`rgba(${tipo==='confirmar'?'252,129,129':'72,187,120'},0.2)`:'transparent',border:`1px solid ${v.meuVoto===tipo?c:c+'50'}`,color:v.meuVoto===tipo?c:'#94a3b8'}}>{label}</button>
                          ))}
                        </div>
                        {total>0&&(
                          <>
                            <div style={{display:'flex',justifyContent:'space-between',marginBottom:3}}>
                              <span style={{fontFamily:'Space Mono,monospace',fontSize:9,color:'#fc8181'}}>⚠️ {v.confirmar} ({pctC}%)</span>
                              <span style={{fontFamily:'Space Mono,monospace',fontSize:9,color:'#48bb78'}}>✅ {v.contestar} ({100-pctC}%)</span>
                            </div>
                            <div style={{height:5,borderRadius:3,background:'#151d35',overflow:'hidden'}}>
                              <div style={{height:'100%',width:`${pctC}%`,background:'linear-gradient(90deg,#fc8181,#f56565)',borderRadius:3,transition:'width 0.4s ease'}}/>
                            </div>
                            <div style={{fontFamily:'Space Mono,monospace',fontSize:9,color:'#4a5568',marginTop:3,textAlign:'center'}}>{total} voto{total!==1?'s':''}</div>
                          </>
                        )}
                      </div>

                      <button onClick={()=>{setSelected(b);setView('mapa');}} style={{width:'100%',padding:'8px 0',background:'rgba(99,179,237,0.08)',border:'1px solid rgba(99,179,237,0.2)',borderRadius:6,color:'#63b3ed',fontFamily:'Space Mono,monospace',fontSize:11,cursor:'pointer',letterSpacing:'0.05em'}}>
                        VER NO MAPA →
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
