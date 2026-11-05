"use strict";
let token = "";
const page = document.body.dataset.page;
const $ = (selector) => document.querySelector(selector);
const state = { snapshot: null, sort: "currency", direction: 1 };
const currencyNames = {
  USD: "US Dollar",
  GBP: "Pound Sterling",
  INR: "Indian Rupee",
  JPY: "Japanese Yen",
  CHF: "Swiss Franc",
  EUR: "Euro",
  AUD: "Australian Dollar",
  BRL: "Brazilian Real",
  CAD: "Canadian Dollar",
  CNY: "Chinese Yuan",
  CZK: "Czech Koruna",
  DKK: "Danish Krone",
  HKD: "Hong Kong Dollar",
  HUF: "Hungarian Forint",
  IDR: "Indonesian Rupiah",
  ILS: "Israeli Shekel",
  ISK: "Icelandic Krona",
  KRW: "South Korean Won",
  MXN: "Mexican Peso",
  MYR: "Malaysian Ringgit",
  NOK: "Norwegian Krone",
  NZD: "New Zealand Dollar",
  PHP: "Philippine Peso",
  PLN: "Polish Zloty",
  RON: "Romanian Leu",
  SEK: "Swedish Krona",
  SGD: "Singapore Dollar",
  THB: "Thai Baht",
  TRY: "Turkish Lira",
  ZAR: "South African Rand",
};
function node(tag, className, text) {
  const n = document.createElement(tag);
  if (className) n.className = className;
  if (text !== undefined) n.textContent = String(text);
  return n;
}
function notice(text, tone = "info") {
  const el = $("#notice");
  el.textContent = text;
  el.dataset.tone = tone;
}
function date(value, withTime = false) {
  if (!value) return "Not captured";
  const d = new Date(value.length === 10 ? value + "T00:00:00Z" : value);
  return Number.isNaN(d.getTime())
    ? "Unknown date"
    : new Intl.DateTimeFormat("en-GB", {
        day: "numeric",
        month: "short",
        year: "numeric",
        timeZone: "UTC",
        ...(withTime ? { hour: "2-digit", minute: "2-digit" } : {}),
      }).format(d) + (withTime ? " UTC" : "");
}
async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      ...(token ? { Authorization: "Bearer " + token } : {}),
      ...(options.headers || {}),
    },
  });
  let data;
  try {
    data = await response.json();
  } catch {
    throw Error("The service returned an unreadable response. Please retry.");
  }
  if (!response.ok) {
    const error = Error(
      typeof data.detail === "string"
        ? data.detail
        : "The service could not complete this request.",
    );
    error.retryAfter = Number(response.headers.get("Retry-After")) || 0;
    error.status = response.status;
    throw error;
  }
  return data;
}
function safeLink(label, href) {
  try {
    const url = new URL(href, location.origin);
    if (
      !["https:", "http:"].includes(url.protocol) ||
      (url.protocol === "http:" && url.origin !== location.origin)
    )
      return node("span", "", label);
    const a = node("a", "", label);
    a.href = url.href;
    if (url.origin !== location.origin) {
      a.target = "_blank";
      a.rel = "noopener noreferrer";
    }
    return a;
  } catch {
    return node("span", "", label);
  }
}
function inlineText(parent, value) {
  function appendTokens(destination, tokens) {
    for (const token of tokens) {
      if (token.type === "strong") {
        const strong = node("strong");
        appendTokens(strong, token.children);
        destination.append(strong);
      } else if (token.type === "code")
        destination.append(node("code", "", token.value));
      else if (token.type === "link")
        destination.append(safeLink(token.value, token.href));
      else destination.append(document.createTextNode(token.value));
    }
  }
  appendTokens(parent, ReconFormat.inlineTokens(value));
}

