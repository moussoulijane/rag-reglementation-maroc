import type { AskResponse } from './types';

export function noteMarkdown(question: string, result: AskResponse): string {
  const assessment = result.assessment;
  const lines = ['# Daftar — note documentaire', '', question, '',
    `Statut : ${assessment?.status ?? result.status}`,
    `Sources : ${result.corpus_label ?? result.corpus_version}`, '', result.answer, ''];
  if (assessment?.missing_points.length) lines.push('## Points non établis', ...assessment.missing_points.map(value => `- ${value}`), '');
  if (assessment?.clarification && assessment.clarification !== result.answer) lines.push(assessment.clarification, '');
  lines.push('## Références', ...result.citations.map((value, index) =>
    `[${index + 1}] ${value.document_title ?? value.document_id} — article ${value.article_id}, PDF p. ${value.page_start}–${value.page_end}. ${value.source_url}#page=${value.page_start}\nSHA-256 : ${value.sha256}`), '',
    assessment?.scope_note ?? '', 'Relecture documentaire interne ; validation juridique indépendante non réalisée.');
  return lines.join('\n');
}

