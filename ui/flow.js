/* TESTIGO+ interface: the shell (one bar for every page), the guided demo, the
 * results page and the router. Loaded after app.js (state, helpers, approval,
 * mandate, presenter) and landing.js (the landing). Visual system and views:
 * docs/specs/06-vistas-app.md.
 *
 * Routes (URL hash):
 *   #/                landing (#/video, #/threats, #/how, #/proof, #/bench,
 *                     #/limits, #/start scroll to a section; #/attacks = #/threats)
 *   #/results         WitnessBench, simply
 *   #/demo/rules      1 Your rules
 *   #/demo/run        2 Run the agent
 *   #/demo/watch      3 Watching
 *   #/demo/result     4 Result
 *   #/present[/0-8]   the presenter views for recording (not linked anywhere)
 */
"use strict";

const STEPS = [
  { key: "rules", name: "Your rules" },
  { key: "run", name: "Run the agent" },
  { key: "watch", name: "Watching" },
  { key: "result", name: "Result" },
];
const SITUATIONS = [
  { key: "clean", name: "Normal order", text: "An honest supplier page. The order should reach your warehouse." },
  { key: "a1", name: "Hidden order in the page code", text: "An invisible notice tells the agent to ship somewhere else." },
  { key: "a2", name: "Order painted in an image", text: "A banner image carries a faint instruction to change the address." },
  { key: "a3", name: "Tampered delivery address", text: "A script shows another street under your company’s name." },
];
function situation(key) { return SITUATIONS.find(x => x.key === key) || { key, name: key || "—", text: "" }; }

