let token = "";
const page = document.body.dataset.page;
const $ = (s) => document.querySelector(s);
function notice(t) {
  $("#notice").textContent = t;
}
async function api(path, options = {}) {
  const r = await fetch(path, {
    ...options,
    headers: {
      ...(token ? { Authorization: "Bearer " + token } : {}),
      ...(options.headers || {}),
    },
  });
  let d;
  try {
    d = await r.json();
  } catch {
    throw Error("Invalid service response");
  }
  if (!r.ok) throw Error(d.detail || "Service request failed");
  return d;
}
function show(id, data) {
  const el = $(id);
  if (!el) return;
  el.replaceChildren();
  const pre = document.createElement("pre");
  pre.textContent = JSON.stringify(data, null, 2);
  el.append(pre);
}
function table(id, rows) {
  const el = $(id);
  el.replaceChildren();
  if (!rows.length) {
    el.className = "empty";
    el.textContent =
      "No records available for this view. Connect your source or operator session to begin.";
    return;
  }
  const cols = Object.keys(rows[0]);
  const t = document.createElement("table"),
    head = t.createTHead().insertRow();
  cols.forEach((c) => {
    const h = document.createElement("th");
    h.textContent = c.replaceAll("_", " ");
    head.append(h);
  });
  const b = t.createTBody();
  rows.slice(0, 200).forEach((row) => {
    const tr = b.insertRow();
    cols.forEach((c) => {
      tr.insertCell().textContent =
        typeof row[c] === "object"
          ? JSON.stringify(row[c])
          : String(row[c] ?? "");
    });
  });
  el.append(t);
}
async function ledger() {
  if (!token) {
    table("#ledger", []);
    return;
  }
  const path =
    page === "payments"
      ? "/workspace/api/payments"
      : page === "settlements"
        ? "/workspace/api/settlements"
        : "/v1/reconciliation";
  const rows = await api(path);
  table(
    "#ledger",
    rows.filter(
      (r) =>
        !String(r.payment_id).startsWith("demo-") &&
        (page !== "exceptions" || r.status !== "matched"),
    ),
  );
}
async function load() {
  try {
    if ($("#status")) integrationStatus(await api("/workspace/api/status"));
    if ($("#ledger")) await ledger();
    if ($("#rates") || $("#provenance")) {
      const d = await api("/workspace/api/rates");
      if ($("#provenance")) show("#provenance", d);
      if ($("#rates")) {
        if (d.status !== "captured") show("#rates", d);
        else {
          notice(
            "Observation " +
              d.observation.date +
              " · captured " +
              d.captured_at,
          );
          table(
            "#rates",
            Object.entries(d.observation.rates).map(([currency, rate]) => ({
              currency,
              base: "EUR",
              rate,
              observation_date: d.observation.date,
            })),
          );
        }
      }
    }
    if ($("#batches")) {
      if (!token) {
        table("#batches", []);
        return;
      }
      const rows = (await api("/v1/batches")).filter(
        (r) => r.source !== "portfolio-synthetic-v1",
      );
      table("#batches", rows);
      rows.slice(0, 20).forEach((r) => {
        const btn = document.createElement("button");
        btn.textContent = "Verify " + r.batch_id;
        btn.addEventListener("click", async () => {
          try {
            notice(
              JSON.stringify(
                await api(
                  "/v1/batches/" + encodeURIComponent(r.batch_id) + "/verify",
                ),
              ),
            );
          } catch (e) {
            notice(e.message);
          }
        });
        $("#batches").append(btn);
      });
    }
  } catch (e) {
    notice(e.message);
  }
}
$("#connect").onclick = () => $("#session").showModal();
$("#close-session").onclick = () => $("#session").close();
$("#session-form").onsubmit = async (e) => {
  e.preventDefault();
  token = new FormData(e.target).get("token");
  e.target.reset();
  $("#session").close();
  $("#connect").textContent = "Disconnect operator";
  $("#connect").onclick = () => {
    token = "";
    location.reload();
  };
  notice("Operator token held in memory for this page only.");
  await load();
};
if ($("#sync"))
  $("#sync").onclick = async (e) => {
    e.target.disabled = true;
    try {
      await api("/workspace/api/rates/sync", { method: "POST" });
      await load();
    } catch (err) {
      notice(err.message);
    } finally {
      e.target.disabled = false;
    }
  };
if ($("#reconcile"))
  $("#reconcile").onclick = () => ledger().catch((e) => notice(e.message));
if ($("#readiness"))
  $("#readiness").onclick = async () => {
    try {
      show("#ready", await api("/readyz"));
    } catch (e) {
      notice(e.message);
    }
  };
if ($("#convert"))
  $("#convert").onsubmit = async (e) => {
    e.preventDefault();
    try {
      show(
        "#conversion",
        await api("/workspace/api/convert", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(Object.fromEntries(new FormData(e.target))),
        }),
      );
    } catch (err) {
      notice(err.message);
    }
  };
if ($("#ingest"))
  $("#ingest").onsubmit = async (e) => {
    e.preventDefault();
    const d = new FormData(e.target),
      f = d.get("file");
    if (f.size > 2000000) {
      notice("Source exceeds 2 MB limit");
      return;
    }
    try {
      show(
        "#receipt",
        await api(
          "/v1/ingest/" +
            encodeURIComponent(d.get("kind")) +
            "?source=" +
            encodeURIComponent(d.get("source")),
          {
            method: "POST",
            headers: {
              "Content-Type":
                d.get("kind") === "payments" ? "application/json" : "text/csv",
            },
            body: await f.text(),
          },
        ),
      );
    } catch (err) {
      notice(err.message);
    }
  };
if ($("#agent"))
  $("#agent").onsubmit = async (e) => {
    e.preventDefault();
    const btn = e.target.querySelector("button");
    btn.disabled = true;
    notice("Investigating…");
    try {
      show(
        "#answer",
        await api("/workspace/api/agent", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            question: new FormData(e.target).get("question"),
          }),
        }),
      );
      notice("Investigation complete");
    } catch (err) {
      notice(err.message);
    } finally {
      btn.disabled = false;
    }
  };
load();

function integrationStatus(data) {
 const el=document.querySelector('#status'); if(!el)return; el.replaceChildren();
 const labels={model_configured:'AI provider',rate_provider:'Reference provider',reference_data:'Reference capture',payment_source:'Payment records',cloud:'Cloud execution',agent_scope:'Agent permissions'};
 const list=document.createElement('dl');list.className='integrations';
 for(const [key,value] of Object.entries(data)){const term=document.createElement('dt'), detail=document.createElement('dd');term.textContent=labels[key]||key;detail.textContent=typeof value==='boolean'?(value?'Connected':'Not configured'):value;list.append(term,detail)}el.append(list);
}
