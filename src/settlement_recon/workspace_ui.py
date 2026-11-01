# ruff: noqa: E501
# HTML/SVG templates keep complete tags and auditable attributes.
"""Evidence-first workspace presentation. Backend authorization lives in workspace.py."""

import html

PATHS = {
    "overview": "M3 10 12 3l9 7v10H3z M9 20v-7h6v7",
    "rates": "M4 20V10h3v10 M10 20V4h3v16 M16 20v-8h3v8",
    "converter": "m3 17 5-7 5 3 7-9 M16 4h4v4",
    "payments": "M6 3h12v18H6z M9 8h6 M9 12h6 M9 16h4",
    "settlements": "m12 3 8 4v6c0 5-8 8-8 8s-8-3-8-8V7z m-4 9 3 3 5-6",
    "reconciliation": "M3 7h16m-4-4 4 4-4 4 M21 17H5m4-4-4 4 4 4",
    "exceptions": "m12 3 10 18H2z M12 9v5 M12 17h.01",
    "ingest": "M4 6h16v15H4z M8 3h8 M12 10v7 m-3-3 3 3 3-3",
    "batches": "M5 3h10l4 4v14H5z M14 3v5h5 M8 12h8 M8 16h5",
    "provenance": "M12 6v5 M5 14v-3h14v3 M3 14h4v5H3z M10 2h4v4h-4z M17 14h4v5h-4z",
    "agent": "m12 2 2.5 7.5L22 12l-7.5 2.5L12 22l-2.5-7.5L2 12l7.5-2.5z",
    "operations": "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8 M12 2v3 M12 19v3 M2 12h3 M19 12h3 M5 5l2 2 M17 17l2 2 M5 19l2-2 M17 7l2-2",
    "search": "M20 20l-5-5 M10.5 3a7.5 7.5 0 1 0 0 15 7.5 7.5 0 0 0 0-15",
    "arrow": "M4 12h16 m-6-6 6 6-6 6",
    "close": "m6 6 12 12 M18 6 6 18",
    "menu": "M4 6h16 M4 12h16 M4 18h16",
    "copy": "M8 8h13v13H8z M16 8V3H3v13h5",
    "user": "M12 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8 M4 21v-3c0-6 16-6 16 0v3",
    "external": "M14 3h7v7 m0-7-11 11 M10 5H3v16h16v-7",
    "check": "m5 12 4 4L19 6",
}


def icon(name, size=20):
    return f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="{PATHS.get(name, PATHS["arrow"])}"/></svg>'


def link(slug, label, *, primary=False):
    return f'<a class="button {"primary" if primary else "secondary"}" href="/workspace/{slug}">{html.escape(label)}{icon("arrow", 17)}</a>'


def locked(title, description, slug):
    return f"""<section class="access-state"><div class="access-symbol">{icon(slug, 32)}</div><h2>{title}</h2><p>{description}</p><button class="primary" data-connect>{icon("user", 17)}Connect operator</button><div class="access-note">Public source data stays open. Financial records stay protected.</div></section>"""