function prose(text) {
  const el = node("div", "answer-prose");
  let list = null;
  for (const line of String(text).slice(0, 20000).split("\n")) {
    const trimmed = line.trim();
    if (!trimmed) {
      list = null;
      continue;
    }
    if (/^[-*]\s/.test(trimmed)) {
      if (!list) {
        list = node("ul");
        el.append(list);
      }
      const item = node("li");
      inlineText(item, trimmed.slice(2));
      list.append(item);
    } else {
      list = null;
      const heading = /^#{1,3}\s/.test(trimmed);
      const p = node(heading ? "h3" : "p");
      inlineText(p, trimmed.replace(/^#{1,3}\s/, ""));
      el.append(p);
    }
  }
  return el;
}
function show(id, data) {
  const el = $(id);
  if (!el) return;
  el.replaceChildren();
  if (id === "#answer" && typeof data.answer === "string") {
    el.append(
      node("h2", "", "Investigation findings"),
      prose(data.answer),
      node(
        "p",
        "answer-meta",
        `${data.provider} · ${data.model} · ${(data.tools || []).length} evidence tools`,
      ),
    );
    el.append(node("h3", "evidence-heading", "Follow the evidence"));
    for (const tool of data.tools || []) {
      const detail = node("details");
      detail.append(
        node("summary", "", tool.name),
        node("pre", "", JSON.stringify(tool.evidence, null, 2)),
      );
      el.append(detail);
    }
    return;
  }
  el.append(node("pre", "", JSON.stringify(data, null, 2)));
}
async function copy(text, button) {
  try {
    await navigator.clipboard.writeText(String(text));
    button?.classList.add("copy-feedback");
    notice("Source evidence copied.", "success");
    setTimeout(() => button?.classList.remove("copy-feedback"), 1500);
  } catch {
    notice(
      "Clipboard is unavailable in this browser. Select the source evidence to copy it.",
      "error",
    );
  }
}
function flag(code) {
  const el = node("span", "flag");
  el.setAttribute("aria-hidden", "true");
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 28 20");
  const shapes = {
    USD: '<rect width="28" height="20" fill="white"/><path stroke="#e34355" stroke-width="2" d="M0 2h28M0 6h28M0 10h28M0 14h28M0 18h28"/><path fill="#214982" d="M0 0h13v11H0z"/>',
    GBP: '<rect width="28" height="20" fill="#19487e"/><path stroke="white" stroke-width="5" d="m0 0 28 20M28 0 0 20"/><path stroke="#d93d52" stroke-width="2" d="m0 0 28 20M28 0 0 20"/><path stroke="white" stroke-width="7" d="M14 0v20M0 10h28"/><path stroke="#d93d52" stroke-width="4" d="M14 0v20M0 10h28"/>',
    INR: '<path fill="#f19b40" d="M0 0h28v7H0z"/><path fill="white" d="M0 7h28v6H0z"/><path fill="#159d64" d="M0 13h28v7H0z"/><circle cx="14" cy="10" r="2.5" fill="none" stroke="#31579a"/>',
    JPY: '<rect width="28" height="20" fill="white"/><circle cx="14" cy="10" r="5" fill="#d53750"/>',
    CHF: '<rect width="28" height="20" fill="#e83f47"/><path fill="white" d="M12 4h4v4h4v4h-4v4h-4v-4H8V8h4z"/>',
  };
  if (shapes[code]) {
    svg.innerHTML = shapes[code];
    el.append(svg);
  } else el.textContent = code.slice(0, 2);
  return el;
}
function evidenceList(entries) {
  const dl = node("dl", "evidence-list");
  for (const [label, value] of entries) {
    dl.append(node("dt", "", label));
    const dd = node("dd");
    dd.append(
      value instanceof Node
        ? value
        : node(
            label.includes("Digest") ? "code" : "span",
            "",
            value ?? "Unavailable",
          ),
    );
    dl.append(dd);
  }
  return dl;
}
function openCurrency(code) {
  const d = state.snapshot;
  if (!d?.observation?.rates[code]) return;
  const container = $("#detail-content");
  container.replaceChildren();
  const identity = node("div", "drawer-currency");
  const names = node("div");
  names.append(
    node("strong", "", code),
    node("p", "", currencyNames[code] || code),
  );
  identity.append(flag(code), names);
  container.append(
    identity,
    node("div", "rate-hero", String(d.observation.rates[code])),
    node("p", "", "Reference units per 1 EUR"),
    evidenceList([
      ["Observation", date(d.observation.date)],
      ["Captured", date(d.captured_at, true)],
      ["Digest", d.digest],
      ["Source", safeLink("Frankfurter / ECB", d.source)],
    ]),
  );
  const use = node("a", "button primary", "Use in calculator");
  use.href = "/workspace/converter?to=" + encodeURIComponent(code);
  container.append(use);
  $("#detail-title").textContent = "Currency evidence";
  $("#currency-detail").showModal();
}
function renderRates() {
  const container = $("#rates");
  if (!container) return;
  const d = state.snapshot;
  if (d?.status !== "captured") {
    container.replaceChildren(
      node(
        "div",
        "empty",
        "No reference observation has been captured. An operator can synchronize the real provider.",
      ),
    );
    return;
  }
  const query = ($("#currency-search")?.value || "").trim().toLowerCase();
  let rows = Object.entries(d.observation.rates).map(([currency, rate]) => ({
    currency,
    rate,
  }));
  const total = rows.length;
  rows = rows.filter((r) =>
    `${r.currency} ${currencyNames[r.currency] || ""}`
      .toLowerCase()
      .includes(query),
  );
  if (page === "overview" && !query) {
    const order = ["USD", "GBP", "INR", "JPY", "CHF"];
    rows = order
      .map((code) => rows.find((r) => r.currency === code))
      .filter(Boolean);
  } else
    rows.sort(
      (a, b) =>
        state.direction *
        (state.sort === "rate"
          ? Number(a.rate) - Number(b.rate)
          : a.currency.localeCompare(b.currency)),
    );
  const wrapper = node("div", "table-scroll"),
    table = node("table");
  table.setAttribute("aria-label", "Captured currency reference rates");
  const header = table.createTHead().insertRow();
  for (const [label, key] of [
    ["Currency", "currency"],
    ["Reference rate", "rate"],
    ["Use", null],
  ]) {
    const th = node("th");
    if (key) {
      const button = node("button", "sort-button", label);
      button.type = "button";
      button.addEventListener("click", () => {
        state.direction = state.sort === key ? -state.direction : 1;
        state.sort = key;
        renderRates();
      });
      th.append(button);
      th.setAttribute(
        "aria-sort",
        state.sort === key
          ? state.direction > 0
            ? "ascending"
            : "descending"
          : "none",
      );
    } else th.textContent = label;
    header.append(th);
  }
  const body = table.createTBody();
  for (const row of rows) {
    const tr = body.insertRow(),
      identity = node("div", "currency-cell"),
      labels = node("div");
    const button = node("button", "currency-code", row.currency);
    button.type = "button";
    button.setAttribute("aria-label", "Inspect " + row.currency + " evidence");
    button.onclick = () => openCurrency(row.currency);
    labels.append(
      button,
      node(
        "span",
        "currency-name",
        currencyNames[row.currency] || "Reference currency",
      ),
    );
    identity.append(flag(row.currency), labels);
    tr.insertCell().append(identity);
    tr.insertCell().append(node("span", "rate-value", String(row.rate)));
    const action = node("a", "button table-action", "Calculate");
    action.href = "/workspace/converter?to=" + encodeURIComponent(row.currency);
    action.setAttribute("aria-label", "Calculate with " + row.currency);
    tr.insertCell().append(action);
  }
  wrapper.append(table);
  container.replaceChildren(
    rows.length
      ? wrapper
      : node("div", "empty", "No currencies match your search."),
  );
  if ($("#currency-count"))
    $("#currency-count").textContent =
      `${rows.length} of ${total} observations`;
}
async function loadReference() {
  const d = await api("/workspace/api/rates");
  state.snapshot = d;
  renderRates();
  if (d.status !== "captured") return;
  const set = (selector, text) => {
    if ($(selector)) $(selector).textContent = text;
  };
  set("#metric-currencies", Object.keys(d.observation.rates).length);
  set("#metric-base", d.observation.base);
  set("#metric-date", date(d.observation.date));
  set("#capture-date", date(d.captured_at));
  set("#source-digest", d.digest.slice(0, 10) + "…" + d.digest.slice(-7));
  set(
    "#rate-observation",
    "Observed " +
      date(d.observation.date) +
      " · captured " +
      date(d.captured_at, true),
  );
  if ($("#copy-digest"))
    $("#copy-digest").onclick = () => copy(d.digest, $("#copy-digest"));
  if ($("#provenance")) {
    $("#provenance").replaceChildren(
      evidenceList([
        ["Provider", safeLink("Frankfurter reference API", d.source)],
        ["Attribution", safeLink("European Central Bank", d.attribution)],
        ["Base currency", d.observation.base],
        ["Observation date", date(d.observation.date)],
        ["Capture time", date(d.captured_at, true)],
        ["SHA-256 Digest", d.digest],
        ["Purpose", d.purpose],
      ]),
    );
    const button = node("button", "secondary", "Copy source digest");
    button.onclick = () => copy(d.digest, button);
    $("#provenance").append(button);
  }
  if ($("#convert")) {
    const codes = ["EUR", ...Object.keys(d.observation.rates).sort()];
    for (const name of ["source", "target"]) {
      const select = $(`#convert [name=${name}]`);
      select.replaceChildren(
        ...codes.map((code) => {
          const option = node(
            "option",
            "",
            code + " · " + (currencyNames[code] || code),
          );
          option.value = code;
          return option;
        }),
      );
      const desired =
        name === "source"
          ? "EUR"
          : new URLSearchParams(location.search).get("to") || "USD";
      select.value = codes.includes(desired) ? desired : "USD";
    }
  }
}
function dataTable(id, rows) {
  const container = $(id);
  if (!container) return;
  if (!rows.length) {
    notice("No authorized records are available in this view.", "info");
    return;
  }
  const panel = node("div", "data-panel"),
    tools = node("div", "record-tools"),
    search = node("input");
  search.type = "search";
  search.placeholder = "Filter records";
  search.setAttribute("aria-label", "Filter records");
  const count = node("span");
  tools.append(search, count);
  panel.append(tools);
  const wrap = node("div", "table-scroll");
  panel.append(wrap);
  container.replaceChildren(panel);
  const cols = Object.keys(rows[0]);
  const update = () => {
    const q = search.value.toLowerCase();
    const filtered = rows.filter((r) =>
      JSON.stringify(r).toLowerCase().includes(q),
    );
    count.textContent = filtered.length + " records";
    const table = node("table"),
      head = table.createTHead().insertRow();
    for (const key of cols)
      head.append(node("th", "", key.replaceAll("_", " ")));
    const body = table.createTBody();
    for (const row of filtered.slice(0, 200)) {
      const tr = body.insertRow();
      for (const key of cols)
        tr.insertCell().textContent =
          typeof row[key] === "object"
            ? JSON.stringify(row[key])
            : String(row[key] ?? "");
    }
    wrap.replaceChildren(table);
  };
  search.oninput = update;
  update();
}
async function ledger() {
  if (!token) {
    notice(
      "Financial records require an operator session. Public reference data and AI investigations remain open.",
    );
    return;
  }
  const path =
    page === "payments"
      ? "payments"
      : page === "settlements"
        ? "settlements"
        : "reconciliation";
  const rows = await api("/workspace/api/" + path);
  dataTable(
    "#ledger",
    rows.filter(
      (r) =>
        !String(r.payment_id).startsWith("demo-") &&
        (page !== "exceptions" || r.status !== "matched"),
    ),
  );
}
function integrationStatus(data) {
  const container = $("#status");
  if (!container) return;
  const labels = {
    model_configured: "AI provider",
    ai_provider: "Model provider",
    ai_model: "Model",
    ai_data_scope: "Model data scope",
    public_demo: "Public investigator",
    demo_limiter_storage: "Budget storage",
    demo_client_identity: "Visitor protection",
    demo_limits: "Public allowance",
    rate_provider: "Reference source",
    reference_data: "Observation state",
    payment_source: "Payment source",
    cloud: "Infrastructure",
    agent_scope: "Agent permissions",
  };
  const dl = node("dl", "integrations");
  for (const [key, value] of Object.entries(data)) {
    dl.append(node("dt", "", labels[key] || key.replaceAll("_", " ")));
    const dd = node("dd");
    dd.textContent =
      typeof value === "boolean"
        ? value
          ? "Connected"
          : "Not configured"
        : String(value ?? "Not configured");
    dl.append(dd);
  }
  container.replaceChildren(dl);
}
async function load() {
  try {
    if ($("#rates") || $("#provenance") || $("#convert")) await loadReference();
    if ($("#status") || $("#agent-provider")) {
      const status = await api("/workspace/api/status");
      integrationStatus(status);
      if ($("#agent-provider"))
        $("#agent-provider").textContent = status.model_configured
          ? `${status.ai_provider} · ${status.ai_model}`
          : "Free model provider is not configured";
    }
    if ($("#ledger") && token) await ledger();
    if ($("#batches") && token) {
      const rows = (await api("/workspace/api/batches")).filter(
        (r) => r.source !== "portfolio-synthetic-v1",
      );
      dataTable("#batches", rows);
      for (const row of rows.slice(0, 20)) {
        const button = node("button", "secondary", "Verify " + row.batch_id);
        button.onclick = async () => {
          try {
            show(
              "#batches",
              await api(
                "/v1/batches/" + encodeURIComponent(row.batch_id) + "/verify",
              ),
            );
            notice("Archive verification complete.", "success");
          } catch (error) {
            notice(error.message, "error");
          }
        };
        $("#batches").append(button);
      }
    }
  } catch (error) {
    notice(error.message, "error");
  }
}
function connect() {
  $("#session").showModal();
}
$("#connect").onclick = () => {
  if (token) {
    token = "";
    location.reload();
  } else connect();
};
document
  .querySelectorAll("[data-connect]")
  .forEach((button) => (button.onclick = connect));
$("#close-session").onclick = () => $("#session").close();
$("#session-form").onsubmit = async (event) => {
  event.preventDefault();
  token = new FormData(event.target).get("token").trim();
  event.target.reset();
  $("#session").close();
  $("#connect").textContent = "Disconnect operator";
  notice("Operator token held in memory for this page only.", "success");
  await load();
};
$("#nav-toggle").onclick = () => {
  const open = $("#workspace-navigation").classList.toggle("is-open");
  $("#nav-toggle").setAttribute("aria-expanded", String(open));
};
document.addEventListener("click", (event) => {
  if (
    !event.target.closest(".sidebar") &&
    !event.target.closest("#nav-toggle")
  ) {
    $("#workspace-navigation").classList.remove("is-open");
    $("#nav-toggle").setAttribute("aria-expanded", "false");
  }
});
const mobileNavigation = matchMedia("(max-width:700px)");
function syncNavigationAccess() {
  const side = $("#workspace-navigation");
  side.inert = mobileNavigation.matches && !side.classList.contains("is-open");
}
mobileNavigation.addEventListener("change", syncNavigationAccess);
const navObserver = new MutationObserver(syncNavigationAccess);
navObserver.observe($("#workspace-navigation"), {
  attributes: true,
  attributeFilter: ["class"],
});
syncNavigationAccess();
const palette = $("#command-palette"),
  commandSearch = $("#command-search");
let selection = 0;
function results() {
  return [...$("#command-results").querySelectorAll("a:not([hidden])")];
}
function selectResult() {
  const links = results();
  if (!links.length) return;
  selection = (selection + links.length) % links.length;
  links.forEach((link, i) =>
    link.classList.toggle("is-selected", i === selection),
  );
}
function openCommand() {
  palette.showModal();
  commandSearch.value = "";
  $("#command-results")
    .querySelectorAll("a")
    .forEach((link) => (link.hidden = false));
  selection = 0;
  selectResult();
  commandSearch.focus();
}
$("#open-command").onclick = openCommand;
$("#close-command").onclick = () => palette.close();
commandSearch.oninput = () => {
  const q = commandSearch.value.toLowerCase().trim();
  $("#command-results")
    .querySelectorAll("a")
    .forEach((link) => (link.hidden = !link.dataset.keywords.includes(q)));
  selection = 0;
  selectResult();
};
commandSearch.onkeydown = (event) => {
  if (event.key === "ArrowDown" || event.key === "ArrowUp") {
    event.preventDefault();
    selection += event.key === "ArrowDown" ? 1 : -1;
    selectResult();
  }
  if (event.key === "Enter") {
    event.preventDefault();
    results()[selection]?.click();
  }
};
document.addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
    event.preventDefault();
    palette.open ? palette.close() : openCommand();
  }
  if (event.key === "Escape") {
    $("#workspace-navigation").classList.remove("is-open");
    $("#nav-toggle").setAttribute("aria-expanded", "false");
  }
});
$("#close-detail").onclick = () => $("#currency-detail").close();
if ($("#currency-search")) $("#currency-search").oninput = renderRates;
if ($("#sync"))
  $("#sync").onclick = async (event) => {
    if (!token) {
      connect();
      return;
    }
    event.currentTarget.disabled = true;
    try {
      await api("/workspace/api/rates/sync", { method: "POST" });
      await loadReference();
      notice("Provider observation captured with source evidence.", "success");
    } catch (error) {
      notice(error.message, "error");
    } finally {
      event.target.disabled = false;
    }
  };
