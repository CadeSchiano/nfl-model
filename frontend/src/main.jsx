import { createRoot } from 'react-dom/client'
import { useEffect, useState } from 'react'
import { api } from './services/api'
import './styles.css'

const nav = [['/', 'Dashboard'], ['/predictions', 'Predictions'], ['/performance', 'Performance'], ['/history', 'History'], ['/methodology', 'Methodology']]
const pct = value => value == null ? '—' : `${(value * 100).toFixed(1)}%`
const margin = value => value == null ? '—' : `${value > 0 ? '+' : ''}${Number(value).toFixed(1)}`

function useData(path) {
  const [state, setState] = useState({ loading: true, data: null, error: null })
  useEffect(() => { let active = true; api(path).then(data => active && setState({ loading: false, data, error: null })).catch(error => active && setState({ loading: false, data: null, error })); return () => { active = false } }, [path])
  return state
}

function Empty({ children }) { return <div className="empty">{children}</div> }
function Loading() { return <Empty>Loading model data…</Empty> }

function PredictionTable({ predictions, games = [] }) {
  if (!predictions.length) return <Empty>No published predictions yet.</Empty>
  const gameById = Object.fromEntries(games.map(game => [game.id, game]))
  return <div className="table-wrap"><table><thead><tr><th>Matchup</th><th>Model win %</th><th>Market win %</th><th>Difference</th><th>Model spread</th><th>Market spread</th><th>Spread difference</th></tr></thead><tbody>{predictions.map(prediction => { const game = gameById[prediction.game_id]; return <tr key={prediction.id}><td>{game ? <a href={`/games/${game.id}`}>{game.away_team} @ {game.home_team}</a> : prediction.game_id}</td><td>{pct(prediction.home_win_probability)}</td><td>{pct(prediction.market_home_probability)}</td><td className="accent">{pct(prediction.moneyline_difference)}</td><td>{margin(prediction.predicted_margin)}</td><td>{prediction.market_spread ?? '—'}</td><td className="accent">{margin(prediction.spread_difference)}</td></tr> })}</tbody></table></div>
}

function Dashboard() { const games = useData('/games/current-week'); const predictions = useData('/predictions/current-week'); if (games.loading || predictions.loading) return <Loading />; if (games.error || predictions.error) return <Empty>Backend unavailable. Start FastAPI on port 8000.</Empty>; return <><section className="hero"><p className="eyebrow">NFL QUANTITATIVE GAME MODEL</p><h1>Current-week projections</h1><p>Pregame model probabilities and market comparison. Results are analytical projections, not guarantees.</p></section><div className="stat-grid"><div><b>{games.data.length}</b><span>Upcoming games</span></div><div><b>{predictions.data.length}</b><span>Published projections</span></div><div><b>V0.1</b><span>Model release</span></div></div><PredictionTable predictions={predictions.data} games={games.data} /></> }
function Predictions() { const predictions = useData('/predictions'); const games = useData('/games'); if (predictions.loading || games.loading) return <Loading />; return <><h1>Predictions</h1><p className="lede">Published model outputs, preserved with their original model version and timestamp.</p><PredictionTable predictions={predictions.data || []} games={games.data || []} /></> }
function Performance() { const data = useData('/performance'); if (data.loading) return <Loading />; if (data.error) return <Empty>Performance data is unavailable.</Empty>; const { moneyline, spread } = data.data; return <><h1>Historical performance</h1><div className="metric-grid"><article><p>Moneyline accuracy</p><b>{pct(moneyline.accuracy)}</b><small>{moneyline.games} graded games · Brier {moneyline.brier_score?.toFixed(3) ?? '—'}</small></article><article><p>Spread MAE</p><b>{spread.mae?.toFixed(2) ?? '—'}</b><small>{spread.games} graded games · RMSE {spread.rmse?.toFixed(2) ?? '—'}</small></article><article><p>ATS record</p><b>{spread.ats ? `${spread.ats.wins}-${spread.ats.losses}-${spread.ats.pushes}` : '—'}</b><small>ROI appears after linked live odds snapshots</small></article></div></> }
function History() { const predictions = useData('/predictions'); if (predictions.loading) return <Loading />; return <><h1>Prediction history</h1><p className="lede">Every published model output remains visible after games finish.</p><PredictionTable predictions={predictions.data || []} /></> }
function Methodology() { return <><h1>Methodology</h1><div className="method"><h2>Pregame only</h2><p>Every historical feature is calculated from information available before kickoff. Future results never enter a prior prediction.</p><h2>Model progression</h2><p>The platform begins with Elo, then tests logistic win probability and Ridge point-differential models on chronological splits.</p><h2>Market comparison</h2><p>American moneyline prices are normalized to no-vig probabilities before comparison. Outputs describe model disagreement, not betting instructions.</p></div></> }
function GameDetail({ id }) { const game = useData(`/games/${id}`); const predictions = useData(`/predictions/${id}`); if (game.loading || predictions.loading) return <Loading />; if (game.error) return <Empty>Game not found.</Empty>; return <><a className="back" href="/predictions">← Predictions</a><h1>{game.data.away_team} @ {game.data.home_team}</h1><p className="lede">Week {game.data.week} · {new Date(game.data.date).toLocaleString()}</p><PredictionTable predictions={predictions.data || []} games={[game.data]} /></> }
function App() { const path = window.location.pathname; const page = path.startsWith('/games/') ? <GameDetail id={decodeURIComponent(path.slice(7))} /> : path === '/predictions' ? <Predictions /> : path === '/performance' ? <Performance /> : path === '/history' ? <History /> : path === '/methodology' ? <Methodology /> : <Dashboard />; return <div className="shell"><aside><a className="brand" href="/"><span>NF</span> MODEL</a><nav>{nav.map(([href, label]) => <a className={path === href ? 'active' : ''} href={href} key={href}>{label}</a>)}</nav><p className="side-note">BETA V0.1<br />NFL · REGULAR SEASON</p></aside><main>{page}</main></div> }
createRoot(document.getElementById('root')).render(<App />)