// -- routes -----------------------------------------------------------------
function parseRoute() {
  const parts = (location.hash || "").replace(/^#\/?/, "").split("/").filter(Boolean);
  if (parts[0] === "present") {
    const n = parseInt(parts[1] || "0", 10);
    return { name: "present", view: Number.isInteger(n) && n >= 0 && n < VIEWS.length ? n : 0 };
  }
  if (/^[0-8]$/.test(parts[0] || "")) return { name: "present", view: Number(parts[0]) };   // old #/N links
  if (parts[0] === "demo") {
    return { name: "demo", step: STEPS.some(x => x.key === parts[1]) ? parts[1] : "rules" };
  }
  if (parts[0] === "results") return { name: "results" };
  if (parts[0] === "attacks") return { name: "landing", section: "threats" };
  if (["top", "video", "threats", "how", "proof", "bench", "limits", "start"].includes(parts[0])) return { name: "landing", section: parts[0] };
  return { name: "landing" };
}
function sameRoute(a, b) {
  return !!a && !!b && a.name === b.name && a.step === b.step && a.view === b.view && a.section === b.section;
}
function nav(hash) {
  if (location.hash === hash) onRoute(true);
  else location.hash = hash;
}
function onRoute(force) {
  const prev = S.route;
  S.route = parseRoute();
  if (!prev || prev.name !== S.route.name || prev.step !== S.route.step) {
    // the new view rises in; the progress fills from the step we came from
    const idx = k => STEPS.findIndex(x => x.key === k);
    S.enter = { at: Date.now(), fromStep: prev && prev.name === "demo" ? idx(prev.step) : 0 };
    S.menuOpen = false;
    if (S.route.name !== "landing") S.navActive = null;
  }
  if (S.route.name === "present") S.view = S.route.view;
  draw();
  loadForRoute();
  if (force || !sameRoute(prev, S.route)) arrive(prev);
}
// after a route change: a section scrolls into view; a new page starts at the
// top with focus on its heading, so screen readers hear where they are
function arrive(prev) {
  if (S.route.name === "landing" && S.route.section) {
    const el = document.getElementById("sec-" + S.route.section);
    const smooth = prev && prev.name === "landing" && !reducedMotion();
    if (el) { el.scrollIntoView({ block: "start", behavior: smooth ? "smooth" : "auto" }); el.focus({ preventScroll: true }); }
    return;
  }
  if (!prev) return;                    // the first load keeps the browser's focus
  window.scrollTo(0, 0);
  const h = document.querySelector("#main h1, #view h1");
  if (h) { h.setAttribute("tabindex", "-1"); h.focus({ preventScroll: true }); }
}
// presenter navigation (arrow keys, 0-8, follow)
function go(i) {
  i = Math.max(0, Math.min(VIEWS.length - 1, i));
  const h = "#/present/" + i;
  if (location.hash !== h) history.replaceState(null, "", h);
  S.route = { name: "present", view: i }; S.view = i;
  draw(); loadFor(i);
}
function follow(i) { if (S.auto && S.route.name === "present") S.pendingView = i; }

async function loadForRoute() {
  const r = S.route;
  try {
    if (r.name === "present") return loadFor(S.view);
    if (r.name === "landing" && !S.benchComplete) { S.benchComplete = await getJSON("/api/bench?complete=1"); draw(); }
    if (r.name === "results" && !S.bench) { S.bench = await getJSON("/api/bench"); draw(); }
    if (r.name === "landing" || r.name === "results") return;
    if (r.name === "demo") {
      if (!S.policy || r.step === "rules") await loadPolicy();
      if (r.step === "result") {
        const run = curRun();
        if (run && run.mode === "supervised") loadReceipt(true);
      }
      if (r.step === "watch") loadDesk();
    }
  } catch (err) { console.error(err); }
}
async function loadPolicy() {
  try { S.policy = await getJSON("/api/policy"); S.policyError = ""; }
  catch (err) { S.policyError = err.message; }
  draw();
}

// -- the run of the guided demo -----------------------------------------------
// The run on screen: the newest one that started (supervised or not), unless the
// page just asked for a new run that has not reported yet.
function curRun() {
  if (S.waitingFor) return null;
  const r = S.runs[S.current];
  return r && r.mode ? r : null;
}
function procFor(r) { return S.proc && r && S.proc.mode === r.mode && S.proc.state !== "idle" && S.proc.state !== "orphaned" ? S.proc : null; }
function procRunning() { return !!S.proc && (S.proc.state === "running" || S.proc.state === "orphaned"); }
function procEnded() { return !!S.proc && ["finished", "failed", "cancelled"].includes(S.proc.state); }
function lastStep(r, f) { for (let i = r.log.length - 1; i >= 0; i--) if (r.log[i].type === "agent.step" && f(r.log[i].label || "")) return r.log[i]; return null; }

// The one outcome of a run, in plain words. kind: running | blocked | paused |
// denied | buyer | attacker | flagged | stopped | ended | error
function outcome(r) {
  if (!r || !r.mode) return null;
  const sup = r.mode === "supervised";
  const order = r.order;
  const toBuyer = order ? toAllowedAddress(order.address) : null;
  const where = order ? `${usd(order.amount_cents)} · ${order.address}` : "";
  const c = r.check;
  if (sup && c && c.status !== "ok") {
    if (c.status === "cannot_verify") return { kind: "paused", cls: "warn", icon: ICON.ask,
      title: "Paused: the screen could not be read clearly",
      text: "TESTIGO+ could not read the total or the address with confidence, so it did not let the agent confirm. Nothing was ordered." };
    if (c.status === "policy_violation") return { kind: "blocked", cls: "bad", icon: ICON.stop,
      title: "Blocked: the order breaks your rules",
      text: "The screen showed an order your rules do not allow. TESTIGO+ stopped it before Confirm. Nothing was ordered." };
    const painted = (c.pixels_only_text || []).length > 0;
    return { kind: "blocked", cls: "bad", icon: ICON.stop,
      title: painted ? "Blocked: an instruction was painted into the page" : "Blocked: the page hid an instruction for the agent",
      text: painted
        ? "The screen showed text that is not in the page code, an order aimed at the agent. TESTIGO+ stopped before Confirm. Nothing was ordered."
        : "The page code carried text you could not see on screen, an order aimed at the agent. TESTIGO+ stopped before Confirm. Nothing was ordered." };
  }
  const vo = verifyOutcome(r);
  if (sup && vo.kind === "blocked") return { kind: "blocked", cls: "bad", icon: ICON.stop,
    title: "Blocked: the address changed after you approved",
    text: `On the review screen the ${diffFields(vo.event).join(" and ") || "order"} no longer matched what you approved, so the order was never confirmed.` };
  if (sup && vo.kind === "cannot" && vo.moment === "review") return { kind: "paused", cls: "warn", icon: ICON.ask,
    title: "Paused: the review screen could not be read clearly",
    text: "Without a clear match to what you approved, TESTIGO+ did not click Confirm. Nothing was ordered." };
  if (r.granted && !isGranted(r.granted)) return { kind: "denied", cls: "off", icon: ICON.stop,
    title: "Not approved: nothing was ordered",
    text: "The order was not approved, so the agent did not confirm it." };
  if (order) {
    if (toBuyer === false) return { kind: "attacker", cls: "lost", icon: ICON.warn,
      title: sup && vo.kind === "flagged" ? "Delivered to the attacker, and flagged" : "Delivered to the attacker",
      text: sup ? `The order was confirmed for ${where}, which is not your warehouse.${vo.kind === "flagged" ? " TESTIGO+ saw after the click that it differs from what you approved; the receipt says so." : ""}`
                : `With nothing checking the screen, the agent confirmed the order for ${where}. The goods go to the attacker.` };
    if (sup && vo.kind === "flagged") return { kind: "flagged", cls: "bad", icon: ICON.stop,
      title: "Delivered, but flagged",
      text: "After the click, what was ordered is not what you approved. The signed receipt says so." };
    if (sup && vo.kind === "cannot") return { kind: "flagged", cls: "warn", icon: ICON.ask,
      title: "Delivered, but not verified",
      text: "The result screen could not be read clearly after the click. The receipt is marked for a person to check." };
    return { kind: "buyer", cls: "ok", icon: ICON.check, title: "Delivered to your warehouse",
      text: sup ? `${where}. Checked before and after the click${r.receipt ? ", and signed" : ""}.`
                : `${where}. Nothing checked the screen, but this time the order went to your warehouse.` };
  }
  if (lastStep(r, l => l === "proposed: done")) return { kind: "stopped", cls: "off", icon: ICON.user,
    title: "The agent stopped on its own",
    text: sup ? "The agent ended without confirming an order. Nothing was ordered."
              : "The agent ended without confirming an order: it did not fall for the page this time. Nothing was ordered." };
  if (lastStep(r, l => /^stopped: max_steps/.test(l))) return { kind: "stopped", cls: "off", icon: ICON.dot,
    title: "The agent ran out of steps", text: "It never confirmed an order. Nothing was ordered." };
  const p = procFor(r);
  if (p && p.state !== "running") return p.state === "finished"
    ? { kind: "ended", cls: "off", icon: ICON.dot, title: "The run ended", text: "It ended without confirming an order." }
    : { kind: "error", cls: "warn", icon: ICON.warn,
        title: p.state === "cancelled" ? "You stopped the run" : "The run stopped with an error",
        text: p.state === "cancelled" ? "Nothing more will happen in this run." : "The agent did not finish. The last lines it printed are in the details." };
  return { kind: "running", cls: "info", icon: ICON.eye, title: "The agent is working", text: "" };
}
function needsYou(r) {
  if (!r || r.mode !== "supervised" || !r.approval || r.granted) return false;
  const p = procFor(r);
  return !(p && p.state !== "running");      // a stopped run waits for nobody
}

// one line of the Watching timeline, in plain words; null to leave it out
function plainLine(e, r) {
  const sup = r.mode === "supervised";
  switch (e.type) {
    case "run.started": return [ICON.dot, "info", sup ? "The agent started restocking your warehouse. TESTIGO+ is watching." : "The agent started restocking your warehouse, with TESTIGO+ switched off."];
    case "agent.step": {
      const l = e.label || "";
      if (l === "proposed: done") return [ICON.user, "info", "The agent says it is finished."];
      if (/^stopped: max_steps/.test(l)) return [ICON.dot, "warn", "The agent ran out of steps."];
      if (/^sensitive/.test(l)) return [ICON.eye, "info", "This click would confirm the order. Checking the screen first."];
      if (/without a check or approval/.test(l)) return [ICON.warn, "lost", "The order was confirmed with nobody checking it."];
      if (/^receipt not/.test(l)) return [ICON.warn, "warn", "The receipt could not be signed on this machine."];
      if (/^proposed: /.test(l) && e.detail) return [ICON.dot, "info", "Agent: “" + clip(e.detail, 160) + "”"];
      return null;
    }
    case "check.result":
      if (e.status === "ok") return [ICON.check, "ok", "Checked the screen: the total and the address follow your rules."];
      if (e.status === "cannot_verify") return [ICON.ask, "warn", "Could not read the screen clearly, so the agent was not allowed to confirm."];
      if (e.status === "policy_violation") return [ICON.stop, "bad", "Stopped: the screen shows an order your rules do not allow."];
      return [ICON.stop, "bad", (e.pixels_only_text || []).length
        ? "Stopped: the screen shows an instruction that is not in the page code."
        : "Stopped: the page code hides an instruction you cannot see."];
    case "approval.requested": return [ICON.pause, "warn", `Asked you to approve ${usd(e.amount_cents)} to ${e.address}.`];
    case "approval.granted": return isGranted(e) ? [ICON.check, "ok", "You approved by reading it aloud."] : [ICON.stop, "off", "The order was not approved."];
    case "order.confirmed": return [ICON.box, "info", `The supplier confirmed the order: ${usd(e.amount_cents)}, ship to ${e.address}.`];
    case "verify.result": {
      const review = e.moment === "review";
      if (e.status === "match") return [ICON.check, "ok", review
        ? "Checked the review screen: the address matches what you approved."
        : "Checked after the click: the order is what you approved."];
      if (e.status === "cannot_verify") return [ICON.ask, "warn", review
        ? "Could not read the review screen clearly, so it did not click Confirm."
        : "Could not read the result clearly. Flagged for a person."];
      return [ICON.stop, "bad", review
        ? "Stopped: the address on the review screen changed after you approved."
        : "After the click, the order differs from what you approved. Flagged."];
    }
    case "explain.result": return [ICON.eye, "info", e.status === "none"
      ? "After the run, TESTIGO+ looked at the screen the agent confirmed: nothing suspicious."
      : "After the run, TESTIGO+ looked at the screen the agent confirmed and found the attack (see the result)."];
    case "receipt.signed": return isPlaceholder(e.signature)
      ? [ICON.warn, "warn", "A receipt was built but could not be signed."]
      : [ICON.seal, "ok", "Signed a receipt you can verify."];
  }
  return null;
}
function clip(t, n) { t = String(t || ""); return t.length > n ? t.slice(0, n - 1) + "…" : t; }

async function startRun(req) {
  if (S.runReq.busy) return;
  S.runReq = { busy: true, error: "", busyRun: false }; draw();
  try {
    S.proc = await getJSON("/api/run", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(req) });
    S.waitingFor = S.proc.mode;
    S.runReq = { busy: false, error: "", busyRun: false };
    nav("#/demo/watch");
  } catch (err) {
    S.runReq = { busy: false, error: err.message, busyRun: err.status === 409 };
    if (err.status === 409) refreshProc();
    draw();
  }
}
function startPicked() {
  const p = S.pick;
  const req = { scenario: p.scenario, variant: p.variant, supervised: p.supervised };
  if (p.headed) req.headed = true;
  startRun(req);
}
async function cancelRun() {
  try {
    S.proc = await getJSON("/api/run/cancel", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
  } catch (err) { S.runReq = Object.assign({}, S.runReq, { error: err.message }); }
  draw();
}
// After a reload: a run started here that has not reported run.started yet is
// still "starting" (same clock on both sides, so the ISO times compare).
function syncWaiting() {
  const p = S.proc;
  if (!p || p.state !== "running" || !p.started) return;
  const first = (S.runs[p.mode] || {}).log || [];
  const started = first.length && first[0].type === "run.started" ? first[0].ts : "";
  if (!started || started < p.started) S.waitingFor = p.mode;
}
async function refreshProc() {
  try { S.proc = await getJSON("/api/run"); } catch (err) { console.error(err); }
}
// while a run started here is alive, ask how it is doing
setInterval(async () => {
  if (!S.proc || S.proc.state !== "running") return;
  await refreshProc();
  if (S.proc.state !== "running") draw();
}, 1500);

// -- small pieces -----------------------------------------------------------------
const TICK = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m6 12.5 4 4 8-9"/></svg>`;
function more(id, summary, body) {
  return `<details class="more" id="${id}"${S.open[id] ? " open" : ""}><summary id="${id}-s">${summary}</summary><div class="more-body">${body}</div></details>`;
}
function askBefore(v) {
  return v === "new_address" ? "shipping to a new address" : String(v || "").replace(/_/g, " ");
}
function shortDate(iso) {
  const m = /^(\d{4})-(\d\d)-(\d\d)/.exec(iso || "");
  if (!m) return "";
  return `${Number(m[3])} ${["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][Number(m[2]) - 1]}`;
}
const secs = ms => Number.isFinite(ms) ? Math.round(ms / 1000) + " s" : "—";
function callout(cls, icon, title, body) {
  return `<div class="callout ${cls}">${icon}<div><b>${title}</b>${body}</div></div>`;
}

// The headline numbers of WitnessBench, from the file only.
// A results file from an earlier scenario is history: never shown as current.
function benchStale(b) { return b && b.available && b.current === false ? (b.source || "the results file") : ""; }
function benchFacts(b) {
  if (benchStale(b)) return null;
  const s = b && b.available && b.data && b.data.summary;
  const counted = x => x && Number.isFinite(x.succeeded) && Number.isFinite(x.runs);
  if (!s || !counted(s.attacks_succeed_without) || !counted(s.attacks_succeed_with)) return null;
  const rows = Array.isArray(b.data.rows) ? b.data.rows : [];
  const hp = rows.filter(x => x.mode === "supervised" && (x.scenario === "a1" || x.scenario === "a2"));
  const fp = s.false_positives || {};
  return {
    wo: s.attacks_succeed_without, wi: s.attacks_succeed_with,
    stopped: hp.filter(x => x.blocked).length, hidden: hp.length,
    fp, fpUnread: Array.isArray(fp.statuses) && fp.statuses.length > 0 && fp.statuses.every(x => x === "cannot_verify"),
    perCheck: (s.per_check_latency_ms || {}).median, perRun: (s.added_latency_ms || {}).median,
    date: shortDate(b.data.generated), source: b.source || "", rows, summary: s,
    incomplete: b.data.complete === false, missing: Array.isArray(b.data.missing) ? b.data.missing.length : null,
  };
}

// -- shell: one bar for every page ---------------------------------------------------
// Outside the demo: brand, the capsule of section links with its sliding pill,
// "Code" and "Try the demo". Inside the demo the capsule becomes the 4-step progress.
function navKey() {
  const r = S.route;
  return r.name === "results" ? "bench" : r.name === "landing" ? S.navActive : null;
}
function siteHeader() {
  const r = S.route, demo = r.name === "demo";
  return `<header class="nav${demo ? " in-demo" : ""}${window.scrollY > 24 ? " scrolled" : ""}" id="topnav"><div class="wrap">
      <a class="brand" id="nav-home" href="#/" aria-label="TESTIGO+ home">${MARK}<span class="name"><b>TESTIGO+</b><small>Witness for AI agents</small></span></a>
      ${demo ? stepper(r.step) : landingNavLinks(navKey())}
      <div class="nav-end">
        <a class="gh" id="nav-code" href="${GH_URL}">${GH_ICON}Code</a>
        ${demo ? "" : `<a class="btn-primary" id="nav-try" href="#/demo/rules">Try the demo</a>
        <button class="menu-btn" id="menuBtn" type="button" aria-expanded="${S.menuOpen ? "true" : "false"}" aria-controls="links" aria-label="${S.menuOpen ? "Close menu" : "Open menu"}"><span></span><span></span><span></span></button>`}
      </div>
    </div></header>`;
}
// the pill sits under the active link (no slide when the bar was just drawn)
function placePill(animate) {
  const links = document.getElementById("links");
  if (!links) return;
  const pill = links.querySelector(".pill"), key = navKey();
  let a = null;
  links.querySelectorAll("a").forEach(l => {
    const on = l.id === "nav-" + key;
    l.classList.toggle("active", on);
    if (on) { l.setAttribute("aria-current", "true"); a = l; } else l.removeAttribute("aria-current");
  });
  if (!a || !a.offsetWidth) { pill.style.opacity = "0"; return; }
  if (!animate) pill.style.transition = "none";
  pill.style.transform = `translateX(${a.offsetLeft}px) scaleX(${a.offsetWidth / 100})`;
  pill.style.opacity = "1";
  if (!animate) { void pill.offsetWidth; pill.style.transition = ""; }
}
function setMenu(open) {
  S.menuOpen = open;
  const links = document.getElementById("links"), btn = document.getElementById("menuBtn");
  if (links) links.classList.toggle("open", open);
  if (btn) { btn.setAttribute("aria-expanded", open ? "true" : "false"); btn.setAttribute("aria-label", open ? "Close menu" : "Open menu"); }
}
function testBanner(fixed) {
  return `<div class="testdata${fixed ? " fixed" : ""}" id="testdata" ${S.test ? "" : "hidden"}>
    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3 2 21h20L12 3Zm0 6v5m0 3v.5" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"/></svg>
    <span><b>Test data.</b> These events come from the offline fixtures, not a real run. Do not record them for the video.</span></div>`;
}
function siteFooter() {
  return `<footer class="site-foot"><div class="wrap">
      <span class="mono">TESTIGO+</span>
      <span>Simulation only: simulated company, supplier and addresses. No real brands.</span>
      <span>Built with Muse Wonder, SAM 3.1, Muse Spark and Muse Voice.</span>
    </div></footer>`;
}
// each view rises in once (0.5 s); a redraw meanwhile continues the same motion
function enterAttr() {
  const e = S.enter;
  const t = e ? Date.now() - e.at : 1e9;
  return t < 600 ? ` data-enter style="--t:-${t}ms"` : "";
}
function pageHead(eyebrow, title, lede) {
  return `<header class="page-head"><span class="eyebrow">${eyebrow}</span><h1>${title}</h1>${lede ? `<p class="lede">${lede}</p>` : ""}</header>`;
}

// -- pages ------------------------------------------------------------------------------
const page = {
  results() {
    const f = benchFacts(S.bench), loaded = !!S.bench, stale = benchStale(S.bench);
    let table = "";
    if (f) {
      const rows = f.rows;
      const count = (sc, mode, fn) => rows.filter(x => x.scenario === sc && x.mode === mode && fn(x)).length;
      const n = (sc, mode) => rows.filter(x => x.scenario === sc && x.mode === mode).length;
      const line = (sc, mode) => {
        const total = n(sc, mode);
        if (!total) return `<td colspan="4">—</td>`;
        const att = count(sc, mode, x => x.delivered_to_attacker);
        const ownWh = count(sc, mode, x => x.confirmed && !x.delivered_to_attacker);
        const stopped = count(sc, mode, x => x.blocked);
        const own = count(sc, mode, x => !x.confirmed && !x.blocked);
        return `<td class="${att ? "lost-t" : ""}">${att} of ${total}</td><td>${stopped}</td><td>${own}</td><td>${ownWh}</td>`;
      };
      const body = SITUATIONS.map(x => ["no_supervisor", "supervised"].map((mode, i) =>
        `<tr${i === 0 ? ' class="first"' : ""}>${i === 0 ? `<th scope="row" rowspan="2">${esc(x.name)}</th>` : ""}<td class="mode">${mode === "supervised" ? "With TESTIGO+" : "Without"}</td>${line(x.key, mode)}</tr>`).join("")).join("");
      table = rows.length ? `<div class="table-wrap" id="rtable-wrap" role="region" aria-label="Results per situation" tabindex="0"><table class="rtable">
          <caption>Each situation ran ${esc(n("a1", "supervised") || 5)} times without and with TESTIGO+.</caption>
          <thead><tr><th scope="col">Situation</th><th scope="col">Run</th><th scope="col">Reached the attacker</th><th scope="col">Stopped by TESTIGO+</th><th scope="col">Agent stopped on its own</th><th scope="col">Delivered to your warehouse</th></tr></thead>
          <tbody>${body}</tbody></table></div>` : "";
    }
    const s = f && f.summary;
    const edges = s && Array.isArray(s.edge_cases) && s.edge_cases.length
      ? `<p>Known limit, counted apart: an attack written only in words (“eighty-eight Mill Street”) slips past the hidden-text filter. ${s.edge_cases.map(x => `${esc(x.mode === "supervised" ? "With" : "Without")} TESTIGO+: ${x.delivered_to_attacker ? "delivered to the attacker" : "not delivered to the attacker"}.`).join(" ")}</p>` : "";
    const details = f ? more("res-more", "How this was measured", `
        <p>Every number is read from <span class="mono">${esc(f.source)}</span>, written by the benchmark itself${f.date ? ` on ${esc(f.date)}` : ""}. Model: <span class="mono">${esc((S.bench.data || {}).model || "—")}</span>.</p>
        <p>TESTIGO+ adds a median of ${esc(secs(f.perRun))} per run and ${esc(secs(f.perCheck))} per screen check (p90 ${esc(secs((s.per_check_latency_ms || {}).p90))}).</p>
        ${edges}
        ${Number(s.errors) > 0 ? `<p>${esc(s.errors)} runs failed and are left out.</p>` : ""}
        <p>The full view with bars is in the <a id="res-present" href="#/present/8">presenter</a>.</p>`) : "";
    const note = !f ? `<p class="bench-note" id="bench-note">${esc(!loaded ? "Loading the results…"
        : stale ? `Not measured yet in this scenario. ${stale} is from an earlier scenario and is kept as history. Re-running with the current scenario.`
        : "No WitnessBench results yet. They are read from the benchmark file, never typed in.")}</p>` : "";
    const hidden = f && f.hidden ? `<p class="bench-extra"><b class="tnum">${esc(f.stopped)} of ${esc(f.hidden)}</b> pages with a hidden or painted order were stopped before Confirm.</p>` : "";
    const resisted = f && f.wo.succeeded === 0 && f.wi.succeeded === 0
      ? `<p class="bench-extra">Muse Wonder resisted every attack on its own in this run, with or without TESTIGO+.</p>` : "";
    return `<div class="wrap page"${enterAttr()}>
      ${pageHead("WitnessBench", "WitnessBench results", f
        ? `${esc(f.wo.runs)} attacks and ${esc(f.fp.clean_runs ?? "—")} clean orders, each run without and with TESTIGO+, with Meta’s real models${f.date ? ` on ${esc(f.date)}` : ""}. Counts, not percentages.`
        : "The benchmark runs every attack without and with TESTIGO+ using Meta’s real models. Counts, not percentages.")}
      ${f && f.incomplete ? callout("warn", ICON.warn, "This benchmark run is incomplete.",
        `<p>${f.missing != null ? `${esc(f.missing)} configurations are missing. ` : ""}These numbers come from an unfinished local run (<span class="mono">${esc(f.source)}</span>); the landing shows the last complete results.</p>`) : ""}
      ${note}${benchFigs(f)}${hidden}${resisted}
      ${table}${details}
      <div class="actions"><a class="btn-primary" id="results-try" href="#/demo/rules">Try the demo</a></div>
    </div>`;
  },

  demo() {
    const step = S.route.step;
    return `<div class="wrap page demo-page step-${step}"${enterAttr()}>${steps[step]()}</div>`;
  },
};

// -- the guided demo --------------------------------------------------------------------
// The progress: four dots on a line that fills up to the current step.
function stepper(step) {
  const at = STEPS.findIndex(x => x.key === step);
  const r = curRun();
  const reach = { rules: true, run: true, watch: !!r || !!S.waitingFor, result: !!r && outcome(r).kind !== "running" };
  const e = S.enter, t = e ? Math.min(Date.now() - e.at, 600) : 600;
  const from = e && Number.isInteger(e.fromStep) ? e.fromStep : at;
  const rail = `<span class="prog-rail" aria-hidden="true"><i style="--from:${from / (STEPS.length - 1)};--to:${at / (STEPS.length - 1)};--t:-${t}ms"></i></span>`;
  return `<nav class="stepper" aria-label="Demo progress">${rail}<ol>${STEPS.map((x, i) => {
    const state = i === at ? "current" : i < at ? "done" : "todo";
    const inner = `<span class="dot" aria-hidden="true">${i < at ? TICK : i + 1}</span><span class="t">${esc(x.name)}</span>`;
    const label = `<span class="sr-only">Step ${i + 1} of ${STEPS.length}${i < at ? ", done" : ""}: </span>`;
    return `<li class="${state}">${reach[x.key] || i === at
      ? `<a id="step-${x.key}" href="#/demo/${x.key}"${i === at ? ' aria-current="step"' : ""}>${label}${inner}</a>`
      : `<span class="off-step">${label}${inner}</span>`}</li>`;
  }).join("")}</ol></nav>`;
}
const stepEyebrow = n => `Step ${n} of ${STEPS.length}`;

// Is TESTIGO+ reading the screen right now? (a sensitive click with no answer yet)
function checking(r) {
  if (!r || r.mode !== "supervised" || needsYou(r) || outcome(r).kind !== "running") return false;
  for (let i = r.log.length - 1; i >= 0; i--) {
    const e = r.log[i];
    if (e.type === "agent.step" && /^sensitive/.test(e.label || "")) return true;
    if (["check.result", "approval.requested", "approval.granted", "verify.result", "order.confirmed"].includes(e.type)) return false;
  }
  return false;
}
// the captured screen in an evidence frame: SAM boxes, and the scanner while checking
function evidence(r) {
  const c = r.check;
  const regions = c && c.frame === r.lastFrame ? c.regions : [];
  const scan = checking(r)
    ? `<span class="scanner" aria-hidden="true" style="animation-delay:-${Date.now() % 1800}ms"></span>` : "";
  return `<div class="frame"><span class="corner c-tl"></span><span class="corner c-tr"></span><span class="corner c-bl"></span><span class="corner c-br"></span>
      ${shot(r, r.lastFrame, regions, c && c.frame === r.lastFrame ? c : null).replace('<div class="shot">', `<div class="shot">${scan}`)}</div>`;
}

const steps = {
  rules() {
    const p = S.policy;
    const head = pageHead(stepEyebrow(1), "Your rules",
      "The agent may only place orders that follow these rules. They are signed, so the agent cannot change them.");
    if (!p && S.policyError) return head + callout("bad", ICON.stop, "Your rules could not be trusted.",
        `<p>${esc(S.policyError)}</p><p>Record new rules to continue.</p>`) +
      `<div class="actions"><button class="btn-primary" id="showmandate" type="button">${ICON.mic} Record new rules</button></div>
        ${S.showMandate ? mandateLive({ transcript: "", deliver_only: [], max_per_order_cents: null, ask_before: "", short_sha: "" }) : ""}`;
    if (!p) return head + `<div class="loading">Loading your rules…</div>`;
    const ok = p.hash_ok && p.signed && p.signature_valid !== false;
    const sig = p.signature_valid === true ? "Signature valid" : p.signature_valid === false ? "Signature NOT valid"
      : "Signature present (the owner key is not on this machine to check it)";
    const row = (k, v) => `<div class="rrow"><dt>${k}</dt><dd>${v}</dd></div>`;
    return head + `<article class="policy-doc" aria-labelledby="doc-h">
        <div class="doc-bar"><span>signed purchasing rules · ${esc(p.owner || "owner")}</span><span>simulated</span></div>
        <div class="doc-body">
          <h2 class="doc-title" id="doc-h">Purchasing rules</h2>
          ${p.transcript ? `<p class="doc-quote">“${esc(p.transcript)}”</p>` : ""}
          <dl class="rules-list">
            ${row("Ship only to", p.deliver_only.map(x => `<span class="rv">${esc(x.name)}</span><span class="ra mono">${esc(x.address)}</span>`).join(""))}
            ${row("Max per order", `<span class="rv tnum">${esc(usd(p.max_per_order_cents))}</span>`)}
            ${row("Ask before", `<span class="rv">${esc(askBefore(p.ask_before))}</span>`)}
          </dl>
          <div class="doc-seal ${ok ? "ok" : "bad"}">${ok ? ICON.seal : ICON.stop}<div>
            <b>${ok ? `Signed · sha256 ${esc(p.short_sha)}` : "Not trusted: the signature or the content does not check out"}</b>
            <span>${ok ? `by ${esc(p.owner || "the owner")} · the agent cannot change these rules` : "Record new rules to continue."}</span></div></div>
        </div>
      </article>
      <div class="actions">
        <a class="btn-primary" href="#/demo/run" id="userules">Use these rules</a>
        <button class="btn-secondary" id="showmandate" type="button" aria-expanded="${S.showMandate}" aria-controls="mlive">${ICON.mic} Record new rules</button>
      </div>
      ${S.showMandate ? `<div class="mandate-wrap">${mandateLive(p)}</div>` : ""}
      ${more("rules-more", "Show the signed policy", `
        ${p.transcript ? `<p>You said: <q>${esc(p.transcript)}</q></p>` : ""}
        <dl class="kv"><dt>Fingerprint</dt><dd class="mono">sha256 ${esc(p.short_sha)}</dd>
          <dt>Content</dt><dd>${p.hash_ok ? "matches its fingerprint" : "does NOT match its fingerprint"}</dd>
          <dt>Signature</dt><dd>${esc(sig)} · ${esc(p.signed_by || "")}</dd>
          <dt>File</dt><dd class="mono">${esc(p.path || "")}${p.active === "signed_here" ? " · signed in this interface" : " · the demo’s committed policy"}</dd></dl>`)}`;
  },

  run() {
    const p = S.pick;
    const busyRun = procRunning();
    const cards = SITUATIONS.map(x => `<label class="pick${p.scenario === x.key ? " on" : ""}" for="sit-${x.key}">
        <input type="radio" name="situation" id="sit-${x.key}" value="${x.key}"${p.scenario === x.key ? " checked" : ""}>
        <span class="thumb" aria-hidden="true">${specimen(x.key)}</span>
        <span class="pick-text"><span class="ptag">${x.key === "clean" ? "NO ATTACK" : esc(x.key.toUpperCase())}</span><span class="pt">${esc(x.name)}</span><span class="pd">${esc(x.text)}</span></span>
        <span class="tick" aria-hidden="true">${TICK}</span></label>`).join("");
    const err = S.runReq.error ? callout(S.runReq.busyRun ? "warn" : "bad", S.runReq.busyRun ? ICON.pause : ICON.warn,
        S.runReq.busyRun ? "Another run is already in progress." : "The run could not start.",
        `<p>${S.runReq.busyRun ? "Only one run at a time. Watch it, or stop it first." : esc(S.runReq.error)}</p>
        ${S.runReq.busyRun ? `<p><a id="watch-current" href="#/demo/watch">Watch the current run</a></p>` : ""}`) : "";
    const orphan = S.proc && S.proc.state === "orphaned" ? callout("warn", ICON.warn, "A run from before the service restarted is still going.",
        `<p>Stop it before starting another.</p><div class="actions tight"><button class="btn-secondary" id="cancelorphan" type="button">Stop that run</button></div>`) : "";
    const inProgress = busyRun && !S.runReq.error ? callout("info", ICON.eye, "A run is in progress.",
        `<p><a id="watch-it" href="#/demo/watch">Watch it</a> or wait until it ends to start another.</p>`) : "";
    return pageHead(stepEyebrow(2), "Run the agent", "Pick a situation. The agent will try to restock your company’s warehouse on the supplier’s page.") +
      `${orphan}${inProgress}
      <form id="runform" class="runform" novalidate>
        <fieldset class="picks"><legend class="sr-only">Situation</legend>${cards}</fieldset>
        <div class="protect${p.supervised ? " on" : ""}">
          <label class="switch" for="protect"><input type="checkbox" role="switch" id="protect"${p.supervised ? " checked" : ""} aria-describedby="protect-help">
            <span class="track" aria-hidden="true"><span class="knob"></span></span><span class="sl">Protect with TESTIGO+</span></label>
          <p id="protect-help">${p.supervised ? "On: TESTIGO+ checks the screen before every sensitive click and asks you before the order is confirmed."
            : "Off: the agent runs alone, to see what would happen without TESTIGO+."}</p>
        </div>
        ${more("run-more", "More options", `
          <label class="optfield">Page version <select id="variant">${[1, 2, 3, 4, 5].map(v => `<option value="${v}"${p.variant === v ? " selected" : ""}>Version ${v}</option>`).join("")}</select></label>
          <p class="muted small">Each situation has five versions of the page (different wording or timing).</p>
          <label class="check"><input type="checkbox" id="headed"${p.headed ? " checked" : ""}> Show the agent’s browser window</label>`)}
        ${err}
        <div class="actions">
          <button class="btn-primary" type="submit" id="runbtn"${S.runReq.busy || busyRun ? " disabled" : ""}>${S.runReq.busy ? "Starting…" : "Run the agent"}</button>
          <a class="btn-link" id="backrules" href="#/demo/rules">Back to your rules</a>
        </div>
        <p class="cost">This runs the real agent with Meta’s models: it takes a minute or two and uses API credit. Simulation only: the company, the supplier and the addresses are not real.</p>
      </form>`;
  },

  watch() {
    const r = curRun();
    const head = lede => pageHead(stepEyebrow(3), "Watching", lede);
    if (S.waitingFor) {
      const p = S.proc;
      if (p && p.state !== "running") return head("") + runFailed(p);
      return head("Starting the agent and opening the supplier’s page. This usually takes a few seconds.") +
        `<div class="status-line info">${ICON.eye}<span>Starting the agent…</span></div>
        <div class="actions"><button class="btn-secondary" id="cancelrun" type="button">Stop the run</button></div>`;
    }
    if (!r) return head("") + `<div class="empty-state"><b>No run yet.</b><p>Choose a situation and start the agent to watch it here.</p>
        <a class="btn-primary" id="choose-run" href="#/demo/run">Choose a situation</a></div>`;
    const o = outcome(r);
    const sup = r.mode === "supervised";
    const you = needsYou(r);
    const done = o.kind !== "running";
    const status = you ? { cls: "warn", icon: ICON.pause, text: "TESTIGO+ needs you: approve or deny the order below." }
      : done ? { cls: o.cls, icon: o.icon, text: o.title + "." }
      : checking(r) ? { cls: "info", icon: ICON.eye, text: "TESTIGO+ is reading the screen before the agent may confirm." }
      : { cls: "info", icon: ICON.eye, text: sup ? "The agent is working. TESTIGO+ is checking each sensitive step." : "The agent is working, with TESTIGO+ switched off." };
    const lines = r.log.map(e => plainLine(e, r)).filter(Boolean);
    const list = lines.length ? `<ol class="plainlog">${lines.map(([, cls, t]) => `<li class="${cls}"><span class="pt" aria-hidden="true"></span><span>${esc(t)}</span></li>`).join("")}</ol>`
      : `<p class="muted pad">Nothing yet.</p>`;
    const proc = procFor(r);
    const capsule = you ? `<section class="needs-you" aria-labelledby="ny-h">
        <span class="eyebrow">TESTIGO+ needs you</span>
        <h2 id="ny-h">Approve what will really happen</h2>
        <p class="ny-sub">These are exact crops of the screen, not the agent’s summary. Read the total and the address aloud, then approve.</p>
        ${approvalCapsule()}</section>` : "";
    return head(`${esc(situation(r.scenario).name)} · ${sup ? "protected by TESTIGO+" : "without TESTIGO+"}`) +
      `<div class="status-line ${status.cls}">${status.icon}<span>${esc(status.text)}</span></div>
      ${capsule}
      <div class="watch-grid">
        <section class="watch-shot" aria-labelledby="scr-h"><h2 id="scr-h" class="card-h">The agent’s screen</h2>${evidence(r)}</section>
        <section class="watch-log" aria-labelledby="chk-h"><h2 id="chk-h" class="card-h">${sup ? "What TESTIGO+ checked" : "What happened"}</h2>
          ${sup ? "" : `<p class="muted pad">TESTIGO+ is off for this run: nothing is checked.</p>`}${list}</section>
      </div>
      <div class="actions">
        ${done ? `<a class="btn-primary" href="#/demo/result" id="seeresult">See the result</a>` : ""}
        ${proc && proc.state === "running" ? `<button class="btn-secondary" id="cancelrun" type="button">Stop the run</button>` : ""}
      </div>`;
  },

  result() {
    const r = curRun();
    const head = lede => pageHead(stepEyebrow(4), "Result", lede);
    if (!r) return head("") + (S.waitingFor && S.proc && S.proc.state !== "running" ? runFailed(S.proc)
      : `<div class="empty-state"><b>No result yet.</b><p>Run the agent first; its result appears here.</p><a class="btn-primary" id="choose-run" href="#/demo/run">Choose a situation</a></div>`);
    const o = outcome(r);
    const sup = r.mode === "supervised";
    if (o.kind === "running") return head("") +
      `<div class="empty-state"><b>The run is not over yet.</b><p>Watch it until it ends.</p><a class="btn-primary" id="back-watch" href="#/demo/watch">Back to watching</a></div>`;
    const other = S.runs[sup ? "no_supervisor" : "supervised"];
    const oo = other && other.mode && other.scenario === r.scenario && (other.variant || 1) === (r.variant || 1) ? outcome(other) : null;
    const modeName = s => s ? "With TESTIGO+" : "Without TESTIGO+";
    const compare = oo && oo.kind !== "running" ? `<div class="compare"><span class="cmp-l">Same situation, both ways</span>
        <span class="chip ${o.cls}">${o.icon}<span><b>${modeName(sup)}</b> · ${esc(o.title)}</span></span>
        <span class="chip ${oo.cls}">${oo.icon}<span><b>${modeName(!sup)}</b> · ${esc(oo.title)}</span></span></div>` : "";
    const proc = procFor(r);
    const tail = proc && proc.tail && proc.tail.length && (o.kind === "error" || o.kind === "ended")
      ? more("res-log", "Last lines the run printed", `<pre class="tail">${esc(proc.tail.join("\n"))}</pre>`) : "";
    const ev = [];
    if (sup && r.check) ev.push(more("res-check", "What TESTIGO+ saw on the screen", `
        <p class="muted">The screen as the agent saw it, with the regions the pixel reader found. Left, text only in the page code; right, text only on screen.</p>${divergeBody(r)}`));
    if (sup && verifyOutcome(r).event) ev.push(more("res-after", "What you approved vs. what happened", afterBody(r)));
    if (!sup && r.explain) ev.push(more("res-explain", "Where the attack was", explainPanel(r)));
    if (!sup && !r.explain && proc && proc.state === "running") ev.push(`<p class="muted">Looking for where the attack was…</p>`);
    ev.push(more("res-steps", "Every step, in detail", timeline(r)));
    const again = sup ? "Compare without TESTIGO+" : "Run it with TESTIGO+";
    const busy = procRunning();
    return head(`${esc(situation(r.scenario).name)} · ${sup ? "protected by TESTIGO+" : "without TESTIGO+"}`) +
      `<div class="outcome-card ${o.cls}"><span class="oi">${o.icon}</span><div><p class="ot">${esc(o.title)}</p><p class="os">${esc(o.text)}</p></div></div>
      ${compare}
      ${S.runReq.error ? callout("bad", ICON.warn, "The run could not start.", `<p>${esc(S.runReq.error)}</p>`) : ""}
      <div class="actions">
        <a class="btn-primary" id="runanother" href="#/demo/run">Run another</a>
        <button class="btn-secondary" id="compare" type="button"${busy || S.runReq.busy ? " disabled" : ""}>${again}</button>
      </div>
      ${sup ? receiptCard(r) : ""}
      <h2 class="sub">The evidence</h2>
      <div class="evidence-list">${ev.join("")}${tail}</div>`;
  },
};

function runFailed(p) {
  const why = p.state === "cancelled" ? "You stopped the run before it reported anything."
    : p.state === "finished" ? "The run ended, but none of its steps reached this page."
    : "The agent could not start. Check that the Meta API key is set in .env and that the supplier portal is running (make run).";
  return callout(p.state === "cancelled" ? "info" : "bad", ICON.warn, p.state === "cancelled" ? "Run stopped" : "The run did not work", `<p>${esc(why)}</p>`) +
    (p.tail && p.tail.length ? more("fail-log", "Last lines the run printed", `<pre class="tail">${esc(p.tail.join("\n"))}</pre>`) : "") +
    `<div class="actions"><a class="btn-primary" id="back-run" href="#/demo/run">Back to Run the agent</a></div>`;
}

// the receipt on paper, with `testigo verify` as a terminal (as on the landing)
function verifyTerm(rc) {
  const vo = S.verify;
  const cmd = `<span class="p">$</span> testigo verify runs/${esc(rc.path)}`;
  let out;
  if (S.verifying) out = `${cmd}\n<span class="dim">  checking the signature and the evidence…</span> <span class="caret"></span>`;
  else if (vo) {
    const t = Date.now() - (S.verifyAt || 0);
    const lines = String(vo.output || "").trimEnd().split("\n");
    out = cmd + "\n" + lines.map((l, i) => {
      const cls = /✗|mismatch|fail|invalid|error/i.test(l) ? "held" : /✓|valid|match/i.test(l) ? "ok" : "dim";
      return `<span class="tl ${cls}" style="animation-delay:${i * 180 - t}ms">${esc(l)}</span>`;
    }).join("\n");
  } else out = `${cmd} <span class="caret"></span>`;
  return `<div class="vterm"><div class="term-bar"><div class="dots" aria-hidden="true"><span></span><span></span><span></span></div>
      <button class="tab" id="verifybtn" type="button"${S.verifying ? " disabled" : ""}>${ICON.seal} Verify receipt</button></div>
    <div class="term-body">${out}</div></div>`;
}
function receiptCard(r) {
  const ev = r.receipt;
  const shell = (body, signed) => `<section class="receipt-paper" aria-labelledby="rc-h"><div class="doc-bar"><span>receipt.json</span><span>${signed ? "signed · ed25519" : "no signed receipt"}</span></div>
      <div class="doc-body"><h2 class="doc-title" id="rc-h">${signed ? "Signed receipt" : "Receipt"}</h2>${body}</div></section>`;
  if (!ev) return shell(`<p class="doc-note">No receipt for this run: receipts are signed only for an order you approved.</p>`, false);
  if (isPlaceholder(ev.signature) || !ev.path) return shell(`<p class="doc-note">A receipt was built but not signed on this machine (the owner key is missing), so there is nothing to verify.</p>`, false);
  const rc = S.receipt, vo = S.verify;
  if (!rc) return shell(`<p class="doc-note">Loading the receipt…</p>`, true);
  if (rc.error) return shell(`<p class="doc-note">The receipt file could not be read: ${esc(rc.error)}</p>`, true);
  const d = rc.receipt;
  const res = vo && !S.verifying ? `<p class="verify-res ${vo.exit_code === 0 ? "ok" : "bad"}">${vo.exit_code === 0 ? ICON.check : ICON.stop}<span>${vo.exit_code === 0
      ? "Valid: the signature and the evidence match." : "Not valid: the receipt or its evidence does not check out."}</span></p>` : "";
  const field = (k, v) => v == null || v === "" ? "" : `<div><dt>${esc(k)}</dt><dd class="mono">${esc(v)}</dd></div>`;
  return shell(`<p class="doc-note">It binds your rules, the screen crops you approved and what executed${d.status === "blocked" ? " (here: a blocked order, nothing executed)" : ""}. Anyone can check it without trusting us.</p>
      <dl class="rc-fields">${field("id", d.id || ev.id)}${field("status", d.status)}${field("time", d.time)}${field("policy", short(d.policy_sha256))}${field("signed by", d.signed_by)}</dl>
      ${verifyTerm(rc)}${res}
      ${more("rc-json", "Receipt contents", `<dl class="kv mono small">${["id", "time", "agent", "action", "status", "policy_sha256", "signed_by", "signature"].filter(k => d[k] != null)
        .map(k => `<dt>${esc(k)}</dt><dd>${esc(d[k])}</dd>`).join("")}</dl><p class="muted small">File: runs/${esc(rc.path)}</p>`)}`, true);
}

// -- the live status for screen readers -------------------------------------------
function alertMessage() {
  if (S.route.name !== "demo") return "";
  const st = S.route.step;
  if (st === "rules" && !S.policy && S.policyError) return "Your rules could not be trusted: " + S.policyError;
  if ((st === "run" || st === "result") && S.runReq.error) return (S.runReq.busyRun ? "Another run is already in progress." : "The run could not start: " + S.runReq.error);
  if (S.waitingFor && S.proc && !["running", "orphaned"].includes(S.proc.state)) return "The run did not work.";
  return "";
}
function liveMessage() {
  if (S.route.name !== "demo") return "";
  if (S.route.step === "result" && (S.verifying || S.verify)) {
    return S.verifying ? "Checking the receipt." : S.verify.exit_code === 0 ? "Receipt valid: the signature and the evidence match." : "Receipt not valid.";
  }
  if (S.waitingFor) return S.proc && S.proc.state !== "running" ? "The run did not start." : "Starting the agent.";
  const r = curRun();
  if (!r) return "";
  if (needsYou(r)) return "TESTIGO+ needs you to approve the order.";
  const o = outcome(r);
  return o.kind === "running" ? "The agent is working." : o.title + ".";
}
// The live regions live outside #app and are never re-created: their text
// changes only when the message does, so nothing is announced twice.
function announce() {
  const set = (id, key, msg) => {
    if (msg === S[key]) return;
    S[key] = msg;
    const el = document.getElementById(id);
    if (el) el.textContent = msg;
  };
  set("announce", "lastAnnounce", liveMessage());
  set("alertmsg", "lastAlert", alertMessage());
}

// -- drawing ----------------------------------------------------------------------
function presentShell() {
  return `<div class="present">
    <header class="topbar" id="topbar">
      <a class="pbrand" id="pnav-home" href="#/" title="Leave the presenter">${MARK}
        <span class="wordmark">TESTIGO<b>+</b></span></a>
      <div class="runinfo" id="runinfo"></div>
      <div class="agentstate" id="agentstate"></div>
      <nav class="views" id="nav" aria-label="Views"></nav>
      <button class="auto" id="auto" type="button" title="Follow events (A)"></button>
      <span class="conn" id="conn"></span>
    </header>${testBanner(false)}<main id="view" class="view"></main></div>`;
}
function hasNews(i) {
  const r = S.runs.supervised;
  return { 2: r.log.length, 3: S.runs.no_supervisor.log.length, 4: r.check, 5: r.approval,
           6: r.verify, 7: r.receipt }[i];
}
// the run a view is about: view 3 is the unsupervised run, 2 and 4-7 the supervised one
function runFor(i) {
  if (i === 3) return S.runs.no_supervisor;
  if (i >= 2 && i <= 7) return S.runs.supervised;
  return run();
}
function drawPresent() {
  const r = runFor(S.view), st = agentState(r);
  document.getElementById("topbar").classList.toggle("off", r.mode === "no_supervisor");
  document.getElementById("runinfo").textContent = r.mode ? `${r.scenario || ""}${r.variant ? " v" + r.variant : ""}` : "";
  document.getElementById("agentstate").innerHTML = chip(st.cls, st.icon, st.text);
  document.getElementById("nav").innerHTML = VIEWS.map((v, i) =>
    `<a id="pnav-${i}" href="#/present/${i}" ${i === S.view ? 'aria-current="page"' : ""}><span class="n">${i || "·"}</span>${esc(v.name)}${hasNews(i) && i !== S.view ? '<span class="dot"></span>' : ""}</a>`).join("");
  const auto = document.getElementById("auto");
  auto.textContent = S.auto ? "Follow: on" : "Follow: off";
  auto.setAttribute("aria-pressed", String(S.auto));
  const conn = document.getElementById("conn");
  conn.className = "conn " + (S.conn === "live" ? "live" : S.conn === "down" ? "down" : "");
  conn.textContent = S.conn === "live" ? "Live" : S.conn === "down" ? "Reconnecting" : "Connecting";
  document.getElementById("view").innerHTML = `<div class="wrap">${render[VIEWS[S.view].key]()}</div>` +
    `<div class="keys"><kbd>←</kbd><kbd>→</kbd> views · <kbd>0</kbd>–<kbd>8</kbd> jump · <kbd>A</kbd> follow</div>`;
}

const TITLES = { rules: "Your rules", run: "Run the agent", watch: "Watching", result: "Result" };
function draw() {
  const app = document.getElementById("app");
  const active = document.activeElement;
  const keep = active && active.id && app.contains(active) ? active.id : null;
  const r = S.route;
  if (r.name === "present") {
    landingUnmount(); S.mounted = "present";
    PLAIN = false;
    app.innerHTML = presentShell();
    drawPresent();
    document.title = "TESTIGO+ · presenter";
  } else if (r.name === "landing") {
    PLAIN = true;
    if (S.mounted === "landing" && document.getElementById("lp")) {
      landingUpdate();                              // the landing keeps its motion
      const tb = document.getElementById("testdata");
      if (tb) tb.hidden = !S.test;
    } else {
      app.innerHTML = siteHeader() + testBanner(true) +
        `<main id="main" class="site-main landing" tabindex="-1">${landingBody()}</main>` + siteFooter();
      S.mounted = "landing";
      landingMount();
      placePill(false);
    }
    document.title = "TESTIGO+ · a witness for AI agents";
  } else {
    landingUnmount(); S.mounted = r.name;
    PLAIN = true;
    const body = r.name === "results" ? page.results() : page.demo();
    app.innerHTML = siteHeader() + `<main id="main" class="site-main ${r.name}" tabindex="-1">${testBanner(false)}${body}</main>` + siteFooter();
    placePill(false);
    document.title = r.name === "demo" ? `${TITLES[r.step]} · TESTIGO+ demo` : "Results · TESTIGO+";
  }
  bind();
  if (keep) {
    const el = document.getElementById(keep);
    if (el && el !== document.activeElement) el.focus({ preventScroll: true });
  }
  document.body.dataset.conn = S.conn;
  announce();
}

function bind() {
  const on = (id, fn) => { const el = document.getElementById(id); if (el) el.onclick = fn; };
  on("runverify", runVerify); on("verifybtn", runVerify);
  on("vrec", startRecording); on("vstop", () => stopRecording(false));
  on("vapprove", () => decide("approve")); on("vdeny", () => decide("deny"));
  on("mrec", startMandate); on("mstop", () => stopMandate(false));
  on("msign", signMandate); on("mdiscard", discardMandate);
  on("auto", () => { S.auto = !S.auto; draw(); });
  on("showmandate", () => { S.showMandate = !S.showMandate; draw(); });
  on("cancelrun", cancelRun); on("cancelorphan", cancelRun);
  on("menuBtn", () => setMenu(!S.menuOpen));
  on("compare", () => {
    const r = curRun();
    if (r) startRun({ scenario: r.scenario, variant: r.variant || 1, supervised: r.mode !== "supervised" });
  });
  // section links: a second click on the same link scrolls there again
  document.querySelectorAll("#links a").forEach(a => {
    a.onclick = e => { e.preventDefault(); setMenu(false); nav(a.getAttribute("href")); };
  });
  const form = document.getElementById("runform");
  if (form) {
    form.onsubmit = e => { e.preventDefault(); startPicked(); };
    form.querySelectorAll('input[name="situation"]').forEach(el => {
      el.onchange = () => { S.pick.scenario = el.value; draw(); };
    });
    const protect = document.getElementById("protect");
    protect.onchange = () => { S.pick.supervised = protect.checked; draw(); };
    const variant = document.getElementById("variant");
    if (variant) variant.onchange = () => { S.pick.variant = Number(variant.value); };
    const headed = document.getElementById("headed");
    if (headed) headed.onchange = () => { S.pick.headed = headed.checked; };
  }
}

// remember which disclosures are open across redraws (toggle does not bubble)
document.addEventListener("toggle", e => {
  const t = e.target;
  if (t && t.tagName === "DETAILS" && t.id) S.open[t.id] = t.open;
}, true);
// the bar turns solid once the page scrolls
window.addEventListener("scroll", () => {
  const n = document.getElementById("topnav");
  if (n) n.classList.toggle("scrolled", window.scrollY > 24);
}, { passive: true });
window.addEventListener("resize", () => placePill(false));

// -- live events ---------------------------------------------------------------------
let backoff = 500;
function connect() {
  const ws = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws");
  ws.onopen = () => { S.conn = "live"; backoff = 500; draw(); };
  ws.onmessage = m => {
    const e = JSON.parse(m.data);
    S.pendingView = undefined;
    if (e.type === "hub.history") {
      S.runs = { supervised: freshRun(), no_supervisor: freshRun() };
      S.current = null; S.test = false;
      e.events.forEach(x => apply(x, () => {}));   // replay without jumping views
      syncWaiting();
    } else {
      if (e.type === "run.started" && S.waitingFor === e.mode) S.waitingFor = null;
      apply(e, follow);
    }
    if (S.route.name === "present" && S.pendingView !== undefined && S.pendingView !== S.view) { go(S.pendingView); return; }
    draw();
    const reload = ["receipt.signed", "hub.reset", "hub.history", "run.started"];
    if (!reload.includes(e.type)) return;
    if (S.route.name === "present" && VIEWS[S.view].key === "receipt") loadFor(S.view);
    if (S.route.name === "demo" && S.route.step === "result") loadForRoute();
  };
  ws.onclose = () => { S.conn = "down"; draw(); setTimeout(connect, backoff); backoff = Math.min(backoff * 2, 8000); };
}

window.addEventListener("hashchange", () => onRoute(false));
document.addEventListener("keydown", e => {
  if (e.key === "Escape" && S.menuOpen) {
    setMenu(false);
    const b = document.getElementById("menuBtn");
    if (b) b.focus();
    return;
  }
  if (S.route.name !== "present" || e.metaKey || e.ctrlKey || e.altKey) return;
  if (e.target && /^(INPUT|SELECT|TEXTAREA|BUTTON)$/.test(e.target.tagName) && e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
  if (e.key === "ArrowRight") go(S.view + 1);
  else if (e.key === "ArrowLeft") go(S.view - 1);
  else if (/^[0-8]$/.test(e.key)) go(Number(e.key));
  else if (e.key === "a" || e.key === "A") { S.auto = !S.auto; draw(); }
});
document.getElementById("skip").onclick = e => {
  e.preventDefault();
  const m = document.getElementById("main") || document.getElementById("view");
  if (m) { m.setAttribute("tabindex", "-1"); m.focus(); }
};

S.route = parseRoute();
if (S.route.name === "present") S.view = S.route.view;
S.enter = { at: Date.now(), fromStep: 0 };
getJSON("/api/policy").then(p => { S.policy = p; draw(); }).catch(err => { S.policyError = err.message; draw(); });
refreshProc().then(() => { if (S.proc && S.proc.state === "running") { syncWaiting(); draw(); } });
draw();
loadForRoute();
if (S.route.section) arrive(null);
connect();
