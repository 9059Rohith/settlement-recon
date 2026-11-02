"use strict";
// Page-local assumptions only. Exact money arithmetic belongs to the server.
(async function treasuryWorkbench() {
  const form = document.querySelector("#stress-form");
  if (!form) return;
  let codes = [],
    nextId = 0,
    report = null,
    revision = 0;
  const positions = document.querySelector("#stress-positions");
  const scenarios = document.querySelector("#stress-shocks");
  const output = document.querySelector("#stress-output");
  const currency = document.querySelector("#stress-currency");
  const run = document.querySelector("#run-stress");
  const limit = document.querySelector("#stress-limit");
  const firstName = document.querySelector("#stress-name");
  // Each scenario owns its name; use the initial field in its first card.
  firstName.closest("label").remove();
  const make = (tag, cls, text) => {
    const element = document.createElement(tag);
    if (cls) element.className = cls;
    if (text !== undefined) element.textContent = String(text);
    return element;
  };
  function input(label, options = {}) {
    const wrapper = make("label", "", label);
    const field = make(options.tag || "input");
    Object.assign(field, options);
    wrapper.append(field);
    return { wrapper, field };
  }
  function select(label, values, selected) {
    const wrapper = make("label", "", label),
      field = make("select");
    for (const [value, text] of values) {
      const option = make("option", "", text);
      option.value = value;
      field.append(option);
    }
    if (selected) field.value = selected;
    wrapper.append(field);
    return { wrapper, field };
  }
  function removeButton(label, target) {
    const button = make("button", "secondary stress-remove", "Remove");
    button.type = "button";
    button.setAttribute("aria-label", label);
    button.onclick = () => {
      target.remove();
      invalidate();
    };
    return button;
  }
  function invalidate() {
    revision++;
    if (!report) return;
    report = null;
    output.replaceChildren(
      make(
        "div",
        "stress-empty",
        "Assumptions changed. Analyze again to generate a report for this draft.",
      ),
    );
  }
  function addPosition() {
    if (positions.children.length >= 50)
      return notice("Maximum 50 cash flows.", "error");
    const id = "flow_" + ++nextId,
      row = make("div", "stress-position");
    row.dataset.id = id;
    const code = select(
      "Currency",
      codes.map((c) => [c, c]),
      "USD",
    );
    code.field.dataset.field = "currency";
    const direction = select("Direction", [
      ["receivable", "Receivable"],
      ["payable", "Payable"],
    ]);
    direction.field.dataset.field = "direction";
    const amount = input("Amount", {
      required: true,
      inputMode: "decimal",
      placeholder: "Enter amount",
      maxLength: 20,
    });
    amount.field.dataset.field = "amount";
    row.append(
      make("span", "stress-flow-id", id.replace("flow_", "#")),
      code.wrapper,
      direction.wrapper,
      amount.wrapper,
      removeButton("Remove cash flow " + nextId, row),
    );
    positions.append(row);
    invalidate();
  }
  function addShock(card) {
    const list = card.querySelector(".stress-shock-list");
    if (list.children.length >= 30)
      return notice("Maximum 30 shocks per scenario.", "error");
    const row = make("div", "stress-shock-row");
    const available = codes.filter((c) => c !== currency.value);
    const used = Array.from(list.querySelectorAll("select")).map(
      (s) => s.value,
    );
    const code = select(
      "Shock currency",
      available.map((c) => [c, c]),
      (available.includes("USD") && !used.includes("USD")
        ? "USD"
        : available.find((c) => !used.includes(c))) || available[0],
    );
    const shock = input("Value change (bps)", {
      required: true,
      type: "number",
      min: -9000,
      max: 9000,
      step: 1,
      placeholder: "e.g. -500",
    });
    row.append(
      code.wrapper,
      shock.wrapper,
      removeButton("Remove currency shock", row),
    );
    list.append(row);
    invalidate();
  }
  function addScenario() {
    if (scenarios.children.length >= 8)
      return notice("Maximum eight scenarios.", "error");
    const card = make("fieldset", "stress-scenario");
    const name = input("Scenario name", {
      required: true,
      maxLength: 40,
      value: "Scenario " + (scenarios.children.length + 1),
    });
    const list = make("div", "stress-shock-list"),
      add = make("button", "secondary", "Add currency shock");
    add.type = "button";
    add.onclick = () => addShock(card);
    card.append(name.wrapper, list, add, removeButton("Remove scenario", card));
    scenarios.append(card);
    addShock(card);
    invalidate();
  }
  function table(headers, rows) {
    const scroller = make("div", "stress-table-scroll"),
      t = make("table", "stress-table"),
      head = make("thead"),
      tr = make("tr");
    for (const title of headers) {
      const th = make("th", "", title);
      th.scope = "col";
      tr.append(th);
    }
    head.append(tr);
    const body = make("tbody");
    for (const values of rows) {
      const r = make("tr");
      for (const value of values) r.append(make("td", "", value));
      body.append(r);
    }
    t.append(head, body);
    scroller.append(t);
    return scroller;
  }
  function render(result) {
    const header = make("div", "panel-heading"),
      title = make("div"),
      download = make("button", "secondary", "Download evidence JSON");
    title.append(
      make("h2", "", "03 / Your exposure, explained"),
      make(
        "p",
        "",
        "Observed " +
          result.observation_date +
          " · " +
          result.position_count +
          " supplied cash flows · " +
          result.reporting_currency +
          " reporting units",
      ),
    );
    download.type = "button";
    download.onclick = () => {
      const blob = new Blob([JSON.stringify(result, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob),
        a = make("a");
      a.href = url;
      a.download =
        "settlement-fx-stress-" + result.report_digest.slice(0, 12) + ".json";
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    };
    header.append(title, download);
    const metrics = make("div", "metrics-band");
    for (const [label, value] of [
      ["Gross cash flows", result.baseline.gross],
      ["Net exposure", result.baseline.net],
      ["Worst scenario loss", result.worst_loss],
      [
        "Baseline net limit",
        result.baseline.limit_breached
          ? "Breached"
          : result.baseline.net_limit === null
            ? "Not set"
            : "Within limit",
      ],
    ]) {
      const metric = make("div");
      metric.append(
        make(
          "strong",
          "stress-number",
          /^-?\d+(\.\d+)?$/.test(value)
            ? ReconFormat.formatCompactDecimal(value)
            : value,
        ),
        make("span", "", label),
      );
      metrics.append(metric);
    }
    const exposure = make("section", "panel"),
      bars = make("div", "stress-bars");
    exposure.append(
      make("h3", "", "Currency concentration / gross cash flows"),
    );
    for (const row of result.exposures) {
      const bar = make("div", "stress-bar"),
        track = make("meter");
      track.min = 0;
      track.max = 1;
      track.value = Number(row.gross_share);
      track.setAttribute(
        "aria-label",
        row.currency + " share of gross cash flows",
      );
      bar.append(
        make("strong", "", row.currency),
        track,
        make("span", "", (Number(row.gross_share) * 100).toFixed(1) + "%"),
      );
      bars.append(bar);
    }
    exposure.append(
      bars,
      table(
        [
          "Currency",
          "Receivable",
          "Payable",
          "Net native",
          "Net " + result.reporting_currency,
        ],
        result.exposures.map((r) => [
          r.currency,
          r.receivable_native,
          r.payable_native,
          r.net_native,
          r.net_reporting,
        ]),
      ),
    );
    const scenariosPanel = make("section", "panel");
    scenariosPanel.append(
      make("h3", "", "Scenario sensitivity / independent hypothetical cases"),
    );
    scenariosPanel.append(
      table(
        ["Scenario", "Net value", "Change", "Net limit"],
        result.scenarios.map((r) => [
          r.name,
          r.net,
          r.delta,
          r.limit_breached
            ? "Breached"
            : result.baseline.net_limit === null
              ? "Not set"
              : "Within limit",
        ]),
      ),
    );
    for (const row of result.scenarios) {
      const detail = make("details", "stress-contributions");
      detail.append(
        make("summary", "", row.name + " / currency contributions"),
        table(
          ["Currency", "Shock (bps)", "Before", "After", "Change"],
          row.contributions.map((c) => [
            c.currency,
            c.shock_bps,
            c.baseline,
            c.stressed,
            c.delta,
          ]),
        ),
      );
      scenariosPanel.append(detail);
    }
    const evidence = make("section", "panel stress-evidence");
    evidence.append(make("h3", "", "A reproducible decision trail"));
    for (const [label, value] of [
      ["Source digest", result.source.digest],
      ["Input digest", result.request_digest],
      ["Report digest", result.report_digest],
      ["Captured", result.source.captured_at],
    ]) {
      const line = make("p");
      line.append(make("strong", "", label + " "), make("code", "", value));
      evidence.append(line);
    }
    evidence.append(
      make(
        "p",
        "",
        "Values above truncate after six decimals (…). Full 50-significant-digit strings and your assumptions are in the download. Exact rational valuation; recurring output is rounded. Hashes identify content, not authorship. No probability, fees, correlation or liquidity model is implied.",
      ),
    );
    output.replaceChildren(header, metrics, exposure, scenariosPanel, evidence);
  }
  form.addEventListener("input", invalidate);
  currency.onchange = () => {
    for (const card of scenarios.children)
      for (const row of card.querySelectorAll(".stress-shock-row")) {
        const code = row.querySelector("select"),
          old = code.value;
        code.replaceChildren(
          ...codes
            .filter((c) => c !== currency.value)
            .map((c) => {
              const option = make("option", "", c);
              option.value = c;
              return option;
            }),
        );
        if (old !== currency.value) code.value = old;
      }
    invalidate();
  };
  document.querySelector("#add-position").onclick = addPosition;
  document.querySelector("#add-shock").textContent = "Add scenario";
  document.querySelector("#add-shock").onclick = addScenario;
  form.onsubmit = async (event) => {
    event.preventDefault();
    run.disabled = true;
    run.textContent = "Analyzing evidence…";
    const submittedRevision = revision;
    const controls = Array.from(form.elements).filter(
      (element) => element !== run,
    );
    const disabledStates = controls.map((element) => element.disabled);
    controls.forEach((element) => {
      element.disabled = true;
    });
    form.setAttribute("aria-busy", "true");
    try {
      const body = {
        reporting_currency: currency.value,
        positions: Array.from(positions.children).map((row) => ({
          id: row.dataset.id,
          currency: row.querySelector('[data-field="currency"]').value,
          direction: row.querySelector('[data-field="direction"]').value,
          amount: row.querySelector('[data-field="amount"]').value.trim(),
        })),
        scenarios: Array.from(scenarios.children).map((card) => {
          const shocks = {};
          for (const row of card.querySelectorAll(".stress-shock-row")) {
            const code = row.querySelector("select").value;
            if (Object.hasOwn(shocks, code))
              throw Error("Each currency may appear once per scenario.");
            shocks[code] = Number(row.querySelector("input").value);
          }
          return {
            name: card.querySelector("input").value.trim(),
            shocks_bps: shocks,
          };
        }),
      };
      if (limit.value.trim()) body.net_limit = limit.value.trim();
      const candidate = await api("/workspace/api/treasury", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (submittedRevision !== revision) {
        notice(
          "Assumptions changed while the analysis was running. Analyze this draft again.",
          "error",
        );
        return;
      }
      report = candidate;
      render(report);
      notice(
        "Analysis complete. These results describe your assumptions, not an actual ledger or future market outcome.",
        "success",
      );
    } catch (error) {
      notice(error.message, "error");
    } finally {
      controls.forEach((element, i) => {
        element.disabled = disabledStates[i];
      });
      form.removeAttribute("aria-busy");
      run.disabled = false;
      run.textContent = "Analyze exposure";
    }
  };
  run.disabled = true;
  try {
    await loadReference();
    if (state.snapshot?.status !== "captured")
      throw Error(
        "No captured reference observation. An operator must synchronize the source first.",
      );
    codes = ["EUR", ...Object.keys(state.snapshot.observation.rates).sort()];
    currency.replaceChildren(
      ...codes.map((c) => {
        const option = make("option", "", c);
        option.value = c;
        return option;
      }),
    );
    addPosition();
    addScenario();
    run.disabled = false;
  } catch (error) {
    notice(error.message, "error");
  }
})();
