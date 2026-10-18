/* Enigma I, the index-of-coincidence sweep and the stecker hill-climb, in JS.
 *
 * A browser restatement of enigma.py, enigma_fast.position_permutations,
 * stecker_climb.climb_stecker and stecker_scoring.FastNgramScorer, so the
 * visualizer runs the same machine and the same attack the Python pipeline
 * does.  tests/test_visualizer.py checks it against the Python on every run.
 * Wirings and n-gram counts are passed in, not restated, so they come from the
 * repository's own sources at build time.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.EnigmaCore = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const A = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
  const idx = (c) => c.charCodeAt(0) - 65;
  const ch = (i) => A[((i % 26) + 26) % 26];
  const mod = (v) => ((v % 26) + 26) % 26;

  function permutation(wiring, label) {
    const w = wiring.toUpperCase();
    if (w.length !== 26 || new Set(w).size !== 26 || [...w].some((c) => !A.includes(c))) {
      throw new Error(`${label} must be a permutation of A-Z`);
    }
    return [...w].map(idx);
  }

  /** Involutive plugboard map from space-separated pairs, as enigma.plugmap. */
  function plugmap(pairs) {
    const mapping = Array.from({ length: 26 }, (_, i) => i);
    const used = new Set();
    for (const pair of (pairs || "").toUpperCase().split(/\s+/).filter(Boolean)) {
      if (pair.length !== 2 || [...pair].some((c) => !A.includes(c))) {
        throw new Error(`"${pair}" is not a pair of letters`);
      }
      if (pair[0] === pair[1]) throw new Error(`"${pair}" plugs a letter to itself`);
      for (const c of pair) {
        if (used.has(c)) throw new Error(`${c} is plugged twice`);
        used.add(c);
      }
      const a = idx(pair[0]);
      const b = idx(pair[1]);
      mapping[a] = b;
      mapping[b] = a;
    }
    return mapping;
  }

  function plugPairs(mapping) {
    const out = [];
    for (let i = 0; i < 26; i++) if (mapping[i] > i) out.push(ch(i) + ch(mapping[i]));
    return out.join(" ");
  }

  class Rotor {
    constructor(name, wiring, notches, ring, pos) {
      this.name = name;
      this.w = permutation(wiring, `rotor ${name} wiring`);
      this.inv = new Array(26);
      this.w.forEach((v, i) => (this.inv[v] = i));
      this.notches = new Set([...notches].map(idx));
      this.ring = ring;
      this.pos = pos;
    }
    atNotch() {
      return this.notches.has(this.pos);
    }
    step() {
      this.pos = (this.pos + 1) % 26;
    }
    fwd(x) {
      return mod(this.w[mod(x + this.pos - this.ring)] - this.pos + this.ring);
    }
    rev(x) {
      return mod(this.inv[mod(x + this.pos - this.ring)] - this.pos + this.ring);
    }
  }

  /** Three-wheel pawl-stepping Enigma I with an identity entry wheel. */
  class Machine {
    constructor(data, { rotors, rings = "AAA", positions = "AAA", plugboard = "" }) {
      if (rotors.length !== 3 || new Set(rotors).size !== 3) throw new Error("choose three different wheels");
      for (const [label, v] of [["ring setting", rings], ["start position", positions]]) {
        if (!/^[A-Z]{3}$/.test(v)) throw new Error(`the ${label} must be three letters A-Z`);
      }
      [this.L, this.M, this.R] = rotors.map((name, i) => {
        const spec = data.rotors[name];
        if (!spec) throw new Error(`unknown wheel ${name}`);
        return new Rotor(name, spec[0], spec[1], idx(rings[i]), idx(positions[i]));
      });
      this.plug = plugmap(plugboard);
      this.reflector = permutation(data.reflector, "reflector wiring");
    }
    get positions() {
      return ch(this.L.pos) + ch(this.M.pos) + ch(this.R.pos);
    }
    /** Step the wheels; returns which moved and why (the middle-wheel double step). */
    step() {
      const middleNotch = this.M.atNotch();
      const rightNotch = this.R.atNotch();
      if (middleNotch) this.L.step();
      if (middleNotch || rightNotch) this.M.step();
      this.R.step();
      return { left: middleNotch, middle: middleNotch || rightNotch, right: true, middleNotch, rightNotch };
    }
    /** Press one key: the wheels step, then the current runs and a lamp lights. */
    press(c) {
      const stepped = this.step();
      const k = idx(c);
      const p1 = this.plug[k];
      const r1 = this.R.fwd(p1);
      const m1 = this.M.fwd(r1);
      const l1 = this.L.fwd(m1);
      const u = this.reflector[l1];
      const l2 = this.L.rev(u);
      const m2 = this.M.rev(l2);
      const r2 = this.R.rev(m2);
      const out = this.plug[r2];
      return { stepped, contacts: [k, p1, r1, m1, l1, u, l2, m2, r2, out], output: ch(out) };
    }
    key(c) {
      return this.press(c).output;
    }
    crypt(text) {
      return [...text.toUpperCase()].filter((c) => A.includes(c)).map((c) => this.key(c)).join("");
    }
  }

  /** Unsteckered permutation at each position, flattened as position_permutations. */
  function positionTable(data, rotors, rings, positions, length) {
    const m = new Machine(data, { rotors, rings, positions });
    const table = new Int16Array(26 * length);
    for (let t = 0; t < length; t++) {
      m.step();
      for (let x = 0; x < 26; x++) {
        table[26 * t + x] = m.R.rev(m.M.rev(m.L.rev(m.reflector[m.L.fwd(m.M.fwd(m.R.fwd(x)))])));
      }
    }
    return table;
  }

  function decryptWithTable(table, body, plugboard) {
    const out = new Array(body.length);
    for (let t = 0; t < body.length; t++) out[t] = plugboard[table[26 * t + plugboard[body[t]]]];
    return out;
  }

  function indexOfCoincidence(counts, total) {
    if (total < 2) return 0;
    let s = 0;
    for (let i = 0; i < 26; i++) s += counts[i] * (counts[i] - 1);
    return s / (total * (total - 1));
  }

  /** stecker_climb.coincidence_of_decryption */
  function coincidenceOfDecryption(table, body, plugboard) {
    const counts = new Array(26).fill(0);
    for (let t = 0; t < body.length; t++) counts[plugboard[table[26 * t + plugboard[body[t]]]]]++;
    return indexOfCoincidence(counts, body.length);
  }

  /**
   * Unsteckered IC of the body at every start position of one wheel order and
   * ring setting, for starts [from, to) in the order AAA, AAB, ...  This is
   * the first stage of the attack, which the README says has almost no power
   * at a ten-pair stecker.
   */
  function sweepStarts(data, rotors, rings, body, from, to) {
    const out = new Float64Array(to - from);
    const counts = new Array(26);
    const m = new Machine(data, { rotors, rings });
    for (let s = from; s < to; s++) {
      m.L.pos = Math.floor(s / 676);
      m.M.pos = Math.floor(s / 26) % 26;
      m.R.pos = s % 26;
      counts.fill(0);
      for (let t = 0; t < body.length; t++) {
        m.step();
        counts[m.R.rev(m.M.rev(m.L.rev(m.reflector[m.L.fwd(m.M.fwd(m.R.fwd(body[t])))])))]++;
      }
      out[s - from] = indexOfCoincidence(counts, body.length);
    }
    return out;
  }

  /** stecker_scoring.FastNgramScorer: bigram term folded into the trigram table. */
  class NgramScorer {
    constructor(scorer) {
      const alpha = scorer.additive_smoothing;
      const table = (counts, width) => {
        let total = 0;
        for (const k in counts) total += counts[k];
        const denominator = total + alpha * 26 ** width;
        const logs = {};
        for (const k in counts) logs[k] = Math.log((counts[k] + alpha) / denominator);
        return { logs, floor: Math.log(alpha / denominator) };
      };
      const bi = table(scorer.bigram_counts, 2);
      const tri = table(scorer.trigram_counts, 3);
      this.bigram = new Float64Array(676);
      for (let a = 0; a < 26; a++) {
        for (let b = 0; b < 26; b++) {
          const key = A[a] + A[b];
          this.bigram[a * 26 + b] = scorer.bigram_weight * (key in bi.logs ? bi.logs[key] : bi.floor);
        }
      }
      this.combined = new Float64Array(17576);
      for (let a = 0; a < 26; a++) {
        for (let b = 0; b < 26; b++) {
          for (let c = 0; c < 26; c++) {
            const key = A[a] + A[b] + A[c];
            this.combined[a * 676 + b * 26 + c] =
              scorer.trigram_weight * (key in tri.logs ? tri.logs[key] : tri.floor) + this.bigram[b * 26 + c];
          }
        }
      }
    }
    scoreDecryption(table, body, plugboard) {
      const bigram = this.bigram;
      const combined = this.combined;
      let total = 0;
      let previous = -1;
      let cursor = -1;
      for (let t = 0; t < body.length; t++) {
        const letter = plugboard[table[26 * t + plugboard[body[t]]]];
        if (previous < 0) {
          previous = letter;
          continue;
        }
        if (cursor < 0) {
          total += bigram[previous * 26 + letter];
          cursor = previous * 676 + letter * 26;
        } else {
          total += combined[cursor + letter];
          cursor = ((cursor % 676) + letter) * 26;
        }
        previous = letter;
      }
      return total;
    }
  }

  /**
   * stecker_climb.climb_stecker, one pass per iteration: best improvement over
   * all 325 swaps plus the unplug moves.  Yields after every improving pass so
   * a page can draw it.  Returns the final plugboard, and whether the climb
   * converged (a pass found no improving change) or stopped at maxPasses.
   */
  function* climbStecker(evaluate, maxPairs, maxPasses, minimumGain, initial) {
    let current = initial ? initial.slice() : Array.from({ length: 26 }, (_, i) => i);
    let best = evaluate(current);
    let evaluations = 1;
    let passes = 0;
    let converged = false;
    while (passes < maxPasses) {
      passes++;
      let passBest = best;
      let chosen = null;
      for (let first = 0; first < 25; first++) {
        for (let second = first + 1; second < 26; second++) {
          const trial = current.slice();
          const partnerFirst = trial[first];
          const partnerSecond = trial[second];
          if (partnerFirst === second) continue;
          trial[partnerFirst] = partnerFirst;
          trial[partnerSecond] = partnerSecond;
          trial[first] = second;
          trial[second] = first;
          let pairs = 0;
          for (let x = 0; x < 26; x++) if (trial[x] > x) pairs++;
          if (pairs > maxPairs) continue;
          const score = evaluate(trial);
          evaluations++;
          if (score > passBest + minimumGain) {
            passBest = score;
            chosen = trial;
          }
        }
      }
      for (let letter = 0; letter < 26; letter++) {
        if (current[letter] === letter) continue;
        const trial = current.slice();
        trial[trial[letter]] = trial[letter];
        trial[letter] = letter;
        const score = evaluate(trial);
        evaluations++;
        if (score > passBest + minimumGain) {
          passBest = score;
          chosen = trial;
        }
      }
      if (chosen === null) {
        converged = true;
        break;
      }
      const before = current;
      current = chosen;
      const previous = best;
      best = passBest;
      yield { pass: passes, before, plugboard: current.slice(), previous, score: best, evaluations };
    }
    return { plugboard: current, score: best, passes, evaluations, converged };
  }

  /**
   * stecker_climb.run_climb_phases, one pass at a time: each objective climbs
   * from where the previous one stopped.  Yields { type: "phase" } as a phase
   * starts, { type: "pass" } after each of its improving passes and
   * { type: "end" } with its record as it stops.  Returns the final plugboard
   * and the records.  The page draws this generator and the parity test runs
   * it, so what the page shows is what the test checks.
   */
  function* climbPhases(phases, objectives, settings, initial) {
    let plugboard = initial ? initial.slice() : Array.from({ length: 26 }, (_, i) => i);
    const records = [];
    for (const [index, objective] of phases.entries()) {
      if (!objectives[objective]) throw new Error(`unknown climb objective: ${objective}`);
      yield { type: "phase", index, objective };
      const climb = climbStecker(
        objectives[objective],
        settings.max_pairs,
        settings.max_passes,
        settings.minimum_gain,
        plugboard
      );
      let step = climb.next();
      while (!step.done) {
        yield { type: "pass", index, objective, ...step.value };
        step = climb.next();
      }
      const { passes, evaluations, converged } = step.value;
      plugboard = step.value.plugboard;
      const record = { objective, plugboard: plugPairs(plugboard), passes, evaluations, converged };
      records.push(record);
      yield { type: "end", index, ...record };
    }
    return { plugboard, records };
  }

  /** Run a whole climb with no drawing. */
  function runClimbPhases(phases, objectives, settings, initial) {
    const run = climbPhases(phases, objectives, settings, initial);
    let step = run.next();
    while (!step.done) step = run.next();
    return step.value;
  }

  function textToIndices(text) {
    return [...text.toUpperCase()].filter((c) => A.includes(c)).map(idx);
  }

  return {
    A,
    idx,
    ch,
    plugmap,
    plugPairs,
    Machine,
    positionTable,
    decryptWithTable,
    indexOfCoincidence,
    coincidenceOfDecryption,
    sweepStarts,
    NgramScorer,
    climbStecker,
    climbPhases,
    runClimbPhases,
    textToIndices,
  };
});
