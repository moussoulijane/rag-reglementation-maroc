import { noteMarkdown } from '../note';
import { DownloadSimple, Info } from '@phosphor-icons/react';
import type { AskResponse, Locale } from '../types';

const statusText = {
  fr: { complete: 'Points identifiés étayés', partial: 'Réponse partielle', absent: 'Information non établie', temporal: 'Date non couverte', ambiguous: 'Précision nécessaire' },
  ar: { complete: 'النقاط المحددة مسندة', partial: 'إجابة جزئية', absent: 'المعلومة غير مثبتة', temporal: 'التاريخ غير مغطى', ambiguous: 'يلزم التوضيح' },
};

export function AssistantSummary({ result, question, locale, onEvidence }: {
  result: AskResponse; question: string; locale: Locale; onEvidence: (index: number) => void;
}) {
  const assessment = result.assessment;
  if (!assessment) return null;
  const ar = locale === 'ar';
  function download() {
    const url = URL.createObjectURL(new Blob([noteMarkdown(question, result)], { type: 'text/markdown;charset=utf-8' }));
    const link = document.createElement('a');
    link.href = url; link.download = 'daftar-note.md'; link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <section className={`assistant-summary paper mb-8 p-6 sm:p-8 status-${assessment.status}`} aria-label={ar ? 'القراءة المسندة' : 'Lecture étayée'}>
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div><p className="text-[10px] font-medium uppercase tracking-wide text-muted">{ar ? 'شكايات ووساطة' : 'Réclamations et médiation'}</p>
        <h3 className="mt-2 text-xl font-medium">{statusText[locale][assessment.status]}</h3></div>
      <button className="secondary-button" onClick={download}><DownloadSimple size={16}/>{ar ? 'تصدير المذكرة' : 'Exporter la note'}</button>
    </div>
    <p className="mt-4 text-sm leading-7 text-muted" lang={result.query_language} dir="auto">{assessment.message}</p>
    {assessment.claims?.length ? <div className="mt-5 grid gap-5">{assessment.claims.map(claim =>
      <p className="text-[15px] leading-8" key={claim.id} lang={result.query_language} dir="auto">{claim.text}{' '}
        {claim.citation_indices.map(index => <button className="inline-reference" key={index} onClick={() => onEvidence(index)} aria-label={`${ar ? 'الدليل' : 'Preuve'} ${index}`}>[{index}]</button>)}
      </p>)}</div> : result.citations.length ? <p className="mt-4 text-sm leading-7" dir="auto" lang={result.query_language}>{result.answer}</p> : null}
    {assessment.missing_points.length > 0 && <div className="mt-6 border-t border-line pt-5"><h4 className="text-xs font-semibold">{ar ? 'ما لم يثبت' : 'Ce qui reste non établi'}</h4>
      <ul className="mt-3 list-disc space-y-2 ps-5 text-sm leading-7 text-muted">{assessment.missing_points.map(value => <li key={value} dir="auto">{value}</li>)}</ul></div>}
    {assessment.clarification && assessment.clarification !== assessment.message && <p className="mt-5 rounded-md bg-canvas p-4 text-sm leading-7" dir="auto" lang={result.query_language}>{assessment.clarification}</p>}
    {assessment.available_source_hint && <p className="mt-4 text-xs leading-7 text-muted" dir="auto">{assessment.available_source_hint}</p>}
    <details className="mt-6 border-t border-line pt-3"><summary className="cursor-pointer py-2 text-xs text-muted">{ar ? 'النقاط التي فُهمت من السؤال' : 'Les points identifiés dans votre question'}</summary>
      <ul className="mt-3 grid gap-2 text-xs leading-6">{assessment.findings.map(finding => <li className="flex flex-wrap justify-between gap-3" key={finding.key}><span dir="auto">{finding.label}</span><span className="text-muted">{finding.state === 'supported' ? ar ? 'مسند' : 'Étayé' : ar ? 'غير مثبت' : 'Non établi'}</span></li>)}</ul>
    </details>
    <p className="mt-5 flex items-start gap-2 text-xs leading-7 text-muted"><Info size={15} className="mt-1 shrink-0"/>{ar ? 'قراءة وثائقية داخلية، دون تحقق قانوني مستقل أو إثبات للسريان الحالي.' : 'Lecture documentaire interne ; validation juridique indépendante et actualité non établies.'}</p>
  </section>;
}