def render(page, pages, css):
    title, subtitle = pages[page]
    title = "Settlement operations" if page == "overview" else title
    subtitle = "From source records to settlement evidence." if page == "overview" else subtitle
    navigation = "".join(
        f'<a href="/workspace/{slug}" {'aria-current="page"' if slug == page else ""}>{icon(slug)}<span>{html.escape("Operations overview" if slug == "overview" else label[0])}</span></a>'
        for slug, label in pages.items()
    )
    palette = "".join(
        f'<a href="/workspace/{slug}" data-keywords="{slug} {html.escape("Operations overview" if slug == "overview" else label[0]).lower()}">{icon(slug)}<span>{html.escape("Operations overview" if slug == "overview" else label[0])}</span>{icon("arrow", 16)}</a>'
        for slug, label in pages.items()
    )
    currency_table = (
        """<section class="panel market-panel"><div class="panel-heading"><div><h2>Reference market</h2><p>Captured ECB observations · 1 EUR</p></div><label class="search-field">"""
        + icon("search", 18)
        + """<span class="sr-only">Search currencies</span><input id="currency-search" placeholder="Search currencies" type="search" autocomplete="off"></label></div><div id="rates" aria-live="polite"><div class="skeleton">Loading captured observations…</div></div><div class="panel-footer"><span id="currency-count">Checking source</span><a href="/workspace/rates">View every currency</a></div></section>"""
    )
    source_panel = (
        """<section class="source-panel"><h2>A traceable source</h2><dl><div><dt>Source</dt><dd>Frankfurter / ECB</dd></div><div><dt>Captured</dt><dd id="capture-date">—</dd></div><div><dt>Digest</dt><dd><code id="source-digest">—</code><button class="icon-button" id="copy-digest" aria-label="Copy source digest">"""
        + icon("copy", 16)
        + """</button></dd></div></dl><a class="button primary" href="/workspace/provenance">"""
        + icon("external", 17)
        + """Inspect provenance</a></section>"""
    )
    workflow = (
        """<section class="workflow"><div class="panel-heading"><h2>A clear path from records to settlement</h2><a href="/workspace/ingest">Explore the workflow """
        + icon("arrow", 16)
        + """</a></div><div class="workflow-steps"><a href="/workspace/ingest"><span>1</span><div><h3>Connect your records</h3><p>Ingest actual payment records and bank statements. Financial ingestion requires operator access.</p></div></a><a href="/workspace/reconciliation"><span>2</span><div><h3>Reconcile precisely</h3><p>Match currency amounts with decimal precision and replay-safe processing.</p></div></a><a href="/workspace/exceptions"><span>3</span><div><h3>Resolve with evidence</h3><p>Trace exceptions to source records and inspect immutable batch receipts.</p></div></a></div></section>"""
    )
    agent_help = (
        """<section class="panel investigator-invite"><h2>Investigate with evidence</h2><p>Read-only AI. Public data. No sign-in.</p><p>Ask about reference rates and integration state, with a visible chain of evidence.</p>"""
        + link("agent", "Open investigator")
        + "</section>"
    )
    content = {
        "overview": """<section class="metrics-band" aria-label="Observed source statistics"><div><strong id="metric-currencies">—</strong><span>Reference currencies</span></div><div><strong id="metric-base">—</strong><span>Base currency</span></div><div><strong id="metric-date">—</strong><span>Observation date</span></div><div><strong>Not connected</strong><span>Bank feed</span></div></section><div class="overview-grid">"""
        + currency_table
        + '<div class="source-rail">'
        + source_panel
        + agent_help
        + "</div></div>"
        + workflow,
        "rates": currency_table
        + """<div class="source-footnote"><p id="rate-observation"></p><button id="sync" class="secondary">Synchronize provider</button><span>Refreshing the source requires operator access.</span></div>""",
        "converter": """<div class="calculator-layout"><section class="panel calculator"><h2>Calculate from evidence</h2><p>Exact cross-rate arithmetic from the captured observation.</p><form id="convert"><label>Amount<input name="amount" value="1000" inputmode="decimal" required></label><div class="currency-inputs"><label>From currency<select name="source"><option>EUR</option></select></label><button id="swap-currencies" class="icon-button" type="button" aria-label="Swap currencies">"""
        + icon("reconciliation")
        + """</button><label>To currency<select name="target"><option>USD</option></select></label></div><button class="primary">Calculate conversion"""
        + icon("arrow", 17)
        + """</button></form><div id="conversion" class="conversion-output" aria-live="polite"><p>Choose currencies and calculate to inspect the result.</p></div></section><div class="source-rail">"""
        + source_panel
        + """<section class="panel"><h2>Precision, with boundaries</h2><p>Calculations run on the server using decimal arithmetic. The observation date and source digest travel with every result.</p><p>These are reference rates, not executable prices or settlement proof.</p></section></div></div>""",
        "payments": '<div id="ledger">'
        + locked(
            "Your ledger, with lineage",
            "Connect an operator session to inspect authorized payment records. Public visitors cannot see customer financial data.",
            "payments",
        )
        + "</div>"
        + workflow,
        "settlements": '<div id="ledger">'
        + locked(
            "Follow the settlement evidence",
            "Inspect expected and received amounts for your authorized ledger, represented in exact currency minor units.",
            "settlements",
        )
        + "</div>"
        + workflow,
        "reconciliation": '<div class="section-actions"><button id="reconcile" class="primary">Run reconciliation</button><span>Protected financial operation</span></div><div id="ledger">'
        + locked(
            "Explain every match",
            "Connect your ledger to inspect matched, partial and unmatched payments using explicit matching rules.",
            "reconciliation",
        )
        + "</div>"
        + workflow,
        "exceptions": '<div id="ledger">'
        + locked(
            "Focus on what needs attention",
            "Authorized unmatched and partial payments appear here with their source evidence. No financial records are exposed publicly.",
            "exceptions",
        )
        + "</div>"
        + workflow,
        "ingest": """<div class="ingestion-layout"><section class="panel form-panel"><h2>Connect an actual source</h2><p>Validate before publication. Keep the original bytes.</p><form id="ingest"><label>Record type<select name="kind"><option value="payments">Payment JSON</option><option value="statement">Bank statement CSV</option></select></label><label>Source identifier<input name="source" required maxlength="87" placeholder="Your source identifier"></label><label class="file-field">Source file<input name="file" type="file" accept=".json,.csv" required><span>JSON or CSV · maximum 2 MB</span></label><button class="primary">Validate and ingest"""
        + icon("arrow", 17)
        + """</button></form><div id="receipt" aria-live="polite"></div></section><section class="panel process-guide"><h2>Every batch leaves a receipt</h2><ol><li><strong>Validate the envelope</strong><p>Enforce the input schema before downstream processing.</p></li><li><strong>Archive the source</strong><p>Preserve original bytes with a checksum.</p></li><li><strong>Publish or quarantine</strong><p>Accept valid records atomically or inspect the rejection evidence.</p></li><li><strong>Replay safely</strong><p>Reprocessing an identical source returns its original receipt.</p></li></ol><p>Writer access is required. Connect your existing operator session before ingestion.</p><button class="secondary" data-connect>Connect operator</button></section></div>""",
        "batches": '<div id="batches">'
        + locked(
            "The receipt behind every record",
            "Accepted, rejected and replayed inputs retain traceable receipts. Connect to verify original archived bytes.",
            "batches",
        )
        + "</div>",
        "provenance": """<section class="panel provenance-panel"><h2>From observation to source</h2><div class="provenance-path"><span>Frankfurter / ECB</span>"""
        + icon("arrow", 18)
        + """<span>Captured observation</span>"""
        + icon("arrow", 18)
        + """<span>SHA-256 identity</span></div><div id="provenance"><div class="skeleton">Loading source evidence…</div></div></section>""",
        "agent": """<div class="agent-layout"><section class="panel agent-workbench"><div class="agent-title">"""
        + icon("agent", 25)
        + """<h2>Ask a precise question.</h2></div><p>Investigate public reference rates and integration state. Every answer includes its actual tool evidence.</p><form id="agent"><label>Investigation question<textarea name="question" minlength="5" maxlength="600" required placeholder="What EUR/USD rate was observed, when was it captured, and where does the evidence come from?"></textarea></label><div class="prompt-buttons"><button type="button" data-prompt="Inspect reference_rates. Give the EUR/USD quote, observation date and source digest with evidence.">Explain the reference rate</button><button type="button" data-prompt="Inspect service_status. Which real integrations are connected and what are their limitations?">Inspect integrations</button></div><div class="agent-submit"><button class="primary" type="submit">Investigate with evidence"""
        + icon("arrow", 17)
        + """</button><span>No sign-in required</span></div></form><div id="answer" aria-live="polite"></div></section><aside class="agent-rail"><section class="panel"><h2>An answer you can inspect.</h2><ol class="agent-principles"><li><span>01</span><div><strong>Read the actual source</strong><p>Captured public observations, not invented transaction records.</p></div></li><li><span>02</span><div><strong>Follow the evidence</strong><p>Inspect the exact tool results behind every finding.</p></div></li><li><span>03</span><div><strong>Keep a clear boundary</strong><p>No payments, private ledger access or infrastructure changes.</p></div></li></ol></section><section class="panel quota-panel"><h3>Free, and deliberately bounded.</h3><p id="agent-provider">Checking provider configuration…</p><p>3 investigations per client / 10 minutes.<br>Shared: 2 per minute, 30 per UTC day.</p><p>Ask only about public data. Never enter secrets or private records. Google unpaid-service data terms apply.</p></section></aside></div>""",
        "operations": """<div class="operations-layout"><section class="panel"><div class="panel-heading"><h2>Integration boundary</h2><a href="/docs">API documentation"""
        + icon("external", 16)
        + """</a></div><div id="status"></div></section><section class="panel"><h2>Readiness checks</h2><p>Inspect the database and archive from an authorized operator session.</p><button id="readiness" class="secondary">Check database and archive</button><div id="ready"></div><p>Operator credentials stay in this page's memory and are cleared on navigation.</p></section></div>""",
    }[page]
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#ffffff"><meta name="description" content="Evidence-first payment reconciliation and public reference-rate investigations."><title>{html.escape(title)} | Settlement Recon</title><link rel="preload" href="/workspace/assets/manrope.ttf" as="font" type="font/ttf" crossorigin><style>{css}</style></head><body data-page="{page}"><a class="skip-link" href="#main-content">Skip to content</a><aside class="sidebar" id="workspace-navigation"><a class="brand" href="/workspace/overview"><span class="brand-mark">SR</span><span>Settlement Recon</span></a><nav aria-label="Workspace">{navigation}</nav><div class="sidebar-footer"><span class="source-dot"></span> Evidence-first operations<a href="https://github.com/9059Rohith/settlement-recon">Source repository {icon("external", 14)}</a></div></aside><div class="app-shell"><header class="topbar"><div class="breadcrumb"><button id="nav-toggle" class="icon-button" aria-label="Toggle navigation" aria-controls="workspace-navigation" aria-expanded="false">{icon("menu")}</button><span>Operations</span><span class="slash">/</span><strong>{"Overview" if page == "overview" else html.escape(title)}</strong></div><div class="topbar-actions"><button class="command-trigger" id="open-command">{icon("search", 18)}<span>Find a page</span><kbd>⌘ K</kbd></button><button id="connect" class="primary compact">{icon("user", 17)}<span>Operator access</span></button></div></header><main id="main-content" tabindex="-1"><section class="heading"><div><h1>{html.escape(title)}</h1><p>{html.escape(subtitle)}</p></div>{link("agent", "Ask the investigator", primary=True) if page == "overview" else ""}</section><div id="notice" role="status" aria-live="polite"></div><div class="page-content">{content}</div><footer class="page-footer"><span>Reference rates are informational, not executable prices.</span><a href="/workspace/provenance">Inspect the source {icon("arrow", 14)}</a></footer></main></div><dialog id="session"><form id="session-form"><div class="dialog-heading"><h2>Operator access</h2><button type="button" id="close-session" class="icon-button" aria-label="Close operator access">{icon("close")}</button></div><p>Public investigations need no token. Enter an existing reader or writer token only for protected operations.</p><label>Bearer token<input name="token" type="password" minlength="32" autocomplete="off" required></label><p class="muted">Sent only to this origin and held in this page's memory.</p><button class="primary">Connect operator</button></form></dialog><dialog id="command-palette"><div class="command-input">{icon("search")}<label class="sr-only" for="command-search">Find a workspace page</label><input id="command-search" placeholder="Where would you like to go?" autocomplete="off"><button class="icon-button" id="close-command" aria-label="Close page search">{icon("close")}</button></div><nav id="command-results" aria-label="Page search results">{palette}</nav><p class="command-hint">Use ↑ ↓ to choose · Enter to open · Esc to close</p></dialog><dialog id="currency-detail" class="detail-drawer"><div class="dialog-heading"><h2 id="detail-title">Currency evidence</h2><button class="icon-button" id="close-detail" aria-label="Close currency evidence">{icon("close")}</button></div><div id="detail-content"></div></dialog><script src="/workspace/assets/format.js" defer></script><script src="/workspace/assets/app.js" defer></script></body></html>'''
