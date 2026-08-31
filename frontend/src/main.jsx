import { createRoot } from 'react-dom/client'
import { useEffect, useState } from 'react'
import { api } from './services/api'
import './styles.css'

const nav = [['/', 'NFL Dashboard'], ['/predictions', 'NFL Predictions'], ['/performance', 'NFL Performance'], ['/history', 'NFL History'], ['/mlb', 'MLB Operations'], ['/methodology', 'Methodology']]
const pct = value => value == null ? '—' : `${(value * 100).toFixed(1)}%`
const margin = value => value == null ? '—' : `${value > 0 ? '+' : ''}${Number(value).toFixed(1)}`
const teamLine = (value, game, market = false) => {
  if (value == null || !game) return '—'
  const homeMargin = market ? -value : value
  const team = homeMargin >= 0 ? game.home_team : game.away_team
  return `${team} -${Math.abs(homeMargin).toFixed(1)}`
}
const disagreement = (value, game) => {
  if (value == null || !game) return '—'
  const team = value >= 0 ? game.home_team : game.away_team
  return `${Math.abs(value).toFixed(1)} pts → ${team}`
}

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
  return <div className="table-wrap"><table><thead><tr><th>Matchup</th><th>Model win %</th><th>Market win %</th><th>Difference</th><th>Model line</th><th>Market line</th><th>Model disagreement</th></tr></thead><tbody>{predictions.map(prediction => { const game = gameById[prediction.game_id]; return <tr key={prediction.id}><td>{game ? <a href={`/games/${game.id}`}>{game.away_team} @ {game.home_team}</a> : prediction.game_id}</td><td>{pct(prediction.home_win_probability)}</td><td>{pct(prediction.market_home_probability)}</td><td className="accent">{pct(prediction.moneyline_difference)}</td><td>{teamLine(prediction.predicted_margin, game)}</td><td>{teamLine(prediction.market_spread, game, true)}</td><td className="accent">{disagreement(prediction.spread_difference, game)}</td></tr> })}</tbody></table></div>
}

