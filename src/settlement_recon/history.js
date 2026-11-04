"use strict";
(() => {
  const form = document.querySelector("#history-form");
  const status = document.querySelector("#history-status");
  const result = document.querySelector("#history-result");
  const button = form.querySelector("button");
  const format = new Intl.NumberFormat("en", { maximumSignificantDigits: 10 });
  const show = (value) => format.format(Number(value));
  const svgNS = "http://www.w3.org/2000/svg";

  function chart(observations, title) {
    const values = observations.map((row) => Number(row.rate));
    const times = observations.map((row) => Date.parse(row.date));
    const min = Math.min(...values);
    const max = Math.max(...values);
    const valueSpan = max - min;
    const daySpan = times.at(-1) - times[0];
    const points = values.map((value, index) => [
      daySpan ? 22 + 756 * (times[index] - times[0]) / daySpan : 400,
      valueSpan ? 182 - 154 * (value - min) / valueSpan : 105,
    ]);
    const make = (tag, attrs) => {
      const element = document.createElementNS(svgNS, tag);
      for (const [name, value] of Object.entries(attrs)) element.setAttribute(name, value);
      return element;
    };
    const graphic = make("svg", {
      viewBox: "0 0 800 210", role: "img",
      "aria-label": `${title}. Range ${show(min)} to ${show(max)}. Full values in table.`,
    });
    for (const y of [28, 79, 131, 182]) {
      graphic.append(make("path", { d: `M22 ${y}H778`, stroke: "#d5e1ef", fill: "none" }));
    }
    if (points.length > 1) {
      graphic.append(make("polyline", {
        points: points.map(([x, y]) => `${x},${y}`).join(" "),
        fill: "none", stroke: "#1558d6", "stroke-width": "2.6",
        "stroke-linejoin": "round", "stroke-linecap": "round",
      }));
    }
    const [cx, cy] = points.at(-1);
    graphic.append(make("circle", { cx, cy, r: 5, fill: "#1558d6" }));
    document.querySelector("#history-chart").replaceChildren(graphic);
  }

  async function run() {
    button.disabled = true;
    result.hidden = true;
    status.textContent = "Replaying published quotes…";
    const url = "/workspace/api/history?" + new URLSearchParams(new FormData(form));
    try {
      const data = await api(url);
      const title = `${data.from_currency} → ${data.to_currency} reference history`;
      document.querySelector("#history-title").textContent = title;
      const move = data.largest_absolute_move;
      document.querySelector("#history-summary").textContent =
        `Range change ${show(data.range_change_percent)}% · Low ${show(data.minimum_rate)}` +
        ` · High ${show(data.maximum_rate)}` +
        (move ? ` · Largest move ${show(move.percent)}% on ${move.date}` : "");
      document.querySelector("#history-report").href = url;
      chart(data.observations, title);
      const rows = data.observations.map((item) => {
        const row = document.createElement("tr");
        for (const value of [
          item.date, show(item.rate),
          item.change_percent === null ? "—" : show(item.change_percent) + "%",
          item.days_since_previous ?? "—",
        ]) {
          const cell = document.createElement("td");
          cell.textContent = value;
          row.append(cell);
        }
        return row;
      });
      document.querySelector("#history-rows").replaceChildren(...rows);
      result.hidden = false;
      status.textContent = `${data.observation_count} paired observations · ` +
        `${data.publication_dates_without_both_quotes} publication dates lacked one or both quotes.`;
    } catch (error) {
      status.textContent = error.message;
    } finally {
      button.disabled = false;
    }
  }
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    run();
  });
  (async () => {
    try {
      const metadata = await api("/workspace/api/history/source");
      for (const key of ["source", "target"]) {
        const select = form.elements.namedItem(key);
        for (const currency of [...metadata.currencies].sort()) {
          select.add(new Option(currency, currency));
        }
      }
      form.elements.namedItem("source").value = "USD";
      form.elements.namedItem("target").value = "INR";
      const start = new Date(metadata.last_date + "T00:00:00Z");
      start.setUTCDate(start.getUTCDate() - 89);
      form.elements.namedItem("start").value = start.toISOString().slice(0, 10);
      form.elements.namedItem("end").value = metadata.last_date;
      for (const key of ["start", "end"]) {
        const field = form.elements.namedItem(key);
        field.min = metadata.first_date;
        field.max = metadata.last_date;
      }
      document.querySelector("#history-source").textContent =
        `${metadata.publication_dates.toLocaleString("en")} publication dates · ` +
        `${metadata.first_date} to ${metadata.last_date}`;
      await run();
    } catch (error) {
      status.textContent = error.message;
    }
  })();
})();
