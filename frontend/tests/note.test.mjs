import test from 'node:test';
import assert from 'node:assert/strict';
import { noteMarkdown } from '../src/note.ts';

test('export preserves partial status, missing points and source edition without raw quotes', () => {
  const result = {
    status: 'evidence_found', corpus_version: '2023-12', corpus_label: 'Recueil fin 2023',
    answer: 'Proposition documentaire [1]',
    assessment: { status: 'partial', missing_points: ['Montant non établi'],
      clarification: null, scope_note: 'Actualité non établie.',
      requested_as_of: null, institution_type: 'credit_institution' },
    citations: [{ document_title: 'Document de test', document_id: 'synthetic',
      article_id: '4', page_start: 2, page_end: 2,
      source_url: 'https://www.bkam.ma/synthetic.pdf', sha256: 'a'.repeat(64),
      quote: 'RAW_SOURCE_QUOTE_NOT_TO_COPY_IN_NOTE' }],
  };
  const output = noteMarkdown('Question de test', result);
  assert.match(output, /Statut : partial/);
  assert.match(output, /Montant non établi/);
  assert.match(output, /Recueil fin 2023/);
  assert.match(output, /#page=2/);
  assert.match(output, /Actualité non établie/);
  assert.doesNotMatch(output, /RAW_SOURCE_QUOTE_NOT_TO_COPY_IN_NOTE/);
});