function Dashboard() { const games = useData('/games/current-week'); const predictions = useData('/predictions/current-week'); if (games.loading || predictions.loading) return <Loading />; if (games.error || predictions.error) return <Empty>Backend unavailable. Start FastAPI on port 8000.</Empty>; return <><section className="hero"><p className="eyebrow">NFL QUANTITATIVE GAME MODEL</p><h1>Current-week projections</h1><p>Pregame model probabilities and market comparison. Results are analytical projections, not guarantees.</p></section><div className="stat-grid"><div><b>{games.data.length}</b><span>Upcoming games</span></div><div><b>{predictions.data.length}</b><span>Published projections</span></div><div><b>V0.1</b><span>Model release</span></div></div><PredictionTable predictions={predictions.data} games={games.data} /></> }
function Predictions() { const predictions = useData('/predictions'); const games = useData('/games'); if (predictions.loading || games.loading) return <Loading />; return <><h1>Predictions</h1><p className="lede">Published model outputs, preserved with their original model version and timestamp.</p><PredictionTable predictions={predictions.data || []} games={games.data || []} /></> }
function Performance() { const data = useData('/performance'); if (data.loading) return <Loading />; if (data.error) return <Empty>Performance data is unavailable.</Empty>; const { moneyline, spread } = data.data; return <><h1>Historical performance</h1><div className="metric-grid"><article><p>Moneyline accuracy</p><b>{pct(moneyline.accuracy)}</b><small>{moneyline.games} graded games · Brier {moneyline.brier_score?.toFixed(3) ?? '—'}</small></article><article><p>Spread MAE</p><b>{spread.mae?.toFixed(2) ?? '—'}</b><small>{spread.games} graded games · RMSE {spread.rmse?.toFixed(2) ?? '—'}</small></article><article><p>ATS record</p><b>{spread.ats ? `${spread.ats.wins}-${spread.ats.losses}-${spread.ats.pushes}` : '—'}</b><small>ROI appears after linked live odds snapshots</small></article></div></> }
function History() { const predictions = useData('/predictions'); if (predictions.loading) return <Loading />; return <><h1>Prediction history</h1><p className="lede">Every published model output remains visible after games finish.</p><PredictionTable predictions={predictions.data || []} /></> }
function Methodology() { return <><h1>Methodology</h1><div className="method"><h2>Pregame only</h2><p>Every historical feature is calculated from information available before kickoff. Future results never enter a prior prediction.</p><h2>Model progression</h2><p>The platform begins with Elo, then tests logistic win probability and Ridge point-differential models on chronological splits.</p><h2>Market comparison</h2><p>American moneyline prices are normalized to no-vig probabilities before comparison. Outputs describe model disagreement, not betting instructions.</p></div></> }
function MlbOperations() {
  const status = useData('/mlb/status')
  const [selectedId, setSelectedId] = useState('')
  if (status.loading) return <Loading />
  if (status.error) return <Empty>MLB data is unavailable. Run the MLB update scripts, then refresh this page.</Empty>
  const data = status.data
  const selected = data.predictions.find(prediction => String(prediction.id) === selectedId)
  return <><section className="hero"><p className="eyebrow">MLB HOME-RUN MODEL · BETA</p><h1>MLB operations</h1><p>Completed-game ingestion, leakage-safe batter history, and versioned HR model training are kept separate from the NFL model.</p></section><div className="stat-grid"><div><b>{data.completed_games}</b><span>Completed games imported</span></div><div><b>{data.feature_rows}</b><span>Pregame batter feature rows</span></div><div><b>{data.scheduled_games.length}</b><span>Upcoming scheduled games</span></div></div><h2>Today’s schedule</h2>{data.scheduled_games.length ? <div className="table-wrap"><table><thead><tr><th>Matchup</th><th>First pitch</th><th>Probable pitchers</th></tr></thead><tbody>{data.scheduled_games.map(game => <tr key={game.id}><td>{game.away_team} @ {game.home_team}</td><td>{new Date(game.first_pitch).toLocaleString()}</td><td>{game.probable_away_pitcher || 'TBD'} / {game.probable_home_pitcher || 'TBD'}</td></tr>)}</tbody></table></div> : <Empty>No upcoming MLB games are currently loaded.</Empty>}<h2>Latest model</h2>{data.models.length ? <div className="method"><p><b>{data.models[0].version}</b></p><p>Trained {new Date(data.models[0].trained_at).toLocaleString()} using completed games through {new Date(data.models[0].training_data_through).toLocaleString()}.</p></div> : <Empty>No MLB model has been trained yet.</Empty>}<h2>Official HR predictions</h2>{data.predictions.length ? <><label className="batter-picker">Select a batter<select value={selectedId} onChange={event => setSelectedId(event.target.value)}><option value="">Choose a published prediction</option>{data.predictions.map(prediction => <option key={prediction.id} value={prediction.id}>{prediction.player_name || `Player ${prediction.player_id}`} · {prediction.team || 'Team unavailable'}</option>)}</select></label>{selected ? <article className="prediction-card"><p className="eyebrow">OFFICIAL HR PREDICTION</p><h3>{selected.player_name || `Player ${selected.player_id}`}</h3><p>{selected.team || 'Team unavailable'} · Game {selected.game_id}</p><b>{pct(selected.probability)}</b><span>Home-run probability</span><small>{selected.model_version} · {selected.result || 'Awaiting result'}</small></article> : null}<div className="table-wrap"><table><thead><tr><th>Game</th><th>Player</th><th>Team</th><th>HR probability</th><th>Model</th><th>Result</th></tr></thead><tbody>{data.predictions.map(prediction => <tr key={prediction.id}><td>{prediction.game_id}</td><td>{prediction.player_name || prediction.player_id}</td><td>{prediction.team || '—'}</td><td>{pct(prediction.probability)}</td><td>{prediction.model_version}</td><td>{prediction.result || 'Pending'}</td></tr>)}</tbody></table></div></> : <Empty>No official MLB HR predictions yet. Run the schedule and prediction scripts after both starting lineups appear in the MLB game feed.</Empty>}</> }
function GameDetail({ id }) { const game = useData(`/games/${id}`); const predictions = useData(`/predictions/${id}`); if (game.loading || predictions.loading) return <Loading />; if (game.error) return <Empty>Game not found.</Empty>; return <><a className="back" href="/predictions">← Predictions</a><h1>{game.data.away_team} @ {game.data.home_team}</h1><p className="lede">Week {game.data.week} · {new Date(game.data.date).toLocaleString()}</p><PredictionTable predictions={predictions.data || []} games={[game.data]} /></> }
function App() { const path = window.location.pathname; const page = path.startsWith('/games/') ? <GameDetail id={decodeURIComponent(path.slice(7))} /> : path === '/predictions' ? <Predictions /> : path === '/performance' ? <Performance /> : path === '/history' ? <History /> : path === '/mlb' ? <MlbOperations /> : path === '/methodology' ? <Methodology /> : <Dashboard />; return <div className="shell"><aside><a className="brand" href="/"><span>NF</span> MODEL</a><nav>{nav.map(([href, label]) => <a className={path === href ? 'active' : ''} href={href} key={href}>{label}</a>)}</nav><p className="side-note">BETA V0.1<br />NFL + MLB</p></aside><main>{page}</main></div> }
createRoot(document.getElementById('root')).render(<App />)