if ($("#reconcile"))
  $("#reconcile").onclick = () => {
    if (!token) {
      connect();
      return;
    }
    ledger().catch((error) => notice(error.message, "error"));
  };
if ($("#readiness"))
  $("#readiness").onclick = async () => {
    if (!token) {
      connect();
      return;
    }
    try {
      show("#ready", await api("/readyz"));
    } catch (error) {
      notice(error.message, "error");
    }
  };
if ($("#swap-currencies"))
  $("#swap-currencies").onclick = () => {
    const source = $("#convert [name=source]"),
      target = $("#convert [name=target]");
    [source.value, target.value] = [target.value, source.value];
    $("#conversion").replaceChildren(
      node("p", "", "Currencies changed. Calculate to inspect the new result."),
    );
  };
if ($("#convert"))
  $("#convert").onsubmit = async (event) => {
    event.preventDefault();
    const button =
      event.target.querySelector("button[type=submit]") ||
      event.target.querySelector("button.primary");
    button.disabled = true;
    try {
      const data = await api("/workspace/api/convert", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(Object.fromEntries(new FormData(event.target))),
      });
      const out = $("#conversion");
      out.replaceChildren(
        node("p", "", `${data.amount} ${data.source} equals`),
      );
      const value = node(
        "div",
        "conversion-result",
        ReconFormat.formatExactDecimal(data.result),
      );
      value.append(node("span", "", data.target));
      out.append(
        value,
        node("p", "", `1 ${data.source} = ${data.cross_rate} ${data.target}`),
      );
      const metadata = node("div", "result-metadata");
      metadata.append(
        node("span", "", "Observation: " + date(data.observation_date)),
        node("code", "", "Exact result: " + data.result),
        node("code", "", "Source: " + data.digest),
      );
      out.append(metadata);
      notice("Calculated from the captured reference observation.", "success");
    } catch (error) {
      notice(error.message, "error");
    } finally {
      button.disabled = false;
    }
  };
