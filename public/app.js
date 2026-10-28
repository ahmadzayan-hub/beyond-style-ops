// public/app.js — Beyond Style ops web app (slice 1: Orders read-only, Payments update).
// Every value from the sheet is written with textContent. Never switch to innerHTML.

const $ = (id) => document.getElementById(id);
const state = { orders: [], payments: [], options: null, selectedOrder: null };

async function api(path, options = {}) {
  const init = { credentials: "same-origin", headers: {}, ...options };
  if (options.body !== undefined) {
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(options.body);
  }
  const res = await fetch(path, init);
  let data = {};
  try { data = await res.json(); } catch (_) { /* empty body */ }
  if (!res.ok) {
    const error = new Error(data.detail || `Request failed (${res.status})`);
    error.status = res.status;
    throw error;
  }
  return data;
}

function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined && text !== null) node.textContent = String(text);
  if (className) node.className = className;
  return node;
}

function setMessage(node, text, isError) {
  node.textContent = text;
  node.hidden = !text;
  node.classList.toggle("error", Boolean(isError));
  node.classList.toggle("success", !isError && Boolean(text));
}

function showView(name) {
  for (const view of ["login-view", "orders-view", "payments-view"]) $(view).hidden = view !== name;
  $("nav").hidden = name === "login-view";
  for (const btn of document.querySelectorAll(".tab")) {
    btn.classList.toggle("active", btn.dataset.tab === name.replace("-view", ""));
  }
}

function fillSelect(select, values, placeholder) {
  select.replaceChildren();
  if (placeholder !== undefined) select.appendChild(el("option", placeholder, null)).value = "";
  for (const v of values) {
    const opt = el("option", v);
    opt.value = v;
    select.appendChild(opt);
  }
}

function money(value) {
  const n = Number(String(value).replace(/,/g, ""));
  return value === "" || Number.isNaN(n) ? (value || "") : `AED ${n.toFixed(2)}`;
}

// ── Orders ─────────────────────────────────────────────────────────────────
function uniqueValues(column) {
  return [...new Set(state.orders.map((o) => o[column]).filter(Boolean))].sort();
}

function renderOrders() {
  const search = $("f-search").value.trim().toLowerCase();
  const status = $("f-status").value;
  const emirate = $("f-emirate").value;
  const risk = $("f-risk").value;
  const rows = state.orders.filter((o) => {
    if (search) {
      const hay = [o["Customer Name"], o["Order ID"], o["Mobile Number"]].join(" ").toLowerCase();
      if (!hay.includes(search)) return false;
    }
    if (status && o["Order Status"] !== status) return false;
    if (emirate && o["Emirate"] !== emirate) return false;
    if (risk && o["Risk Status"] !== risk) return false;
    return true;
  });

  $("orders-count").textContent = `Showing ${rows.length} of ${state.orders.length} orders`;
  const body = $("orders-body");
  body.replaceChildren();
  for (const o of rows) {
    const tr = document.createElement("tr");
    tr.tabIndex = 0;
    tr.dataset.orderId = o["Order ID"];
    tr.append(
      el("td", o["Order ID"]),
      el("td", o["Order Date"]),
      el("td", o["Customer Name"]),
      el("td", o["Emirate"]),
      el("td", o["Order Status"]),
      el("td", o["Payment Status"]),
      el("td", o["Risk Status"]),
      el("td", money(o["Total Amount"])),
    );
    tr.addEventListener("click", () => openOrder(o["Order ID"]));
    tr.addEventListener("keydown", (e) => { if (e.key === "Enter") openOrder(o["Order ID"]); });
    body.appendChild(tr);
  }
  if (!rows.length) body.appendChild(el("tr", "No orders match the filters.", "empty"));
}

async function loadOrders() {
  const data = await api("/api/orders");
  state.orders = data.orders;
  fillSelect($("f-status"), uniqueValues("Order Status"), "All order statuses");
  fillSelect($("f-emirate"), uniqueValues("Emirate"), "All emirates");
  fillSelect($("f-risk"), uniqueValues("Risk Status"), "All risk levels");
  renderOrders();
}

const DETAIL_FIELDS = [
  ["Order Date", "Order date"], ["Customer Name", "Customer"], ["Mobile Number", "Mobile"],
  ["WhatsApp Number", "WhatsApp"], ["Instagram Username", "Instagram"], ["Emirate", "Emirate"],
  ["Area", "Area"], ["Product Summary", "Product"], ["Colour / Design", "Colour / design"],
  ["Quantity", "Quantity"], ["Total Amount", "Total"], ["Payment Method", "Payment method"],
  ["Payment Status", "Payment status"], ["Order Status", "Order status"],
  ["Packing QC Status", "Packing QC"], ["Courier Status", "Courier"],
  ["Delivery Status", "Delivery"], ["Risk Status", "Risk"], ["Critical Data Status", "Critical data"],
];

