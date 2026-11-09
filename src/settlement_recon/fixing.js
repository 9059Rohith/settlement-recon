"use strict";
(() => {
  const form = document.querySelector("#fixing-form");
  if (!form) return;
  const rows = document.querySelector("#fixing-inputs");
  const status = document.querySelector("#fixing-status");
  const output = document.querySelector("#fixing-output");
  const submit = form.querySelector("button[type=submit]");
  const add = document.querySelector("#fixing-add");
  const download = document.querySelector("#fixing-download");
  let currencies = [], lastDate = "", counter = 0, latest = null, revision = 0;
  function invalidate() {
    revision += 1; latest = null; output.hidden = true; download.disabled = true;
    status.textContent = "Inputs changed. Value the current records to generate new evidence.";
  }
  form.addEventListener("input", invalidate);
  form.addEventListener("change", invalidate);
  const make = (tag, text) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    return node;
  };
  function addRow() {
    if (rows.children.length >= 50) return;
    const fieldset = make("fieldset");
    fieldset.className = "fixing-record";
    fieldset.dataset.record = `record-${++counter}`;
    fieldset.append(make("legend", `Record ${counter} · your amount and date`));
    for (const [name, label, type] of [["currency", "Source currency", "select"],
      ["amount", "Amount in source currency", "text"], ["date", "Record date", "date"]]) {
      const group = make("label", label);
      const input = make(type === "select" ? "select" : "input");
      input.name = name; input.required = true;
      if (name === "currency") {
        currencies.forEach(code => input.add(new Option(code, code)));
        input.value = "USD";
      } else {
        input.type = type;
        if (name === "amount") {
          input.inputMode = "decimal"; input.maxLength = 20;
          input.placeholder = "Enter an actual amount";
          input.pattern = "(0|[1-9][0-9]{0,12})(\\.[0-9]{1,6})?";
        } else input.value = lastDate;
      }
      group.append(input); fieldset.append(group);
    }
    const remove = make("button", "Remove record");
    remove.className = "secondary"; remove.type = "button";
    remove.addEventListener("click", () => {
      invalidate();
      fieldset.remove(); add.disabled = false;
      if (!rows.children.length) addRow();
    });
    fieldset.append(remove); rows.append(fieldset);
    add.disabled = rows.children.length >= 50;
  }
  function render(data) {
    output.replaceChildren();
    output.append(make("h3", data.status === "complete" ? "Every record valued" : "Incomplete valuation — inspect blocked records"));
    output.append(make("p", data.complete_total !== null
      ? `Complete total: ${data.complete_total} ${data.target_currency}`
      : `${data.unvalued_count} records blocked. No complete total is published.`));
    output.append(make("p", `Valued subtotal: ${data.rounded_exact_subtotal} · Sum of rounded rows: ${data.sum_rounded_rows} · Rounding difference: ${data.rounding_difference} ${data.target_currency}`));
    const wrap = make("div"), table = make("table"), head = make("thead"), header = make("tr"), body = make("tbody");
    wrap.className = "history-table";
    ["Record", "Status", "Reference date", "Age (calendar days)", "Rounded value / reason"].forEach(label => {
      const th = make("th", label); th.scope = "col"; header.append(th);
    });
    head.append(header);
    data.records.forEach(record => {
      const tr = make("tr");
      [record.id, record.status, record.quote_date ?? (record.method === "identity" ? "No FX conversion" : "No prior quote"), record.quote_age_days ?? "—",
        record.rounded_value ?? record.reason].forEach(value => tr.append(make("td", String(value))));
      body.append(tr);
    });
    table.append(head, body); wrap.append(table); output.append(wrap);
    output.append(make("p", `Report SHA-256: ${data.report_sha256}`));
    output.append(make("p", `Source archive: ${data.source.first_date} to ${data.source.last_date}. Amounts are visitor-authored; ECB rates are reference observations, not executable prices. Calendar-day age and reporting precision are your explicit policies.`));
    output.hidden = false;
    download.disabled = false;
  }
  add.addEventListener("click", () => { invalidate(); addRow(); });
  form.addEventListener("submit", async event => {
    event.preventDefault(); submit.disabled = true; download.disabled = true;
    output.hidden = true; latest = null;
    status.textContent = "Checking dated quotes and exact rounding…";
    const requestedRevision = revision;
    const records = [...rows.children].map(row => ({id: row.dataset.record,
      ...Object.fromEntries([...row.querySelectorAll("input,select")].map(input => [input.name, input.value]))}));
    try {
      const body = {target_currency: form.elements.namedItem("target_currency").value,
        rounding_places: Number(form.elements.namedItem("rounding_places").value),
        max_quote_age_days: Number(form.elements.namedItem("max_quote_age_days").value), records};
      const response = await fetch("/workspace/api/fixing", {method: "POST",
        headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
      const data = await response.json();
      if (requestedRevision !== revision) return;
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Valuation rejected. Check the input policies.");
      latest = data; render(data);
      status.textContent = `${data.valued_count} valued · ${data.unvalued_count} blocked. Nothing saved or executed.`;
    } catch (error) { if (requestedRevision === revision) status.textContent = error.message; }
    finally { submit.disabled = false; }
  });
  download.addEventListener("click", () => {
    if (!latest) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(latest, null, 2)], {type: "application/json"}));
    const link = make("a"); link.href = url; link.download = "historical-fixing-evidence.json";
    link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  (async () => {
    try {
      const metadata = await api("/workspace/api/history/source");
      currencies = [...metadata.currencies].sort(); lastDate = metadata.last_date;
      const select = form.elements.namedItem("target_currency");
      currencies.forEach(code => select.add(new Option(code, code)));
      select.value = "INR"; addRow(); submit.disabled = false; add.disabled = false;
      status.textContent = `Archive ends ${lastDate}. Enter your own amounts. Dates after the archive may be stale; no future quotes or missing rates are invented.`;
    } catch (error) { status.textContent = error.message; }
  })();
})();
