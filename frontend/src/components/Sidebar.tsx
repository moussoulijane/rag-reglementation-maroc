import { BookOpenText, MagnifyingGlass, Files, ClockCounterClockwise, Question, X, Trash } from '@phosphor-icons/react';
import type { Copy } from '../i18n';
import type { HistoryEntry } from '../types';

interface Props { text: Copy; page: 'search' | 'sources'; history: HistoryEntry[]; selected: string | null; onPage: (page: 'search' | 'sources') => void; onRestore: (entry: HistoryEntry) => void; onClear: () => void; onHelp: () => void; onClose?: () => void }
export function Sidebar({ text, page, history, selected, onPage, onRestore, onClear, onHelp, onClose }: Props) {
 return <div className="sidebar-inner flex min-h-full flex-col p-5">
  <div className="mb-12 flex items-center gap-3 px-2 pt-2">
   <span className="brand-mark"><BookOpenText size={24} weight="duotone" aria-hidden="true" /></span>
   <div><div className="brand-name" dir="ltr">daftar<span lang="ar"> / دفتر</span></div><div className="mt-1 text-[11px] text-white/65">{text.product}</div></div>
   {onClose && <button className="icon-button ms-auto text-white" onClick={onClose} aria-label={text.close}><X size={20}/></button>}
  </div>
  <nav aria-label={text.menu} className="grid gap-1">
   <button className={`nav-item ${page === 'search' ? 'is-active' : ''}`} aria-current={page === 'search' ? 'page' : undefined} onClick={() => onPage('search')}><MagnifyingGlass size={19}/>{text.search}</button>
   <button className={`nav-item ${page === 'sources' ? 'is-active' : ''}`} aria-current={page === 'sources' ? 'page' : undefined} onClick={() => onPage('sources')}><Files size={19}/>{text.sources}</button>
  </nav>
  <div className="mt-12 flex items-center justify-between px-2 text-[11px] font-medium tracking-wide text-white/55"><span>{text.recent}</span><ClockCounterClockwise size={15} aria-hidden="true"/></div>
  {history.length === 0 ? <p className="mt-4 px-2 text-xs leading-6 text-white/50">{text.historyEmpty}</p> : <ol className="mt-3 grid gap-1">{history.map(entry => <li key={entry.id}><button className={`history-item ${selected === entry.id ? 'is-selected' : ''}`} onClick={() => onRestore(entry)} title={entry.snapshot.question} dir="auto"><span className="line-clamp-2">{entry.snapshot.question}</span>{entry.state === 'loading' && <span className="history-dot" aria-label={text.loading}/>}</button></li>)}</ol>}
  {history.length > 0 && <button className="mt-3 flex min-h-11 items-center gap-2 px-2 text-xs text-white/55 hover:text-white" onClick={onClear}><Trash size={14}/>{text.clearHistory}</button>}
  <div className="mt-auto pt-12"><div className="sidebar-edition"><span className="text-[10px] tracking-widest text-white/50">{text.corpusShort}</span><span className="mt-2 block text-sm text-white/85" dir="ltr">2022 · fin 2023</span></div><button className="mt-4 flex min-h-11 items-center gap-2 px-2 text-xs text-white/65 hover:text-white" onClick={onHelp}><Question size={17}/>{text.help}</button></div>
 </div>;
}