if ($("#ingest"))
  $("#ingest").onsubmit = async (event) => {
    event.preventDefault();
    if (!token) {
      connect();
      return;
    }
    const data = new FormData(event.target),
      file = data.get("file");
    if (!file || file.size > 2000000) {
      notice("Source exceeds the 2 MB limit.", "error");
      return;
    }
    const button = event.target.querySelector("button");
    button.disabled = true;
    try {
      const result = await api(
        "/v1/ingest/" +
          encodeURIComponent(data.get("kind")) +
          "?source=" +
          encodeURIComponent("operator:" + data.get("source")),
        {
          method: "POST",
          headers: {
            "Content-Type":
              data.get("kind") === "payments" ? "application/json" : "text/csv",
          },
          body: file,
        },
      );
      show("#receipt", result);
      notice("Source processed. Inspect the batch receipt below.", "success");
    } catch (error) {
      notice(error.message, "error");
    } finally {
      button.disabled = false;
    }
  };
document.querySelectorAll("[data-prompt]").forEach(
  (button) =>
    (button.onclick = () => {
      $("#agent textarea").value = button.dataset.prompt;
      $("#agent textarea").focus();
    }),
);
if ($("#agent"))
  $("#agent").onsubmit = async (event) => {
    event.preventDefault();
    const button = event.target.querySelector("button[type=submit]");
    const original = button.textContent;
    button.disabled = true;
    const answer = $("#answer");
    answer.replaceChildren(
      node(
        "div",
        "loading-answer",
        "Reading the source. Following the evidence.",
      ),
    );
    notice("Investigation in progress.");
    let cooldown = 0;
    try {
      const result = await api("/workspace/api/agent/demo", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: new FormData(event.target).get("question"),
        }),
      });
      show("#answer", result);
      notice(
        "Investigation complete. Inspect the source evidence below.",
        "success",
      );
    } catch (error) {
      answer.replaceChildren();
      notice(error.message, "error");
      cooldown = error.retryAfter;
      if (cooldown) {
        button.textContent = `Try again in ${cooldown}s`;
        const interval = setInterval(() => {
          cooldown--;
          button.textContent = `Try again in ${cooldown}s`;
          if (cooldown <= 0) {
            clearInterval(interval);
            button.textContent = original;
            button.disabled = false;
            notice(
              "The cooldown has ended. You can try the public investigator again.",
            );
          }
        }, 1000);
      }
    } finally {
      if (!cooldown) button.disabled = false;
    }
  };
if (
  "IntersectionObserver" in window &&
  !CSS.supports("animation-timeline: view()") &&
  matchMedia("(prefers-reduced-motion: no-preference)").matches
) {
  const atlasObserver = new IntersectionObserver(
    (entries, observer) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        entry.target.classList.add("atlas-revealed");
        observer.unobserve(entry.target);
      }
    },
    { threshold: 0.23 },
  );
  document.querySelectorAll("[data-atlas-reveal]").forEach((plate) => {
    atlasObserver.observe(plate);
  });
}
load();
