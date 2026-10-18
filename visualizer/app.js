/* The Enigma Attack Bench page: key sheet, machine, sweep, climb, verdict. */
(function () {
  "use strict";

  const C = EnigmaCore;
  const D = ENIGMA_DATA;
  const $ = (id) => document.getElementById(id);
  const SVGNS = "http://www.w3.org/2000/svg";
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const scorer = new C.NgramScorer(D.scorer);
  const WHEELS = Object.keys(D.rotors);
  const STARTS = 17576;
  const RANDOM_IC = 1 / 26;

  const groups5 = (s) => (s.match(/.{1,5}/g) || []).join(" ");
  const fmt = (v, digits = 4) => v.toFixed(digits);
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  const startName = (s) => C.ch(Math.floor(s / 676)) + C.ch(Math.floor(s / 26)) + C.ch(s);
  const startIndex = (p) => C.idx(p[0]) * 676 + C.idx(p[1]) * 26 + C.idx(p[2]);
  /** Two starts are the same key when the first key press brings them to the same positions. */
  function afterFirstPress(positions) {
    const m = new C.Machine(D, { rotors: key.rotors, rings: key.rings, positions });
    m.step();
    return m.positions;
  }
  const sameKey = (a, b) => a === b || afterFirstPress(a) === afterFirstPress(b);
  const plugCount = (n) => `${n} plug${n === 1 ? "" : "s"}`;

  function icOfText(text) {
    const counts = new Array(26).fill(0);
    for (const c of text) counts[C.idx(c)]++;
    return C.indexOfCoincidence(counts, text.length);
  }

  function el(tag, attrs, parent) {
    const node = document.createElementNS(SVGNS, tag);
    for (const k in attrs) node.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(node);
    return node;
  }
  function svgText(parent, x, y, text, attrs = {}) {
    const t = el("text", { x, y, ...attrs }, parent);
    t.textContent = text;
    return t;
  }

  // ------------------------------------------------------------------ key sheet

  let key = null;

  function demoKey() {
    const d = D.demo;
    return {
      rotors: d.rotors.slice(),
      rings: d.rings,
      grund: d.grundstellung,
      msgKey: d.message_key,
      plugboard: d.plugboard,
      plaintext: d.plaintext,
    };
  }

  function fillForm(k) {
    ["key-l", "key-m", "key-r"].forEach((id, i) => ($(id).value = k.rotors[i]));
    $("key-rings").value = k.rings;
    $("key-grund").value = k.grund;
    $("key-msg").value = k.msgKey;
    $("key-plugs").value = k.plugboard;
    $("key-plain").value = k.plaintext;
  }

  function readForm() {
    const up = (id) => $(id).value.toUpperCase().trim();
    const k = {
      rotors: ["key-l", "key-m", "key-r"].map((id) => $(id).value),
      rings: up("key-rings"),
      grund: up("key-grund"),
      msgKey: up("key-msg"),
      plugboard: up("key-plugs").split(/[^A-Z]+/).filter(Boolean).join(" "),
      plaintext: up("key-plain").replace(/[^A-Z]/g, ""),
    };
    if (new Set(k.rotors).size !== 3) throw new Error("Choose three different wheels.");
    for (const [label, v] of [["Ring setting", k.rings], ["Grundstellung", k.grund], ["Message key", k.msgKey]]) {
      if (!/^[A-Z]{3}$/.test(v)) throw new Error(`${label} needs exactly three letters.`);
    }
    try {
      C.plugmap(k.plugboard);
    } catch (e) {
      throw new Error(`Plugboard: ${e.message}. Write pairs like AN BY CF.`);
    }
    if (k.plaintext.length < 26) throw new Error("Give the plaintext at least 26 letters so the attack has something to measure.");
    return k;
  }

  function machineFor(k, positions, plugboard = k.plugboard) {
    return new C.Machine(D, { rotors: k.rotors, rings: k.rings, positions, plugboard });
  }

  function applyKey(k) {
    key = k;
    key.pairs = k.plugboard.split(" ").filter(Boolean);
    key.indicator = machineFor(k, k.grund).crypt(k.msgKey);
    key.ciphertext = machineFor(k, k.msgKey).crypt(k.plaintext);
    $("sent-text").textContent = `${k.grund} ${key.indicator}   ${groups5(key.ciphertext)}`;
    $("sent-note").textContent =
      `Indicator: the Grundstellung ${k.grund} in the clear, then the message key ${k.msgKey} enciphered from it as ${key.indicator}. ` +
      `Then ${key.ciphertext.length} letters of body in five-letter groups.`;
    const slider = $("sweep-plugs");
    slider.max = String(key.pairs.length);
    slider.value = String(key.pairs.length);
    loadMode(panel.mode);
    renderKeyspace();
    resetSweep(true);
  }

  // ------------------------------------------------------------------ machine

  const panel = { mode: "encipher", machine: null, input: "", cursor: 0, output: "", last: null, custom: false, timer: null };
  const G = {
    top: 76,
    row: 15,
    label: 22,
    plug: [44, 120],
    R: [160, 250],
    M: [290, 380],
    L: [420, 510],
    U: [550, 616],
    width: 640,
  };
  const yOf = (i) => G.top + i * G.row + G.row / 2;
  const PAD = 14; // room for each wheel's letter ring

  function modeSpec(mode) {
    if (mode === "indicator") {
      return {
        positions: key.grund,
        input: key.msgKey,
        inLabel: "Message key",
        outLabel: "Enciphered key",
        note: `Since 1940 the Army operator sets the wheels to a Grundstellung he picks himself (${key.grund}), types his chosen message key (${key.msgKey}) once, and sends the Grundstellung in the clear followed by the three lamps that lit. The receiver does the same in reverse to learn ${key.msgKey}.`,
      };
    }
    if (mode === "encipher") {
      return {
        positions: key.msgKey,
        input: key.plaintext,
        inLabel: "Plaintext typed",
        outLabel: "Ciphertext lit",
        note: `Wheels set to the message key ${key.msgKey}. Each key press steps the wheels before the current flows, so a letter enciphers differently every time. The current returns by a different path, so no letter can ever encipher to itself.`,
      };
    }
    return {
      positions: key.msgKey,
      input: key.ciphertext,
      inLabel: "Ciphertext typed",
      outLabel: "Plaintext lit",
      note: `The receiver sets the same wheels to ${key.msgKey} and types the ciphertext. The reflector makes every position of the machine its own inverse, so the same key turns ciphertext back into plaintext.`,
    };
  }

  function loadMode(mode) {
    stopPlay();
    panel.mode = mode;
    const spec = modeSpec(mode);
    panel.machine = machineFor(key, spec.positions);
    panel.input = spec.input;
    panel.cursor = 0;
    panel.output = "";
    panel.last = null;
    panel.custom = false;
    for (const m of ["indicator", "encipher", "decipher"]) $(`mode-${m}`).setAttribute("aria-pressed", String(m === mode));
    $("mode-note").textContent = spec.note;
    $("tape-in-label").textContent = spec.inLabel;
    $("tape-out-label").textContent = spec.outLabel;
    $("step-note").textContent = `Wheels at ${spec.positions}. Press a key to send current through the machine.`;
    drawMachine(null, false);
    renderTrace(null);
    renderTapes();
    lightLamp(null);
  }

  function speed() {
    return Number($("m-speed").value);
  }

  function pressNext(animate) {
    if (panel.cursor >= panel.input.length) return false;
    const c = panel.input[panel.cursor];
    const trace = panel.machine.press(c);
    panel.output += trace.output;
    panel.cursor++;
    panel.last = trace;
    if (animate) {
      drawMachine(trace, !reduceMotion && speed() > 0);
      renderTrace(trace);
      renderStepNote(trace, c);
      renderTapes();
      flashKey(c);
    }
    return true;
  }

  function renderAll() {
    drawMachine(panel.last, false);
    renderTrace(panel.last);
    if (panel.last) renderStepNote(panel.last, panel.input[panel.cursor - 1]);
    renderTapes();
  }

  function stopPlay() {
    if (panel.timer) clearTimeout(panel.timer);
    panel.timer = null;
    $("m-play").textContent = "Play";
  }

  function play() {
    if (panel.timer) return stopPlay();
    if (panel.cursor >= panel.input.length) loadMode(panel.mode);
    if (speed() === 0) {
      while (pressNext(false));
      renderAll();
      return;
    }
    $("m-play").textContent = "Pause";
    const tick = () => {
      if (!pressNext(true)) return stopPlay();
      panel.timer = setTimeout(tick, speed());
    };
    tick();
  }

  function typeLetter(c) {
    stopPlay();
    panel.input = panel.input.slice(0, panel.cursor) + c;
    panel.custom = true;
    pressNext(true);
  }

  function renderStepNote(trace, c) {
    const m = panel.machine;
    const s = trace.stepped;
    const parts = [`Key ${c} pressed. The right wheel stepped first`];
    if (s.rightNotch) {
      parts.push(`; it was at its turnover letter ${D.rotors[m.R.name][1]}, so the middle wheel stepped too`);
    }
    if (s.middleNotch) {
      parts.push(
        `; the middle wheel was at its own turnover letter ${D.rotors[m.M.name][1]}, so it stepped once and carried the left wheel with it. ` +
          `A middle wheel carried onto its turnover by the right wheel steps again on the very next press: the double step`
      );
    }
    parts.push(`. Wheels now read ${m.positions}; lamp ${trace.output} lit.`);
    $("step-note").textContent = parts.join("");
  }

  function renderTrace(trace) {
    const host = $("trace");
    host.innerHTML = "";
    if (!trace) return;
    const [k, p1, r1, m1, l1, u, l2, m2, r2, out] = trace.contacts.map(C.ch);
    const m = panel.machine;
    const cells = [
      ["Key", k, "f"],
      ["Plugboard", `${k}→${p1}`, "f"],
      [`Wheel ${m.R.name}`, `${p1}→${r1}`, "f"],
      [`Wheel ${m.M.name}`, `${r1}→${m1}`, "f"],
      [`Wheel ${m.L.name}`, `${m1}→${l1}`, "f"],
      ["UKW-B", `${l1}→${u}`, "f"],
      [`Wheel ${m.L.name}`, `${u}→${l2}`, "r"],
      [`Wheel ${m.M.name}`, `${l2}→${m2}`, "r"],
      [`Wheel ${m.R.name}`, `${m2}→${r2}`, "r"],
      ["Plugboard", `${r2}→${out}`, "r"],
      ["Lamp", out, "l"],
    ];
    for (const [label, value, dir] of cells) {
      const cell = document.createElement("div");
      cell.className = `cell ${dir}`;
      cell.innerHTML = `<span>${esc(label)}</span><b>${esc(value)}</b>`;
      host.appendChild(cell);
    }
  }

  function renderTapes() {
    const fill = (host, text, count, cursor) => {
      host.innerHTML = "";
      for (let i = 0; i < text.length; i++) {
        const span = document.createElement("span");
        span.textContent = text[i];
        if (i < count) span.className = i === cursor ? "cur" : "done";
        host.appendChild(span);
        if (i % 5 === 4) host.appendChild(document.createTextNode(" "));
      }
    };
    fill($("tape-in"), panel.input, panel.cursor, panel.cursor - 1);
    fill($("tape-out"), panel.output, panel.output.length, panel.output.length - 1);
    const status = $("tape-status");
    const finished = panel.cursor >= panel.input.length;
    let html = "";
    if (panel.custom) {
      html = `<span class="chip wait">Your own text</span> <button type="button" id="tape-restore">Restore the message</button>`;
    } else if (!finished) {
      html = `<span class="chip wait">${panel.cursor} of ${panel.input.length} keys pressed</span>`;
    } else if (panel.mode === "decipher") {
      html = panel.output === key.plaintext
        ? `<span class="chip ok">Matches the plaintext letter for letter</span>`
        : `<span class="chip bad">Does not match the plaintext</span>`;
    } else if (panel.mode === "encipher") {
      html = panel.output === key.ciphertext
        ? `<span class="chip ok">This is the ciphertext on the key sheet</span>`
        : `<span class="chip bad">Differs from the key sheet</span>`;
    } else {
      html = `<span class="chip ok">Indicator to send: ${esc(key.grund)} ${esc(panel.output)}</span>`;
    }
    status.innerHTML = html;
    const restore = $("tape-restore");
    if (restore) restore.addEventListener("click", () => loadMode(panel.mode));
  }

  function drawMachine(trace, animate) {
    const svg = $("wiring");
    const height = G.top + 26 * G.row + 14;
    svg.setAttribute("viewBox", `0 0 ${G.width} ${height}`);
    svg.innerHTML = "";
    const m = panel.machine;
    const moved = trace ? trace.stepped : {};

    // Letter column: keys and lamps.
    svgText(svg, G.label, 40, "Keys", { "text-anchor": "middle", "font-size": 10, class: "faint" });
    svgText(svg, G.label, 52, "lamps", { "text-anchor": "middle", "font-size": 10, class: "faint" });
    const inK = trace ? trace.contacts[0] : -1;
    const outK = trace ? trace.contacts[9] : -1;
    const labelGroup = el("g", {}, svg);
    for (let i = 0; i < 26; i++) {
      const isKey = i === inK;
      const isLamp = i === outK;
      if (isKey || isLamp) {
        el("circle", { cx: G.label, cy: yOf(i), r: 7, class: isKey ? "key-dot" : "lamp-dot", "data-lamp": isLamp ? "1" : "0" }, labelGroup);
      }
      svgText(labelGroup, G.label, yOf(i) + 3.5, C.ch(i), { "text-anchor": "middle", "font-size": 10 });
    }

    // Plugboard.
    el("rect", { x: G.plug[0], y: G.top - 4, width: G.plug[1] - G.plug[0], height: 26 * G.row + 8, class: "box" }, svg);
    svgText(svg, (G.plug[0] + G.plug[1]) / 2, 16, "Plugboard", { "text-anchor": "middle", "font-size": 11 });
    svgText(svg, (G.plug[0] + G.plug[1]) / 2, 30, `${key.pairs.length} pairs`, { "text-anchor": "middle", "font-size": 10, class: "faint" });
    for (let i = 0; i < 26; i++) {
      el("line", { x1: G.plug[0], y1: yOf(i), x2: G.plug[1], y2: yOf(m.plug[i]), class: "wire" }, svg);
    }

    // Wheels, with each wheel's letter ring drawn above the current.
    const ringGroup = el("g", {});
    for (const [slot, rotor, hasMoved] of [["R", m.R, moved.right], ["M", m.M, moved.middle], ["L", m.L, moved.left]]) {
      const [x0, x1] = G[slot];
      const mid = (x0 + x1) / 2;
      svgText(svg, mid, 16, `Wheel ${rotor.name}`, { "text-anchor": "middle", "font-size": 11 });
      el("rect", { x: mid - 13, y: 22, width: 26, height: 26, class: hasMoved ? "win moved" : "win" }, svg);
      svgText(svg, mid, 41, C.ch(rotor.pos), { "text-anchor": "middle", "font-size": 16, "font-weight": 600 });
      const place = slot === "R" ? "right" : slot === "M" ? "middle" : "left";
      svgText(svg, mid, 62, `${place} · ring ${C.ch(rotor.ring)}`, { "text-anchor": "middle", "font-size": 9, class: "faint" });
      el("rect", { x: x0, y: G.top - 4, width: x1 - x0, height: 26 * G.row + 8, class: "box" }, svg);
      for (let i = 0; i < 26; i++) {
        svgText(ringGroup, x0 + 7, yOf(i) + 3, C.ch(i + rotor.pos), { "text-anchor": "middle", "font-size": 8, class: "faint ringlbl" });
        el("line", { x1: x0 + PAD, y1: yOf(i), x2: x1, y2: yOf(rotor.fwd(i)), class: "wire" }, svg);
      }
    }

    // Reflector.
    const [u0, u1] = G.U;
    svgText(svg, (u0 + u1) / 2, 16, "UKW-B", { "text-anchor": "middle", "font-size": 11 });
    svgText(svg, (u0 + u1) / 2, 30, "reflector", { "text-anchor": "middle", "font-size": 10, class: "faint" });
    el("rect", { x: u0, y: G.top - 4, width: u1 - u0, height: 26 * G.row + 8, class: "box" }, svg);
    const bulge = (a, b) => 8 + ((u1 - u0 - 14) * Math.abs(a - b)) / 25;
    const arc = (a, b, dy = 0) =>
      `C ${u0 + bulge(a, b)} ${yOf(a) + dy} ${u0 + bulge(a, b)} ${yOf(b) + dy} ${u0} ${yOf(b) + dy}`;
    for (let i = 0; i < 26; i++) {
      const j = m.reflector[i];
      if (j > i) el("path", { d: `M ${u0} ${yOf(i)} ${arc(i, j)}`, class: "wire" }, svg);
    }

    if (!trace) {
      svg.appendChild(ringGroup);
      return;
    }
    const [k, p1, r1, m1, l1, u, l2, m2, r2, out] = trace.contacts;
    const f = -2;
    const r = 2;
    const P = (x, i, dy) => `${x} ${yOf(i) + dy}`;
    const forward = [
      `M ${P(G.label + 8, k, f)}`,
      `L ${P(G.plug[0], k, f)}`, `L ${P(G.plug[1], p1, f)}`,
      `L ${P(G.R[0] + PAD, p1, f)}`, `L ${P(G.R[1], r1, f)}`,
      `L ${P(G.M[0] + PAD, r1, f)}`, `L ${P(G.M[1], m1, f)}`,
      `L ${P(G.L[0] + PAD, m1, f)}`, `L ${P(G.L[1], l1, f)}`,
      `L ${P(u0, l1, f)}`, arc(l1, u, f),
    ].join(" ");
    const back = [
      `M ${P(u0, u, r)}`,
      `L ${P(G.L[1], u, r)}`, `L ${P(G.L[0] + PAD, l2, r)}`,
      `L ${P(G.M[1], l2, r)}`, `L ${P(G.M[0] + PAD, m2, r)}`,
      `L ${P(G.R[1], m2, r)}`, `L ${P(G.R[0] + PAD, r2, r)}`,
      `L ${P(G.plug[1], r2, r)}`, `L ${P(G.plug[0], out, r)}`,
      `L ${P(G.label + 8, out, r)}`,
    ].join(" ");
    const pf = el("path", { d: forward, class: "sig-f" }, svg);
    const pr = el("path", { d: back, class: "sig-r" }, svg);
    svg.appendChild(ringGroup); // keep letters above the current
    svg.appendChild(labelGroup);
    const lampDot = labelGroup.querySelector('[data-lamp="1"]');
    if (!animate) {
      lightLamp(trace.output);
      return;
    }
    // Both halves and the lamp fit inside one key interval, so even at Fast the
    // return path finishes and the lamp lights before the next press clears them.
    const half = Math.min(700, speed() * 0.3);
    for (const [path, delay] of [[pf, 0], [pr, half]]) {
      const len = path.getTotalLength();
      path.style.strokeDasharray = `${len}`;
      path.style.strokeDashoffset = `${len}`;
      path.getBoundingClientRect();
      path.style.transition = `stroke-dashoffset ${half}ms linear ${delay}ms`;
      path.style.strokeDashoffset = "0";
    }
    if (lampDot) {
      lampDot.style.opacity = "0";
      lampDot.style.transition = `opacity 80ms linear ${2 * half}ms`;
      lampDot.getBoundingClientRect();
      lampDot.style.opacity = "1";
    }
    lightLamp(null);
    const token = trace;
    setTimeout(() => {
      if (panel.last === token) lightLamp(trace.output);
    }, 2 * half);
  }

  const BOARD_ROWS = ["QWERTZUIO", "ASDFGHJK", "PYXCVBNML"];

  function buildBoards() {
    for (const [hostId, cls] of [["lamps", "lamp"], ["keys", "kb"]]) {
      const host = $(hostId);
      host.style.display = "grid";
      host.style.gap = "6px";
      for (const row of BOARD_ROWS) {
        const r = document.createElement("div");
        r.className = "krow";
        for (const c of row) {
          const node = document.createElement(cls === "kb" ? "button" : "div");
          node.className = cls;
          node.id = `${cls}-${c}`;
          node.textContent = c;
          if (cls === "kb") {
            node.type = "button";
            node.setAttribute("aria-label", `Press ${c}`);
            node.addEventListener("click", () => typeLetter(c));
          }
          r.appendChild(node);
        }
        host.appendChild(r);
      }
    }
  }

  function lightLamp(c) {
    document.querySelectorAll(".lamp.lit").forEach((n) => n.classList.remove("lit"));
    if (c) $(`lamp-${c}`).classList.add("lit");
  }

  function flashKey(c) {
    const node = $(`kb-${c}`);
    node.classList.add("down");
    setTimeout(() => node.classList.remove("down"), Math.max(90, Math.min(300, speed() * 0.4)));
  }

  // ------------------------------------------------------------------ keyspace

  function plugboardCount(pairs) {
    let n = 1n;
    for (let i = 0; i < 2 * pairs; i++) n *= BigInt(26 - i);
    let d = 1n;
    for (let i = 2; i <= pairs; i++) d *= BigInt(i);
    return n / (d * 2n ** BigInt(pairs));
  }

  function renderKeyspace() {
    const pairs = key.pairs.length;
    const plugs = plugboardCount(pairs);
    // The left wheel's ring only shifts its start, so 26 ring and start pairs act alike.
    const total = 60n * 26n ** 5n * plugs;
    const sci = (big) => {
      const s = big.toString();
      return `${s[0]}.${s.slice(1, 3)} × 10<sup>${s.length - 1}</sup>`;
    };
    $("keyspace").innerHTML = [
      ["Wheel orders from I–V", "60"],
      ["Ring settings", "17,576"],
      ["Start positions (message key)", "17,576"],
      [`Plugboards with ${pairs} pairs`, plugs.toLocaleString("en-US")],
    ]
      .map(([l, v]) => `<div><span class="label">${esc(l)}</span><b>${esc(v)}</b></div>`)
      .join("") + `<div class="times"><span class="label">Distinct settings for one message</span><b>${sci(total)}</b></div>`;
  }

  // ------------------------------------------------------------------ stage 1

  const sweep = { plugs: 10, body: null, values: null, done: 0, running: false, token: 0, best: null };

  function senderBoard(count) {
    return key.pairs.slice(0, count).join(" ");
  }

  function attackCipher(count) {
    return machineFor(key, key.msgKey, senderBoard(count)).crypt(key.plaintext);
  }

  function resetSweep(autoRun) {
    sweep.token++;
    sweep.running = false;
    sweep.plugs = Number($("sweep-plugs").value);
    $("sweep-plugs-v").textContent = String(sweep.plugs);
    $("sweep-plugs-note").textContent = sweep.plugs === key.pairs.length
      ? `The full key-sheet plugboard.`
      : `Only the first ${sweep.plugs} of the key sheet's ${key.pairs.length} pairs: ${senderBoard(sweep.plugs) || "no plugs"}.`;
    sweep.body = C.textToIndices(attackCipher(sweep.plugs));
    sweep.values = new Float64Array(STARTS);
    sweep.done = 0;
    sweep.best = null;
    $("sweep-progress").style.width = "0";
    $("sweep-run").disabled = false;
    drawSweep();
    resetClimb();
    if (autoRun) runSweep();
  }

  function runSweep() {
    if (sweep.running) return;
    if (sweep.done >= STARTS) {
      // The same ciphertext again: the top start, and any climb from it, stay valid.
      sweep.values = new Float64Array(STARTS);
      sweep.done = 0;
    }
    sweep.running = true;
    $("sweep-run").disabled = true;
    const token = sweep.token;
    const chunk = 700;
    const tick = () => {
      if (token !== sweep.token) return;
      const end = Math.min(STARTS, sweep.done + chunk);
      sweep.values.set(C.sweepStarts(D, key.rotors, key.rings, sweep.body, sweep.done, end), sweep.done);
      sweep.done = end;
      $("sweep-progress").style.width = `${(100 * end) / STARTS}%`;
      if (end < STARTS) {
        drawSweep();
        requestAnimationFrame(tick);
      } else {
        sweep.running = false;
        $("sweep-run").disabled = false;
        finishSweep();
      }
    };
    requestAnimationFrame(tick);
  }

  function finishSweep() {
    let best = 0;
    for (let s = 1; s < STARTS; s++) if (sweep.values[s] > sweep.values[best]) best = s;
    sweep.best = best;
    drawSweep();
    updateClimbChoices(); // a climb from the sender's start keeps its result
  }

  function drawSweep() {
    const svg = $("sweep-hist");
    svg.innerHTML = "";
    const W = 640;
    const H = 240;
    const L = 46;
    const R = 16;
    const T = 26;
    const B = 34;
    const n = sweep.done;
    const truth = startIndex(key.msgKey);
    const plainIC = icOfText(key.plaintext);
    const lo = 0.025;
    const hi = Math.max(0.085, plainIC + 0.005);
    const bins = 60;
    const counts = new Array(bins).fill(0);
    for (let s = 0; s < n; s++) {
      const b = Math.min(bins - 1, Math.max(0, Math.floor(((sweep.values[s] - lo) / (hi - lo)) * bins)));
      counts[b]++;
    }
    const maxCount = Math.max(10, ...counts);
    const x = (v) => L + ((v - lo) / (hi - lo)) * (W - L - R);
    const y = (c) => H - B - (c / maxCount) * (H - T - B);
    const nice = maxCount > 2000 ? 1000 : maxCount > 800 ? 400 : maxCount > 200 ? 100 : 20;
    for (let c = 0; c <= maxCount; c += nice) {
      el("line", { x1: L, x2: W - R, y1: y(c), y2: y(c), class: "grid" }, svg);
      svgText(svg, L - 6, y(c) + 3, c.toLocaleString("en-US"), { "text-anchor": "end" });
    }
    const bw = (W - L - R) / bins;
    counts.forEach((c, i) => {
      if (c) el("rect", { x: L + i * bw + 0.5, y: y(c), width: Math.max(1, bw - 1), height: H - B - y(c), class: "bar" }, svg);
    });
    el("line", { x1: L, x2: W - R, y1: H - B, y2: H - B, class: "axis" }, svg);
    for (let v = 0.03; v <= hi + 1e-9; v += 0.01) {
      el("line", { x1: x(v), x2: x(v), y1: H - B, y2: H - B + 4, class: "axis" }, svg);
      svgText(svg, x(v), H - B + 16, v.toFixed(2), { "text-anchor": "middle" });
    }
    svgText(svg, (L + W - R) / 2, H - 4, "index of coincidence of the unplugged decryption", { "text-anchor": "middle" });
    svgText(svg, L - 6, T - 12, "starts", { "text-anchor": "end" });
    for (const [v, label] of [[RANDOM_IC, "random 0.0385"], [plainIC, `plaintext ${fmt(plainIC, 3)}`]]) {
      el("line", { x1: x(v), x2: x(v), y1: T - 6, y2: H - B, class: "ref" }, svg);
      svgText(svg, x(v) - 4, T + 2, label, { "text-anchor": "end", class: "ref-t halo" });
    }
    if (n > truth) {
      const v = sweep.values[truth];
      const right = x(v) < W * 0.75;
      el("line", { x1: x(v), x2: x(v), y1: T + 30, y2: H - B, class: "hot" }, svg);
      svgText(svg, x(v) + (right ? 5 : -5), T + 40, `sender's start ${key.msgKey}`, {
        "text-anchor": right ? "start" : "end",
        class: "hot-t halo",
      });
    }
    renderSweepStats();
  }

  function renderSweepStats() {
    const n = sweep.done;
    const truth = startIndex(key.msgKey);
    const dl = $("sweep-stats");
    const tbody = $("sweep-top");
    if (n < STARTS) {
      dl.innerHTML = `<dt>Starts scored</dt><dd>${n.toLocaleString("en-US")} / 17,576</dd>`;
      tbody.innerHTML = "";
      $("sweep-read").textContent = n ? "Sweeping…" : "";
      return;
    }
    const v = sweep.values;
    const t = v[truth];
    const TIE = 1e-12;
    const target = afterFirstPress(key.msgKey);
    let sum = 0;
    let sq = 0;
    let above = 0;
    const equivalent = [];
    const tied = [];
    for (let s = 0; s < STARTS; s++) {
      if (s === truth) continue;
      sum += v[s];
      sq += v[s] * v[s];
      if (v[s] > t + TIE) above++;
      else if (v[s] >= t - TIE) (afterFirstPress(startName(s)) === target ? equivalent : tied).push(startName(s));
    }
    const mean = sum / (STARTS - 1);
    const sd = Math.sqrt(sq / (STARTS - 1) - mean * mean);
    const z = (t - mean) / sd;
    const rank = above + 1;
    const ties = equivalent.length + tied.length;
    const zText = (z >= 0 ? "+" : "") + z.toFixed(1);
    const tiedNames = [...equivalent, ...tied];
    const rankText = rank.toLocaleString("en-US") + (ties ? ` (tied: ${tiedNames.slice(0, 2).join(", ")}${ties > 2 ? ", …" : ""})` : "");
    dl.innerHTML = [
      ["Sender's start", key.msgKey],
      ["Its IC", fmt(t)],
      ["Wrong starts, mean ± sd", `${fmt(mean)} ± ${fmt(sd)}`],
      ["z-score", zText],
      ["Rank among 17,576", rankText],
    ].map(([a, b]) => `<dt>${esc(a)}</dt><dd>${esc(b)}</dd>`).join("");
    // Competition ranking: equal scores share a rank.
    const order = Array.from({ length: STARTS }, (_, i) => i).sort((a, b) => v[b] - v[a] || (a === truth ? -1 : b === truth ? 1 : a - b));
    const rankOf = (s) => {
      let r = 1;
      for (let i = 0; i < STARTS && v[order[i]] > v[s] + TIE; i++) r++;
      return r;
    };
    const top = order.slice(0, 8);
    if (!top.includes(truth)) top.push(truth);
    tbody.innerHTML = top
      .map((s) => {
        const tag = s === truth ? " · sender's" : equivalent.includes(startName(s)) ? " · same key" : "";
        return `<tr class="${s === truth ? "truth" : ""}"><td>${rankOf(s).toLocaleString("en-US")}</td><td class="mono">${startName(s)}${tag}</td><td class="n">${fmt(v[s])}</td></tr>`;
      })
      .join("");
    const sameKeyNote = equivalent.length
      ? ` ${equivalent.join(", ")} ${equivalent.length === 1 ? "scores" : "score"} exactly the same because ${equivalent.length === 1 ? "it is" : "they are"} the same key: the first key press brings ${equivalent.length === 1 ? "it" : "each"} to ${target}, as it does from ${key.msgKey}, so the whole message decrypts identically.`
      : "";
    const otherTies = tied.length ? ` It also ties with ${tied.length} unrelated start${tied.length === 1 ? "" : "s"} (${tied.slice(0, 3).join(", ")}${tied.length > 3 ? ", …" : ""}).` : "";
    const plugs = plugCount(sweep.plugs);
    let read;
    if (rank === 1 && !tied.length) {
      read = `With ${plugs}, the sender's key stands alone at the top, z = ${zText}. Enough letters pass through unplugged that the decryption keeps plaintext's lopsided letter counts.${sameKeyNote}`;
    } else if (rank === 1) {
      read = `With ${plugs}, the sender's start ${key.msgKey} shares the top score (z = ${zText}).${sameKeyNote}${otherTies}`;
    } else if (rank <= 200) {
      read = `With ${plugs} the sender's start ranks ${rank}. A sweep that keeps its top 200 would pass it to the climb, but it no longer stands out (z = ${zText}).${sameKeyNote}${otherTies}`;
    } else {
      read = `With ${plugs} the sender's start ranks ${rank.toLocaleString("en-US")} of 17,576 (z = ${zText}).${sameKeyNote} With ${2 * sweep.plugs} of 26 letters plugged, only about ${Math.round(100 * ((26 - 2 * sweep.plugs) / 26) ** 2)}% of key presses pass the plugboard untouched both ways, so the unplugged decryption keeps almost none of the plaintext's letter counts. Over all 60 wheel orders it would be buried far deeper. ${sweep.plugs === 10 ? "This is the README's finding: at ten plugs the IC stage has almost no detection power." : "The README measures the same loss at ten plugs, where the IC stage has almost no detection power."}`;
    }
    $("sweep-read").textContent = read;
  }

  // ------------------------------------------------------------------ stage 2

  const climb = {};

  function climbStart() {
    const wantBest = $("climb-best").checked && sweep.best !== null;
    return wantBest ? startName(sweep.best) : key.msgKey;
  }

  function updateClimbChoices() {
    $("climb-true-v").textContent = key.msgKey;
    const ready = sweep.best !== null;
    $("climb-best").disabled = !ready;
    const bestName = ready ? startName(sweep.best) : "";
    const bestTag = !ready
      ? ""
      : bestName === key.msgKey
        ? " (the sender's)"
        : sameKey(bestName, key.msgKey)
          ? " (the same key as the sender's)"
          : "";
    $("climb-best-v").textContent = ready ? bestName + bestTag : "(run the sweep)";
    if (!ready && $("climb-best").checked) $("climb-true").checked = true;
  }

  function resetClimb() {
    if (climb.timer) clearTimeout(climb.timer);
    updateClimbChoices();
    const positions = climbStart();
    const body = sweep.body;
    const table = C.positionTable(D, key.rotors, key.rings, positions, body.length);
    Object.assign(climb, {
      positions,
      body,
      table,
      truth: C.plugmap(senderBoard(sweep.plugs)),
      objectives: {
        index_of_coincidence: (pb) => C.coincidenceOfDecryption(table, body, pb),
        ngram: (pb) => scorer.scoreDecryption(table, body, pb),
      },
      phase: 0,
      gen: null,
      board: Array.from({ length: 26 }, (_, i) => i),
      history: [],
      log: [],
      done: false,
      timer: null,
    });
    record(0, "start");
    $("climb-run").disabled = false;
    $("climb-step").disabled = false;
    $("climb-run").textContent = "Run the climb";
    $("decrypt-label").textContent = `Decryption at wheel start ${positions} with this plugboard`;
    const cap = sweep.plugs > D.climb.max_pairs ? ` The sender used ${sweep.plugs} pairs; the climb places at most ${D.climb.max_pairs}.` : "";
    $("climb-status").textContent = `Pass 0: no plugs. ${D.climb.phases.length} phases, best improvement over every one-plug change.${cap}`;
    $("climb-log").innerHTML = "";
    drawClimb();
    renderVerdict();
  }

  function record(pass, kind) {
    const pb = climb.board;
    climb.history.push({
      phase: D.climb.phases[Math.min(climb.phase, D.climb.phases.length - 1)],
      pass,
      kind,
      ic: climb.objectives.index_of_coincidence(pb),
      ng: climb.objectives.ngram(pb) / climb.body.length,
    });
  }

  function describeMove(before, after) {
    const pairs = (pb) => new Set(C.plugPairs(pb).split(" ").filter(Boolean));
    const a = pairs(before);
    const b = pairs(after);
    const added = [...b].filter((p) => !a.has(p));
    const removed = [...a].filter((p) => !b.has(p));
    return [...added.map((p) => `+${p}`), ...removed.map((p) => `−${p}`)].join(" ");
  }

  function logLine(text, cls) {
    const li = document.createElement("li");
    if (cls) li.className = cls;
    li.textContent = text;
    const log = $("climb-log");
    log.appendChild(li);
    log.scrollTop = log.scrollHeight;
  }

  function climbPass() {
    if (climb.done) return false;
    const phases = D.climb.phases;
    const settings = D.climb;
    if (!climb.gen) {
      const objective = phases[climb.phase];
      climb.gen = C.climbStecker(climb.objectives[objective], settings.max_pairs, settings.max_passes, settings.minimum_gain, climb.board);
      logLine(objective === "ngram" ? "Phase 2 · n-gram log-likelihood" : "Phase 1 · index of coincidence", "phase");
    }
    const step = climb.gen.next();
    if (!step.done) {
      const s = step.value;
      climb.board = s.plugboard;
      record(s.pass, "pass");
      const h = climb.history[climb.history.length - 1];
      const val = phases[climb.phase] === "ngram" ? `n-gram ${fmt(h.ng, 3)}/letter` : `IC ${fmt(h.ic)}`;
      logLine(`pass ${s.pass}: ${describeMove(s.before, s.plugboard)}  →  ${val}`);
      $("climb-status").textContent = `${phases[climb.phase] === "ngram" ? "Phase 2" : "Phase 1"}, pass ${s.pass}: ${C.plugPairs(climb.board).split(" ").filter(Boolean).length} plugs.`;
      drawClimb();
      return true;
    }
    logLine(`converged after ${step.value.passes} pass${step.value.passes === 1 ? "" : "es"}; ${step.value.evaluations.toLocaleString("en-US")} plugboards scored`);
    climb.gen = null;
    climb.phase++;
    if (climb.phase >= phases.length) {
      climb.done = true;
      $("climb-run").disabled = true;
      $("climb-step").disabled = true;
      $("climb-status").textContent = "Converged: no single plug change improves the score.";
      drawClimb();
      renderVerdict();
      return false;
    }
    return climbPass();
  }

  function runClimb() {
    if (climb.timer) {
      clearTimeout(climb.timer);
      climb.timer = null;
      $("climb-run").textContent = "Run the climb";
      return;
    }
    $("climb-run").textContent = "Pause";
    const delay = reduceMotion ? 0 : 420;
    const tick = () => {
      if (!climbPass()) {
        climb.timer = null;
        $("climb-run").textContent = "Run the climb";
        return;
      }
      climb.timer = setTimeout(tick, delay);
    };
    tick();
  }

  function drawClimb() {
    drawPlugs();
    drawChart($("chart-ic"), climb.history.map((h) => h.ic), "ic", [RANDOM_IC, "random"]);
    drawChart($("chart-ng"), climb.history.map((h) => h.ng), "ng", null);
    const plain = C.decryptWithTable(climb.table, climb.body, climb.board).map(C.ch).join("");
    const truth = key.plaintext;
    let right = 0;
    $("decrypt").innerHTML = [...plain]
      .map((c, i) => {
        const ok = c === truth[i];
        if (ok) right++;
        return `<span class="${ok ? "y" : "n"}">${c}</span>`;
      })
      .join("");
    $("decrypt-label").textContent = `Decryption at wheel start ${climb.positions}: ${right} of ${plain.length} letters right`;
    climb.right = right;
    climb.plain = plain;
  }

  function drawPlugs() {
    const svg = $("plug-svg");
    svg.innerHTML = "";
    const x = (i) => 20 + i * 23.2;
    const base = 78;
    for (let i = 0; i < 26; i++) svgText(svg, x(i), base + 5, C.ch(i), { "text-anchor": "middle" });
    const arc = (a, b, up, cls) => {
      const h = 10 + Math.abs(a - b) * 2.3;
      const y0 = up ? base - 10 : base + 14;
      const yc = up ? y0 - h : y0 + h * 0.75;
      el("path", { d: `M ${x(a)} ${y0} Q ${(x(a) + x(b)) / 2} ${yc} ${x(b)} ${y0}`, class: cls }, svg);
    };
    for (let i = 0; i < 26; i++) {
      if (climb.truth[i] > i) arc(i, climb.truth[i], false, "arc-true");
      if (climb.board[i] > i) arc(i, climb.board[i], true, climb.truth[i] === climb.board[i] ? "arc-ok" : "arc-bad");
    }
  }

  function drawChart(svg, values, kind, ref) {
    svg.innerHTML = "";
    const W = 320;
    const H = 170;
    const L = 46;
    const R = 10;
    const T = 12;
    const B = 26;
    let lo = Math.min(...values);
    let hi = Math.max(...values);
    if (ref) {
      lo = Math.min(lo, ref[0]);
      hi = Math.max(hi, ref[0]);
    }
    if (hi - lo < 1e-6) {
      hi += 0.5 * Math.abs(hi || 1) * 0.02 + 1e-3;
      lo -= 0.5 * Math.abs(lo || 1) * 0.02 + 1e-3;
    }
    const pad = (hi - lo) * 0.08;
    lo -= pad;
    hi += pad;
    const n = Math.max(values.length - 1, 1);
    const x = (i) => L + (i / n) * (W - L - R);
    const y = (v) => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
    const digits = kind === "ic" ? 3 : 2;
    for (let k = 0; k <= 3; k++) {
      const v = lo + ((hi - lo) * k) / 3;
      el("line", { x1: L, x2: W - R, y1: y(v), y2: y(v), class: "grid" }, svg);
      svgText(svg, L - 5, y(v) + 3, v.toFixed(digits), { "text-anchor": "end" });
    }
    el("line", { x1: L, x2: W - R, y1: H - B, y2: H - B, class: "axis" }, svg);
    const ticks = Math.min(n, 6);
    for (let k = 0; k <= ticks; k++) {
      const i = Math.round((n * k) / ticks);
      svgText(svg, x(i), H - B + 14, String(i), { "text-anchor": "middle" });
    }
    svgText(svg, W - R, H - 2, "step of the climb", { "text-anchor": "end" });
    if (ref) {
      el("line", { x1: L, x2: W - R, y1: y(ref[0]), y2: y(ref[0]), class: "ref" }, svg);
      svgText(svg, W - R - 2, y(ref[0]) - 4, ref[1], { "text-anchor": "end", class: "ref-t" });
    }
    // Shade the n-gram phase so the hand-off between objectives is visible.
    const firstNg = climb.history.findIndex((h) => h.phase === "ngram");
    if (firstNg > 0 && values.length > 1) {
      el("rect", { x: x(firstNg - 1), y: T, width: Math.max(0, W - R - x(firstNg - 1)), height: H - T - B, class: "grid", style: "fill:var(--sunk);stroke:none;opacity:0.6" }, svg);
      svgText(svg, x(firstNg - 1) + 3, T + 10, "n-gram phase", {});
    }
    const pts = values.map((v, i) => `${x(i)},${y(v)}`);
    if (values.length > 1) {
      el("path", { d: `M ${x(0)},${H - B} L ${pts.join(" L ")} L ${x(values.length - 1)},${H - B} Z`, class: `area-${kind}` }, svg);
      el("path", { d: `M ${pts.join(" L ")}`, class: `line-${kind}` }, svg);
    }
    const last = values.length - 1;
    el("circle", { cx: x(last), cy: y(values[last]), r: 3.5, class: `dot-${kind}` }, svg);
  }

  function renderVerdict() {
    const box = $("verdict-box");
    if (!climb.done) {
      box.className = "verdict";
      box.innerHTML = `<p>Run the climb to see what it recovers from the ciphertext alone.</p>`;
      return;
    }
    const found = C.plugPairs(climb.board).split(" ").filter(Boolean);
    // Compare plug maps, not the key sheet's text, which may write a pair either way round.
    const truth = C.plugPairs(climb.truth).split(" ").filter(Boolean);
    const correct = found.filter((p) => truth.includes(p)).length;
    const exact = climb.plain === key.plaintext;
    const atTrue = sameKey(climb.positions, key.msgKey);
    const where = climb.positions === key.msgKey
      ? "the sender's start"
      : `${climb.positions}, the same key as the sender's ${key.msgKey},`;
    box.className = `verdict ${exact ? "ok" : "bad"}`;
    let body;
    if (exact) {
      const start = climb.positions === key.msgKey ? climb.positions : `${climb.positions} (the same key as the sender's ${key.msgKey})`;
      body = `<h3>Plaintext recovered exactly</h3><p>From the ciphertext alone, given wheel order ${key.rotors.join("-")}, rings ${key.rings} and start ${start}, the climb found ${correct} of the sender's ${plugCount(truth.length)} and read all ${climb.plain.length} letters. ${atTrue ? "This is the positive control the repository runs: it certifies the climb, not the sweep that has to hand it the right setting." : ""}</p>`;
    } else if (!atTrue) {
      body = `<h3>The climb polished noise</h3><p>The sweep's top start ${climb.positions} is neither the sender's ${key.msgKey} nor the same key, so no plugboard can make the text readable. The climb still converged, on ${found.length} plugs of which ${correct} happen to be right, with ${climb.right} of ${climb.plain.length} letters matching by chance. This is how the attack fails with ${plugCount(truth.length)}: stage 1 does not hand stage 2 the right setting.</p>`;
    } else if (truth.length > D.climb.max_pairs) {
      body = `<h3>Right setting, more plugs than the climb allows</h3><p>The sender used ${truth.length} pairs, but the climb places at most ${D.climb.max_pairs}, so it cannot reach the sender's plugboard from any start. At ${where} it found ${correct} of the ${truth.length} plugs and ${climb.right} of ${climb.plain.length} letters.</p>`;
    } else {
      body = `<h3>Right setting, wrong plugboard</h3><p>At ${where} the climb found ${correct} of ${truth.length} plugs and ${climb.right} of ${climb.plain.length} letters, then stuck at a local optimum. The repository's <code>climb.first_plug</code> option restarts the climb from every first plug on a few common letters to recover most of these.</p>`;
    }
    box.innerHTML = `${body}<p class="mono">Found: ${esc(found.join(" ") || "no plugs")}<br>Sender: ${esc(truth.join(" ") || "no plugs")}</p>`;
  }

  // ------------------------------------------------------------------ wiring up

  function init() {
    for (const id of ["key-l", "key-m", "key-r"]) {
      $(id).innerHTML = WHEELS.map((w) => `<option value="${w}">${w}</option>`).join("");
    }
    buildBoards();
    const k = demoKey();
    fillForm(k);
    applyKey(k);

    $("key-form").addEventListener("submit", (e) => {
      e.preventDefault();
      try {
        const next = readForm();
        $("key-error").textContent = "";
        fillForm(next);
        applyKey(next);
      } catch (err) {
        $("key-error").textContent = err.message;
      }
    });
    $("key-demo").addEventListener("click", () => {
      $("key-error").textContent = "";
      const d = demoKey();
      fillForm(d);
      applyKey(d);
    });
    for (const m of ["indicator", "encipher", "decipher"]) $(`mode-${m}`).addEventListener("click", () => loadMode(m));
    $("m-step").addEventListener("click", () => {
      stopPlay();
      if (panel.cursor >= panel.input.length) loadMode(panel.mode);
      pressNext(true);
    });
    $("m-play").addEventListener("click", play);
    $("m-reset").addEventListener("click", () => loadMode(panel.mode));
    document.addEventListener("keydown", (e) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.target.closest && e.target.closest("input, textarea, select")) return;
      if (!/^[a-zA-Z]$/.test(e.key)) return;
      const box = $("machine").getBoundingClientRect();
      if (box.bottom < 0 || box.top > window.innerHeight) return;
      e.preventDefault();
      typeLetter(e.key.toUpperCase());
    });
    $("sweep-plugs").addEventListener("input", () => resetSweep(false));
    $("sweep-run").addEventListener("click", runSweep);
    $("climb-run").addEventListener("click", runClimb);
    $("climb-step").addEventListener("click", () => {
      if (climb.timer) runClimb();
      climbPass();
    });
    $("climb-reset").addEventListener("click", resetClimb);
    $("climb-true").addEventListener("change", resetClimb);
    $("climb-best").addEventListener("change", resetClimb);
  }

  init();
})();
