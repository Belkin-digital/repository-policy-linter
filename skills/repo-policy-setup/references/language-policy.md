---
created: 2026-10-29
updated: 2026-10-29
---

# Optional language and terminology policies

Read only for lexical checking or an authorized editorial migration. There is no universal ban
on English or universal client glossary. A lexical match does not determine the right translation,
the artifact's audience or whether an acceptance scenario tests user behavior.

Before implementation define owner, paths/types/audience, the representation actually read by
the recipient, canonical glossary and precedence of merged lists, prose/code/name/URL/quote
categories, quote boundaries, historical adoption and every checker/exporter entrypoint.
Keep a formal-language requirement distinct from the host document's audience; changing metadata
must not hide a violation of a canonical client-facing scenario.

Reuse the actual exporter or visible-text filter instead of reconstructing hidden sections and
columns with unrelated regex. Distinguish source H1, export title, link label and technical URL.
Report source paths/locations; transformed line numbers need an explicit mapping.

Keep one maintained glossary and derive other representations. If lists are merged, verify the
effective result: removing a prohibition from one table may leave it in another source. Explicit
term IDs, forms, allow/suggest/context behavior and meaning scope can be useful project data;
they are not built-in `policy.yaml` fields. Do not infer forms from typography or `/`, claim
morphology without implementation or copy a client's allowed vocabulary into universal defaults.

Quote policy requires a real project decision: external-only, selected quote forms or no quote
exemption. Quotes alone do not prove external provenance. Define straight/typographic pairs,
nesting, formatting, apostrophes and unterminated quotes. YAML syntactic quoting is not a visible
quotation; capitalization is not an exemption. Code/name labels must not conceal ordinary prose.

Run actual entrypoints against the same examples: prose, heading, table, code, link label versus
URL, hidden section with visible text resuming, paired/unterminated quote and blockquote including
lazy continuation without another `>`. One shared helper does not prove entrypoint parity.
Describe intentional Gherkin/other formal-language differences separately; keep native parsers
and their pinned versions rather than replacing them to make diagnostics agree.

Translate a whole sentence/paragraph with its intended meaning. Preserve product literals,
identifiers, links, numbers and facts. A changed entity, interface label, status, expected behavior
or test-result transfer is a substantive decision, separate from editorial permission. Read the
result after edits; a finite dictionary does not catch every mixed phrase or conceptual error.

Use the selected [adoption model](data-preservation.md) for historical language. Never copy a
different project's cutoff date or exemption classes. Preserve published results and original
bytes; a lexical exception does not remove arithmetic/integrity checks or change old verdicts.

Record the initial diagnostic unit: first match per file is not a count of all occurrences.
For each finding retain rule/path, fragment or stable fingerprint, actual decision and resolution
reason: prose edit, accepted term, quote exemption, historical adoption or checker correction.
Line numbers alone are unstable after edits. When the rule changed, report unchanged files as
reclassified, not repaired, and verify their bytes. Report lexical outcome separately from other
queues and any unperformed semantic review. Zero lexical warnings is not overall acceptance.