async function openOrder(orderId) {
  state.selectedOrder = orderId;
  const { order } = await api(`/api/orders/${encodeURIComponent(orderId)}`);
  $("detail-title").textContent = `Order ${order["Order ID"]}`;
  const dl = $("detail-fields");
  dl.replaceChildren();
  for (const [key, label] of DETAIL_FIELDS) {
    dl.append(el("dt", label), el("dd", key === "Total Amount" ? money(order[key]) : order[key] || "—"));
  }
  $("order-detail").hidden = false;
  $("order-detail").scrollIntoView({ behavior: "smooth", block: "start" });
}

// ── Payments ───────────────────────────────────────────────────────────────
async function loadPayments() {
  const { payments, source } = await api("/api/payments");
  state.payments = payments;
  const body = $("payments-body");
  body.replaceChildren();
  for (const p of payments) {
    const tr = document.createElement("tr");
    tr.append(
      el("td", p["Order ID"]),
      el("td", p["Customer Name"]),
      el("td", p["Payment Method"]),
      el("td", p["Payment Status"]),
      el("td", money(p["Total Amount"])),
      el("td", money(p["COD Expected"])),
    );
    body.appendChild(tr);
  }
  if (!payments.length) body.appendChild(el("tr", "No payment records found.", "empty"));
  $("payments-source").textContent = source === "master_orders"
    ? "Showing Master Orders because the Payments tab is empty."
    : "Source: Payments tab.";

  fillSelect($("pay-order"), payments.map((p) => p["Order ID"]).filter(Boolean));
  if (state.options) {
    fillSelect($("pay-status"), state.options.payment_statuses);
  }
  if ($("pay-order").options.length) fillPaymentForm($("pay-order").value);
}

function fillPaymentForm(orderId) {
  const p = state.payments.find((x) => x["Order ID"] === orderId);
  if (!p) return;
  if ([...$("pay-status").options].some((o) => o.value === p["Payment Status"])) {
    $("pay-status").value = p["Payment Status"];
  }
  $("pay-ref").value = p["Payment Reference"] || "";
  $("pay-link").value = p["Payment Link"] || "";
  $("pay-cod-exp").value = p["COD Expected"] || "";
  $("pay-cod-col").value = p["COD Collected"] || "";
  $("pay-notes").value = p["Notes"] || "";
  updateRuleHint();
}

function updateRuleHint() {
  const status = $("pay-status").value;
  const hint = status === "Paid Online"
    ? "Paid Online sets COD expected to 0."
    : status === "COD Confirmed"
      ? "COD Confirmed needs a COD expected amount."
      : "";
  $("pay-rule").textContent = hint;
}

async function savePayment(event) {
  event.preventDefault();
  const orderId = $("pay-order").value;
  const msg = $("pay-message");
  try {
    const result = await api(`/api/payments/${encodeURIComponent(orderId)}`, {
      method: "POST",
      body: {
        status: $("pay-status").value,
        payment_reference: $("pay-ref").value,
        payment_link: $("pay-link").value,
        cod_expected: $("pay-cod-exp").value,
        cod_collected: $("pay-cod-col").value,
        notes: $("pay-notes").value,
      },
    });
    const note = result.payments_tab_updated ? "" : " The Payments tab has no row for this order, so only Master Orders changed.";
    setMessage(msg, `Payment saved for ${orderId}.${note}`, false);
    await loadPayments();
    await loadOrders();
    $("pay-order").value = orderId;
    fillPaymentForm(orderId);
  } catch (err) {
    setMessage(msg, err.message, true);
  }
}

// ── Session and navigation ─────────────────────────────────────────────────
async function enter() {
  if (!state.options) state.options = await api("/api/options");
  showView("orders-view");
  await loadOrders();
}

async function showTab(tab) {
  if (tab === "orders") {
    showView("orders-view");
    await loadOrders();
  } else {
    showView("payments-view");
    await loadPayments();
  }
}

function wire() {
  $("login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const err = $("login-error");
    err.hidden = true;
    try {
      await api("/api/login", { method: "POST", body: { password: $("password").value } });
      $("password").value = "";
      await enter();
    } catch (ex) {
      err.textContent = ex.status === 503 ? ex.message : "Incorrect password.";
      err.hidden = false;
    }
  });

  $("logout").addEventListener("click", async () => {
    await api("/api/logout", { method: "POST" });
    state.options = null;
    showView("login-view");
  });

  for (const btn of document.querySelectorAll(".tab")) {
    btn.addEventListener("click", () => showTab(btn.dataset.tab));
  }
  for (const id of ["f-search", "f-status", "f-emirate", "f-risk"]) {
    $(id).addEventListener("input", renderOrders);
  }
  $("pay-order").addEventListener("change", (e) => fillPaymentForm(e.target.value));
  $("pay-status").addEventListener("change", updateRuleHint);
  $("payment-form").addEventListener("submit", savePayment);
}

async function start() {
  wire();
  try {
    const { authenticated } = await api("/api/session");
    if (authenticated) await enter();
    else showView("login-view");
  } catch (_) {
    showView("login-view");
  }
}

start();
