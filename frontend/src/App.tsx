import { useEffect, useRef, useState } from 'react';
import { ArrowClockwise, BookOpenText, CaretRight, Info, List, X } from '@phosphor-icons/react';
import { ApiError, ask, getConfig, isAbort, search } from './api';
import { Composer } from './components/Composer';
import { Results } from './components/Results';
import { Sidebar } from './components/Sidebar';
import { Sources } from './components/Sources';
import { copy, documentaryLabel, formatDate } from './i18n';
import type { AskResponse, HistoryEntry, Locale, RequestSettings, RequestState, SearchHit, Snapshot, UIConfig } from './types';

export default function App() {
 const [locale, setLocale] = useState<Locale>('fr');
 const text = copy[locale];
 const [page, setPage] = useState<'search' | 'sources'>('search');
 const [menuOpen, setMenuOpen] = useState(false);
 const [helpOpen, setHelpOpen] = useState(false);
 const menuDialog = useRef<HTMLDialogElement>(null);
 const helpDialog = useRef<HTMLDialogElement>(null);
 const inputRef = useRef<HTMLTextAreaElement>(null);
 const [config, setConfig] = useState<UIConfig | null>(null);
 const [configLoading, setConfigLoading] = useState(true);
 const [configError, setConfigError] = useState(false);
 const [configRevision, setConfigRevision] = useState(0);
 const initializedMethod = useRef(false);
 const [online, setOnline] = useState(navigator.onLine);
 const [question, setQuestion] = useState('');
 const [settings, setSettings] = useState<RequestSettings>({ sourceLanguage: 'auto', method: 'bm25', generator: 'extractive', topK: 5 });
 const [advanced, setAdvanced] = useState(false);
 const [state, setState] = useState<RequestState>('idle');
 const [result, setResult] = useState<AskResponse | null>(null);
 const [error, setError] = useState<number | null>(null);
 const [history, setHistory] = useState<HistoryEntry[]>([]);
 const [selected, setSelected] = useState<string | null>(null);
 const lastSnapshot = useRef<Snapshot | null>(null);
 const activeRequest = useRef<{ id: string; controller: AbortController } | null>(null);
 const rankingRequest = useRef<AbortController | null>(null);
 const [ranking, setRanking] = useState<SearchHit[] | null>(null);
 const [rankingState, setRankingState] = useState<'idle' | 'loading' | 'done' | 'error'>('idle');
 const [showRanking, setShowRanking] = useState(false);

 useEffect(() => { document.documentElement.lang = locale; document.documentElement.dir = locale === 'ar' ? 'rtl' : 'ltr'; document.title = `Daftar — ${text.corpusShort}`; }, [locale, text.corpusShort]);
 useEffect(() => { const connect = () => setOnline(true); const disconnect = () => setOnline(false); window.addEventListener('online', connect); window.addEventListener('offline', disconnect); return () => { window.removeEventListener('online', connect); window.removeEventListener('offline', disconnect); }; }, []);
 useEffect(() => { const desktop = window.matchMedia('(width > 900px)'); const closeOnDesktop = () => { if (desktop.matches) setMenuOpen(false); }; desktop.addEventListener('change', closeOnDesktop); return () => desktop.removeEventListener('change', closeOnDesktop); }, []);
 useEffect(() => { if (menuOpen) menuDialog.current?.showModal(); else menuDialog.current?.close(); }, [menuOpen]);
 useEffect(() => { if (helpOpen) helpDialog.current?.showModal(); else helpDialog.current?.close(); }, [helpOpen]);
 useEffect(() => {
  const controller = new AbortController(); let current = true;
  setConfigLoading(true); setConfigError(false);
  void getConfig(controller.signal).then(value => {
   if (!current) return;
   setConfig(value);
   if (!initializedMethod.current && value.available_modes.length) { initializedMethod.current = true; setSettings(previous => ({ ...previous, method: value.available_modes.includes('semantic') ? 'semantic' : 'bm25', topK: 5 })); }
  }).catch(cause => { if (current && !isAbort(cause)) { setConfigError(true); setConfig(null); } }).finally(() => { if (current) setConfigLoading(false); });
  return () => { current = false; controller.abort(); };
 }, [configRevision]);
 useEffect(() => () => { activeRequest.current?.controller.abort(); rankingRequest.current?.abort(); }, []);

 function resetRanking() { rankingRequest.current?.abort(); rankingRequest.current = null; setRanking(null); setRankingState('idle'); setShowRanking(false); }
 function stopCurrent(showNotice = false) {
  const active = activeRequest.current; if (!active) return;
  activeRequest.current = null; active.controller.abort();
  setHistory(previous => previous.map(entry => entry.id === active.id ? { ...entry, state: 'cancelled', error: null } : entry));
  if (showNotice) { setState('cancelled'); setError(null); setResult(null); }
 }
 async function execute(snapshot: Snapshot) {
  if (!config?.ready || !config.available_modes.includes(snapshot.settings.method) || !config.generators.choices.includes(snapshot.settings.generator)) { setError(422); setState('error'); return; }
  if (snapshot.question.trim().length < config.request_limits.question_min_length) return;
  stopCurrent(); resetRanking(); setPage('search');
  const id = crypto.randomUUID(); const controller = new AbortController();
  activeRequest.current = { id, controller }; lastSnapshot.current = snapshot;
  setQuestion(snapshot.question); setSettings(snapshot.settings); setSelected(id); setState('loading'); setResult(null); setError(null);
  const entry: HistoryEntry = { id, snapshot, state: 'loading', result: null, error: null, at: Date.now() };
  setHistory(previous => [entry, ...previous].slice(0, 5));
  try {
   const response = await ask(snapshot, controller.signal);
   if (activeRequest.current?.id !== id) return;
   activeRequest.current = null; setResult(response); setState('done');
   setHistory(previous => previous.map(item => item.id === id ? { ...item, state: 'done', result: response } : item));
  } catch (cause) {
   if (activeRequest.current?.id !== id) return;
   activeRequest.current = null;
   const cancelled = isAbort(cause); const code = cause instanceof ApiError ? cause.status : 0;
   setError(cancelled ? null : code); setState(cancelled ? 'cancelled' : 'error');
   setHistory(previous => previous.map(item => item.id === id ? { ...item, state: cancelled ? 'cancelled' : 'error', error: cancelled ? null : code } : item));
  }
 }
 function restore(entry: HistoryEntry) {
  const wasLoading = entry.state === 'loading'; stopCurrent(); resetRanking();
  setQuestion(entry.snapshot.question); setSettings(entry.snapshot.settings); lastSnapshot.current = entry.snapshot; setResult(entry.result); setError(entry.error); setState(wasLoading ? 'cancelled' : entry.state); setSelected(entry.id); setPage('search'); setMenuOpen(false);
 }
 function navigate(value: 'search' | 'sources') { setPage(value); setMenuOpen(false); }
 function example(value: string) { setPage('search'); setQuestion(value); inputRef.current?.focus(); }
 function clearHistory() { setHistory([]); setSelected(null); }
 async function toggleRanking() {
  if (showRanking) { setShowRanking(false); return; }
  setShowRanking(true);
  if (rankingState === 'done' || !lastSnapshot.current || !result) return;
  const controller = new AbortController(); rankingRequest.current?.abort(); rankingRequest.current = controller; setRankingState('loading');
  try { const response = await search(lastSnapshot.current, result.source_language, controller.signal); if (rankingRequest.current !== controller) return; setRanking(response.hits); setRankingState('done'); }
  catch (cause) { if (rankingRequest.current === controller && !isAbort(cause)) setRankingState('error'); }
 }
 const sidebarProps = { text, page, history, selected, onPage: navigate, onRestore: restore, onClear: clearHistory, onHelp: () => { setMenuOpen(false); setHelpOpen(true); } };
 const ready = config?.ready && !configLoading && !configError;
 return <div className="app-shell min-h-dvh bg-canvas text-ink">
  <a className="skip-link" href="#main-content">{text.question}</a>
  <aside className="desktop-sidebar"><Sidebar {...sidebarProps}/></aside>
  <dialog className="mobile-navigation" aria-label={text.menu} ref={menuDialog} onCancel={() => setMenuOpen(false)} onClose={() => setMenuOpen(false)} onClick={event => { if (event.target === event.currentTarget) setMenuOpen(false); }}><Sidebar {...sidebarProps} onClose={() => setMenuOpen(false)}/></dialog>
  <div className="main-shell">
   <p className="sr-only" role="status" aria-live="polite" aria-atomic="true">{state === 'done' && result ? result.assessment?.message ?? (result.status === 'abstained' ? text.refused : `${result.citations.length} ${text.numberPassages}`) : ''}</p>
   <header className="app-header flex items-center justify-between gap-4 border-b border-line px-5 sm:px-10"><div className="flex min-w-0 items-center gap-3"><button className="icon-button mobile-menu-button" aria-label={text.menu} onClick={() => setMenuOpen(true)}><List size={22}/></button><span className="hidden text-xs text-muted sm:inline">{text.corpusShort}</span><CaretRight size={12} className="directional hidden text-muted sm:block" aria-hidden="true"/><span className="text-xs font-medium">{page === 'search' ? text.search : text.sources}</span></div><div className="language-switch flex items-center gap-1" aria-label={locale === 'fr' ? 'Langue de l’interface' : 'لغة الواجهة'}><button lang="fr" aria-pressed={locale === 'fr'} onClick={() => setLocale('fr')} className={locale === 'fr' ? 'active' : ''}>FR</button><span className="text-line" aria-hidden="true">/</span><button lang="ar" aria-pressed={locale === 'ar'} onClick={() => setLocale('ar')} className={locale === 'ar' ? 'active' : ''}>العربية</button></div></header>
   <main id="main-content" className="content-wrap mx-auto w-full px-5 pb-12 pt-9 sm:px-10 sm:pt-12" tabIndex={-1}>
    {!online && <div className="service-notice mb-6" role="status"><Info size={17}/><span>{text.offline}</span></div>}
    {(configError || (!configLoading && config && !config.ready)) && <div className="service-notice mb-6" role="status"><Info size={17}/><span>{configError ? text.configError : text.notReady}</span><button className="subtle-button ms-auto" onClick={() => setConfigRevision(value => value + 1)}><ArrowClockwise size={14}/>{text.reconnect}</button></div>}
    {configLoading && <p className="mb-6 flex items-center gap-2 text-xs text-muted" role="status"><span className="loading-dot"/>{text.configLoading}</p>}
    {ready && config?.profile && !config.profile.domain_loaded && <div className="service-notice mb-6" role="status"><Info size={17}/><span>{locale === 'fr' ? 'Textes spécialisés non chargés : la lecture reste limitée à la loi de 2022.' : 'النصوص المتخصصة غير محملة: تقتصر القراءة على قانون نسخة 2022.'}</span></div>}
    {page === 'search' ? <>
     <div className="mb-8 grid gap-6 lg:grid-cols-[minmax(0,1fr)_235px] lg:items-end"><div><p className="eyebrow flex items-center gap-2"><BookOpenText size={15}/>{text.corpus}</p><h1 className="page-title mt-4 max-w-[650px]">{text.title}</h1><p className="mt-4 max-w-[620px] text-sm leading-7 text-muted">{text.subtitle}</p></div><div className="edition-note border-s-2 border-line ps-4"><p className="text-[10px] font-medium uppercase tracking-wider text-muted">{text.edition}</p><p className="mt-2 text-sm font-medium">{documentaryLabel(config?.corpus_label ?? formatDate(config?.corpus_version ?? '2022-03-31', locale), locale)}</p><p className="mt-2 text-[11px] leading-6 text-muted">{text.scopeBody}</p></div></div>
     <Composer locale={locale} text={text} question={question} settings={settings} config={ready ? config : null} loading={state === 'loading'} advanced={advanced} inputRef={inputRef} onQuestion={setQuestion} onSettings={setSettings} onAdvanced={() => setAdvanced(value => !value)} onSubmit={() => void execute({ question: question.trim(), settings: { ...settings, topK: 5 } })} onCancel={() => stopCurrent(true)} onExample={example}/>
     <Results submittedQuestion={lastSnapshot.current?.question ?? ''} locale={locale} text={text} state={state} result={result} error={error} advanced={advanced} ranking={ranking} rankingState={rankingState} showRanking={showRanking} onRanking={() => void toggleRanking()} onRetry={() => { if (lastSnapshot.current) void execute(lastSnapshot.current); }} onExtractive={() => { if (lastSnapshot.current) void execute({ ...lastSnapshot.current, settings: { ...lastSnapshot.current.settings, generator: 'extractive' } }); }}/>
    </> : <Sources sources={config?.sources ?? []} locale={locale} text={text}/>}
    <footer className="page-footer mt-14 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-5 text-[10px] leading-6 text-muted"><span>Daftar / <span lang="ar">دفتر</span> · {text.helpLegal}</span><button className="subtle-button" onClick={() => setHelpOpen(true)}>{text.help}<Info size={13}/></button></footer>
   </main>
  </div>
  <dialog ref={helpDialog} className="help-dialog paper" onCancel={() => setHelpOpen(false)} onClose={() => setHelpOpen(false)} aria-labelledby="help-title" onClick={event => { if (event.target === event.currentTarget) setHelpOpen(false); }}><div className="flex items-start justify-between gap-5"><h2 id="help-title" className="text-xl font-medium">{text.help}</h2><button className="icon-button" aria-label={text.close} onClick={() => setHelpOpen(false)}><X size={20}/></button></div><p className="mt-5 text-sm leading-8 text-muted">{text.helpText}</p><p className="mt-5 border-t border-line pt-5 text-sm leading-8">{text.scopeBody}</p><p className="mt-3 text-xs leading-7 text-muted">{text.generatedNote} {text.sourceFoot}</p><p className="mt-6 text-xs font-medium text-accent">{text.helpLegal}</p></dialog>
 </div>;
}
