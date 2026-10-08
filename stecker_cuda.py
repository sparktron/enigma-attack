"""CUDA stecker climb for the body-direct sweep: ``climb.engine = "cuda"``.

An exact port of :class:`stecker_batch.BatchedClimber`, run for a whole chunk of
rotor settings in one call.  Each CUDA thread block climbs one (setting, window)
pair: it builds the setting's per-position permutation table itself (the work
``enigma_fast.position_permutations`` does in Python per setting), then runs the
configured phases with one thread per candidate move.  The batched climber is
the specification and this module reproduces it, not a tolerance around it:

* the move order, the pair limit and the evaluation count are the batched
  climber's (swaps in ``np.triu_indices(26, 1)`` order skipping pairs already
  plugged together and boards over ``max_pairs``, then one unplug move per
  plugged letter in ascending order);
* the n-gram objective adds its terms in numpy's pairwise-summation order
  (eight accumulators, blocks of 128, halves rounded to a multiple of eight) in
  FP64, so every candidate's score is the batched score bit for bit and the
  acceptance rule (last move to clear the running best by more than
  ``minimum_gain``) makes the same choice; the coincidence objective is integer
  counts and the same three floating-point operations;
* the window score is the sequential sum ``FastNgramScorer.score_decryption``
  computes, divided by the window's letters, so the reported score and the
  window choice are the CPU sweep's exactly.

The acceptance scan is exact without being serial over every candidate: a move
can only replace the running best if its score exceeds every earlier score and
the starting best plus the gain (both follow from the running best never falling
below either), so one warp finds those few candidates with a prefix-maximum scan
and applies the rule to them in order.

``stecker_controls.cuda_climb_parity_report`` checks the engine against the
batched climber before any sweep that uses it, and the tests check the position
tables against ``enigma_fast.position_permutations``.

The kernel is compiled with ``nvcc`` on first use into a cache directory
(``$ENIGMA_ATTACK_CUDA_CACHE``, else ``~/.cache/enigma-attack/cuda``) and loaded
with ctypes; numpy is the only Python dependency (``pip install .[gpu]``).  An
nvcc-built library rather than a CuPy ``RawKernel``: the toolchain is already on
the host, ctypes adds no package, and the kernel source sits in this module, so
the provenance hash of the imported modules covers it.  Without numpy, nvcc or a
CUDA device ``available()`` is false and nothing else changes.

Scope: the whole-message and head-and-tail windowed climbs with the
``index_of_coincidence`` and ``ngram`` phases.  The split-point climb
(``stecker_split.SplitClimber``) is not implemented and is refused.
"""

from __future__ import annotations

import ctypes
import hashlib
import os
import pathlib
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from typing import Any

try:  # optional, as for stecker_batch
    import numpy as np
except ImportError:  # pragma: no cover - exercised by the fallback test
    np = None

import enigma_fast
from stecker_climb import climb_windows

MAX_LENGTH = 512
MAX_PHASES = 8
MAX_TOKENS = 32
OBJECTIVES = {"index_of_coincidence": 0, "ngram": 1}

CUDA_SOURCE = r"""
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cmath>
#include <cuda_runtime.h>

#define NPAIRS 325
#define NSLOT 352            /* 325 swaps, 26 unplugs, the current board */
#define CURRENT_SLOT 351
#define MAX_LENGTH 512
#define MAX_PHASES 8
#define MAX_TOKENS 32
#define COUNT_WORDS 13       /* 26 letter counts, two 16-bit fields a word */
#define NONE 99
#define FULL 0xffffffffu

struct WindowDesc {
    int first, length, letters, scorable;
    int ntri, nbi, ntri_tok, nbi_tok;
    int tri_tok[MAX_TOKENS];
    int bi_tok[MAX_TOKENS];
    signed char cipher[MAX_LENGTH];
    unsigned short tripos[MAX_LENGTH];
    unsigned short bipos[MAX_LENGTH];
};

struct ClimbDesc {
    int nphases;
    int phases[MAX_PHASES];
    int max_pairs, max_passes, nwin, maxlen;
    double min_gain;
};

__constant__ unsigned char c_first[NPAIRS];
__constant__ unsigned char c_second[NPAIRS];

struct Move { int a0, b0, a1, b1, a2, b2, a3, b3; };

/* The candidate board, as overrides of the current one applied in order (the
   last match wins): exactly the assignments stecker_batch._candidates makes. */
__device__ __forceinline__ int board_at(const unsigned char* cur, const Move& m, int x) {
    int v = cur[x];
    v = (x == m.a0) ? m.b0 : v;
    v = (x == m.a1) ? m.b1 : v;
    v = (x == m.a2) ? m.b2 : v;
    v = (x == m.a3) ? m.b3 : v;
    return v;
}

/* Slot j's move from the current board and whether it is a candidate. */
__device__ __forceinline__ bool move_of(int j, const unsigned char* cur, int pairs, int max_pairs,
                                        Move& m) {
    m.a0 = m.a1 = m.a2 = m.a3 = NONE;
    m.b0 = m.b1 = m.b2 = m.b3 = NONE;
    if (j < NPAIRS) {
        int f = c_first[j], s = c_second[j];
        int pf = cur[f], ps = cur[s];
        if (pf == s) return false;
        int after = pairs - (pf != f) - (ps != s) + 1;
        m.a0 = ps; m.b0 = ps;
        m.a1 = pf; m.b1 = pf;
        m.a2 = s;  m.b2 = f;
        m.a3 = f;  m.b3 = s;
        return after <= max_pairs;
    }
    if (j < CURRENT_SLOT) {
        int l = j - NPAIRS, partner = cur[l];
        m.a0 = partner; m.b0 = partner;
        m.a1 = l; m.b1 = l;
        return partner != l;
    }
    return true;
}

struct Decrypt {
    const unsigned char* cur;
    const unsigned char* table;
    const signed char* cipher;
    Move m;
    __device__ __forceinline__ int letter(int p) const {
        int x = board_at(cur, m, cipher[p]);
        int y = table[p * 26 + x];
        return board_at(cur, m, y);
    }
};

struct TrigramTerms {
    const Decrypt* d;
    const unsigned short* pos;
    const double* combined;
    int k, last, l0, l1;
    __device__ __forceinline__ double operator()() {
        int p = pos[k++];
        int a, b;
        if (p == last + 1) { a = l0; b = l1; }
        else { a = d->letter(p - 2); b = d->letter(p - 1); }
        int c = d->letter(p);
        l0 = b; l1 = c; last = p;
        return __ldg(&combined[a * 676 + b * 26 + c]);
    }
};

struct BigramTerms {
    const Decrypt* d;
    const unsigned short* pos;
    const double* bigram;
    int k;
    __device__ __forceinline__ double operator()() {
        int p = pos[k++];
        return __ldg(&bigram[d->letter(p - 1) * 26 + d->letter(p)]);
    }
};

/* numpy's DOUBLE_pairwise_sum over n terms that arrive in order. */
template <class F>
__device__ __forceinline__ double leaf_sum(int n, F& term) {
    if (n < 8) {
        double res = 0.0;
        for (int i = 0; i < n; ++i) res += term();
        return res;
    }
    double r0 = term(); double r1 = term(); double r2 = term(); double r3 = term();
    double r4 = term(); double r5 = term(); double r6 = term(); double r7 = term();
    int i = 8;
    int whole = n - (n % 8);
    for (; i < whole; i += 8) {
        r0 += term(); r1 += term(); r2 += term(); r3 += term();
        r4 += term(); r5 += term(); r6 += term(); r7 += term();
    }
    double res = ((r0 + r1) + (r2 + r3)) + ((r4 + r5) + (r6 + r7));
    for (; i < n; ++i) res += term();
    return res;
}

/* The pairwise recursion as a postorder plan: n >= 0 is a leaf of n terms,
   -1 adds the two partial sums on top of the stack (left + right). */
template <class F>
__device__ double pairwise(const int* tok, int ntok, F& term) {
    double stack[8];
    int sp = 0;
    for (int t = 0; t < ntok; ++t) {
        int v = tok[t];
        if (v < 0) {
            double right = stack[--sp];
            double left = stack[--sp];
            stack[sp++] = left + right;
        } else {
            stack[sp++] = leaf_sum(v, term);
        }
    }
    return stack[0];
}

__device__ double ngram_score(const Decrypt& d, const WindowDesc& w, const unsigned short* tripos,
                              const unsigned short* bipos, const double* bigram,
                              const double* combined) {
    TrigramTerms tri{&d, tripos, combined, 0, -10, 0, 0};
    double total = pairwise(w.tri_tok, w.ntri_tok, tri);
    if (w.nbi > 0) {
        BigramTerms bi{&d, bipos, bigram, 0};
        total = total + pairwise(w.bi_tok, w.nbi_tok, bi);
    }
    return total;
}

__device__ double coincidence_score(const Decrypt& d, int length, int letters,
                                    unsigned int* counts) {
    for (int w = 0; w < COUNT_WORDS; ++w) counts[w * NSLOT] = 0u;
    for (int p = 0; p < length; ++p) {
        if (d.cipher[p] < 0) continue;
        int z = d.letter(p);
        counts[(z >> 1) * NSLOT] += 1u << ((z & 1) * 16);
    }
    long long sum = 0;
    for (int w = 0; w < COUNT_WORDS; ++w) {
        unsigned int v = counts[w * NSLOT];
        long long a = v & 0xffffu, b = v >> 16;
        sum += a * (a - 1) + b * (b - 1);
    }
    double coincidence = (double)sum / (double)((long long)letters * (letters - 1));
    coincidence = coincidence * (double)length;
    return coincidence / (double)letters;
}

/* The per-position permutations of one setting for positions [first, first + length),
   exactly as enigma_fast.position_permutations steps and composes them. */
__device__ void build_table(const unsigned char* rotors, unsigned int notch_middle,
                            unsigned int notch_right, const unsigned char* s, int first,
                            int length, unsigned char* offsets, unsigned char* table) {
    const unsigned char* forward = rotors;            /* [3][26][26] left, middle, right */
    const unsigned char* reverse = rotors + 3 * 676;
    const unsigned char* reflector = rotors + 6 * 676;
    if (threadIdx.x == 0) {
        int pl = s[3], pm = s[4], pr = s[5];
        int ol = (pl - s[0] + 26) % 26, om = (pm - s[1] + 26) % 26, orr = (pr - s[2] + 26) % 26;
        for (int t = 0; t < first + length; ++t) {
            bool middle_at_notch = (notch_middle >> pm) & 1u;
            if (middle_at_notch) { pl = (pl + 1) % 26; ol = (ol + 1) % 26; }
            if (middle_at_notch || ((notch_right >> pr) & 1u)) { pm = (pm + 1) % 26; om = (om + 1) % 26; }
            pr = (pr + 1) % 26; orr = (orr + 1) % 26;
            if (t >= first) {
                int q = t - first;
                offsets[3 * q] = ol; offsets[3 * q + 1] = om; offsets[3 * q + 2] = orr;
            }
        }
    }
    __syncthreads();
    for (int i = threadIdx.x; i < length * 26; i += blockDim.x) {
        int q = i / 26, x = i % 26;
        int ol = offsets[3 * q], om = offsets[3 * q + 1], orr = offsets[3 * q + 2];
        int v = forward[2 * 676 + orr * 26 + x];
        v = forward[1 * 676 + om * 26 + v];
        v = forward[0 * 676 + ol * 26 + v];
        v = reflector[v];
        v = reverse[0 * 676 + ol * 26 + v];
        v = reverse[1 * 676 + om * 26 + v];
        v = reverse[2 * 676 + orr * 26 + v];
        table[i] = v;
    }
    __syncthreads();
}

struct Shared {
    unsigned char* table;
    signed char* cipher;
    unsigned short* tripos;
    unsigned short* bipos;
    double* scores;
    unsigned int* counts;
};

__device__ Shared carve(unsigned char* smem, int maxlen) {
    Shared sh;
    size_t at = 0;
    sh.scores = (double*)(smem + at); at += NSLOT * sizeof(double);
    sh.counts = (unsigned int*)(smem + at); at += COUNT_WORDS * NSLOT * sizeof(unsigned int);
    sh.tripos = (unsigned short*)(smem + at); at += maxlen * sizeof(unsigned short);
    sh.bipos = (unsigned short*)(smem + at); at += maxlen * sizeof(unsigned short);
    sh.table = smem + at; at += maxlen * 26;
    sh.cipher = (signed char*)(smem + at);
    return sh;
}

__device__ void load_rotors(const unsigned char* rotors, unsigned char* dst) {
    for (int i = threadIdx.x; i < 6 * 676 + 26; i += blockDim.x) dst[i] = rotors[i];
}

__global__ void __launch_bounds__(NSLOT, 2)
climb_kernel(ClimbDesc climb, const WindowDesc* windows, const double* bigram,
             const double* combined, const unsigned char* rotors, unsigned int notch_middle,
             unsigned int notch_right, const unsigned char* settings, int base, int count,
             unsigned char* out_board, int* out_evals, double* out_score) {
    extern __shared__ __align__(16) unsigned char smem[];
    __shared__ unsigned char cur[32];
    __shared__ unsigned char next[32];
    __shared__ int s_chosen, s_pairs;
    __shared__ double s_running, s_current;

    int block = blockIdx.x;
    int item = base + block / climb.nwin;
    int wi = block % climb.nwin;
    if (item >= count) return;
    const WindowDesc& w = windows[wi];
    int tid = threadIdx.x, lane = tid & 31, warp = tid >> 5;
    long long out = (long long)item * climb.nwin + wi;
    if (!w.scorable) {
        if (tid < 26) out_board[out * 26 + tid] = tid;
        if (tid == 0) { out_evals[out] = 0; out_score[out] = -INFINITY; }
        return;
    }
    Shared sh = carve(smem, climb.maxlen);
    int length = w.length;

    /* The rotor tables and the stepping offsets live in the count area until the
       table is built. */
    unsigned char* scratch = (unsigned char*)sh.counts;
    load_rotors(rotors, scratch);
    for (int i = tid; i < length; i += NSLOT) sh.cipher[i] = w.cipher[i];
    for (int i = tid; i < w.ntri; i += NSLOT) sh.tripos[i] = w.tripos[i];
    for (int i = tid; i < w.nbi; i += NSLOT) sh.bipos[i] = w.bipos[i];
    if (tid < 32) cur[tid] = tid < 26 ? tid : 0;
    if (tid == 0) s_pairs = 0;
    __syncthreads();
    build_table(scratch, notch_middle, notch_right, settings + 6 * (long long)item, w.first,
                length, scratch + 6 * 676 + 26, sh.table);

    unsigned int* my_counts = sh.counts + tid;
    double best = 0.0;
    int evaluations = 0;
    for (int ph = 0; ph < climb.nphases; ++ph) {
        int objective = climb.phases[ph];
        if (climb.max_passes <= 0) { evaluations += 1; continue; }
        bool first_pass = true;
        for (int pass = 0; pass < climb.max_passes; ++pass) {
            Decrypt d;
            d.cur = cur; d.table = sh.table; d.cipher = sh.cipher;
            bool valid = move_of(tid, cur, s_pairs, climb.max_pairs, d.m);
            if (tid == CURRENT_SLOT) valid = first_pass;
            double score = -INFINITY;
            if (valid) {
                score = objective == 0
                    ? coincidence_score(d, length, w.letters, my_counts)
                    : ngram_score(d, w, sh.tripos, sh.bipos, bigram, combined);
            }
            if (tid < CURRENT_SLOT) sh.scores[tid] = score;
            else if (first_pass) s_current = score;
            int candidates = __syncthreads_count(valid && tid < CURRENT_SLOT);
            if (first_pass) { best = s_current; evaluations += 1; }
            evaluations += candidates;

            if (warp == 0) {
                double gate = best + climb.min_gain;
                double carry = -INFINITY, running = best;
                int chosen = -1;
                for (int start = 0; start < CURRENT_SLOT; start += 32) {
                    int j = start + lane;
                    double v = j < CURRENT_SLOT ? sh.scores[j] : -INFINITY;
                    double inclusive = v;
                    for (int o = 1; o < 32; o <<= 1) {
                        double t = __shfl_up_sync(FULL, inclusive, o);
                        if (lane >= o) inclusive = fmax(inclusive, t);
                    }
                    double before = __shfl_up_sync(FULL, inclusive, 1);
                    if (lane == 0) before = -INFINITY;
                    before = fmax(before, carry);
                    unsigned int flagged = __ballot_sync(FULL, v > before && v > gate);
                    while (flagged) {
                        int l = __ffs(flagged) - 1;
                        flagged &= flagged - 1;
                        double s = __shfl_sync(FULL, v, l);
                        if (s > running + climb.min_gain) { running = s; chosen = start + l; }
                    }
                    carry = fmax(carry, __shfl_sync(FULL, inclusive, 31));
                }
                if (lane == 0) { s_chosen = chosen; s_running = running; }
            }
            __syncthreads();
            int chosen = s_chosen;
            if (chosen < 0) break;
            if (tid < 26) {
                Move m;
                move_of(chosen, cur, s_pairs, climb.max_pairs, m);
                next[tid] = board_at(cur, m, tid);
            }
            best = s_running;
            __syncthreads();
            if (tid < 26) cur[tid] = next[tid];
            __syncthreads();
            if (warp == 0) {
                unsigned int plugged = __ballot_sync(FULL, lane < 26 && cur[lane] > lane);
                if (lane == 0) s_pairs = __popc(plugged);
            }
            __syncthreads();
            first_pass = false;
        }
        __syncthreads();
    }

    if (tid < 26) out_board[out * 26 + tid] = cur[tid];
    if (tid == 0) {
        /* FastNgramScorer.score_decryption, term for term and in its order. */
        Decrypt d;
        d.cur = cur; d.table = sh.table; d.cipher = sh.cipher;
        d.m.a0 = d.m.a1 = d.m.a2 = d.m.a3 = NONE;
        d.m.b0 = d.m.b1 = d.m.b2 = d.m.b3 = NONE;
        double total = 0.0;
        int previous = -1, cursor = -1;
        for (int p = 0; p < length; ++p) {
            if (sh.cipher[p] < 0) { previous = -1; cursor = -1; continue; }
            int z = d.letter(p);
            if (previous < 0) { previous = z; continue; }
            if (cursor < 0) {
                total += bigram[previous * 26 + z];
                cursor = previous * 676 + z * 26;
            } else {
                total += combined[cursor + z];
                cursor = ((cursor % 676) + z) * 26;
            }
            previous = z;
        }
        out_evals[out] = evaluations;
        out_score[out] = total / (double)w.letters;
    }
}

__global__ void table_kernel(const unsigned char* rotors, unsigned int notch_middle,
                             unsigned int notch_right, const unsigned char* settings, int length,
                             unsigned char* out) {
    extern __shared__ __align__(16) unsigned char smem[];
    load_rotors(rotors, smem);
    __syncthreads();
    build_table(smem, notch_middle, notch_right, settings + 6 * (long long)blockIdx.x, 0, length,
                smem + 6 * 676 + 26, out + (long long)blockIdx.x * length * 26);
}

static char g_error[512];

static int fail(const char* what, cudaError_t err) {
    snprintf(g_error, sizeof g_error, "%s: %s", what, cudaGetErrorString(err));
    return -1;
}

#define CHECK(what, call) do { cudaError_t e_ = (call); if (e_ != cudaSuccess) return fail(what, e_); } while (0)

struct Context {
    ClimbDesc climb;
    WindowDesc* windows;
    double* bigram;
    double* combined;
    unsigned char* rotors;
    unsigned char* settings;
    unsigned char* board;
    int* evals;
    double* score;
    size_t capacity;
    size_t shared_bytes;
};

static size_t shared_for(int maxlen) {
    return NSLOT * sizeof(double) + COUNT_WORDS * NSLOT * sizeof(unsigned int)
        + 2 * maxlen * sizeof(unsigned short) + maxlen * 26 + maxlen;
}

extern "C" {

const char* ec_last_error(void) { return g_error; }

int ec_device_count(void) {
    int n = 0;
    if (cudaGetDeviceCount(&n) != cudaSuccess) { cudaGetLastError(); return 0; }
    return n;
}

int ec_device_info(char* name, int size, int* exec_timeout) {
    cudaDeviceProp prop;
    CHECK("cudaGetDeviceProperties", cudaGetDeviceProperties(&prop, 0));
    snprintf(name, size, "%s", prop.name);
    *exec_timeout = prop.kernelExecTimeoutEnabled;
    return 0;
}

int ec_window_desc_size(void) { return (int)sizeof(WindowDesc); }
int ec_climb_desc_size(void) { return (int)sizeof(ClimbDesc); }

int ec_create(const ClimbDesc* climb, const WindowDesc* windows, const double* bigram,
              const double* combined, void** handle) {
    static bool constants = false;
    if (!constants) {
        unsigned char first[NPAIRS], second[NPAIRS];
        int k = 0;
        for (int a = 0; a < 26; ++a)
            for (int b = a + 1; b < 26; ++b) { first[k] = a; second[k] = b; ++k; }
        CHECK("cudaMemcpyToSymbol", cudaMemcpyToSymbol(c_first, first, NPAIRS));
        CHECK("cudaMemcpyToSymbol", cudaMemcpyToSymbol(c_second, second, NPAIRS));
        constants = true;
    }
    Context* ctx = (Context*)calloc(1, sizeof(Context));
    if (!ctx) { snprintf(g_error, sizeof g_error, "out of host memory"); return -1; }
    ctx->climb = *climb;
    ctx->shared_bytes = shared_for(climb->maxlen);
    CHECK("cudaMalloc", cudaMalloc(&ctx->windows, sizeof(WindowDesc) * climb->nwin));
    CHECK("cudaMemcpy", cudaMemcpy(ctx->windows, windows, sizeof(WindowDesc) * climb->nwin, cudaMemcpyHostToDevice));
    CHECK("cudaMalloc", cudaMalloc(&ctx->bigram, 676 * sizeof(double)));
    CHECK("cudaMalloc", cudaMalloc(&ctx->combined, 17576 * sizeof(double)));
    CHECK("cudaMemcpy", cudaMemcpy(ctx->bigram, bigram, 676 * sizeof(double), cudaMemcpyHostToDevice));
    CHECK("cudaMemcpy", cudaMemcpy(ctx->combined, combined, 17576 * sizeof(double), cudaMemcpyHostToDevice));
    CHECK("cudaMalloc", cudaMalloc(&ctx->rotors, 6 * 676 + 26));
    CHECK("cudaFuncSetAttribute", cudaFuncSetAttribute(climb_kernel, cudaFuncAttributeMaxDynamicSharedMemorySize, (int)ctx->shared_bytes));
    *handle = ctx;
    return 0;
}

static int reserve(Context* ctx, size_t count) {
    if (count <= ctx->capacity) return 0;
    cudaFree(ctx->settings); cudaFree(ctx->board); cudaFree(ctx->evals); cudaFree(ctx->score);
    ctx->settings = 0; ctx->board = 0; ctx->evals = 0; ctx->score = 0; ctx->capacity = 0;
    size_t items = count * ctx->climb.nwin;
    CHECK("cudaMalloc", cudaMalloc(&ctx->settings, 6 * count));
    CHECK("cudaMalloc", cudaMalloc(&ctx->board, 26 * items));
    CHECK("cudaMalloc", cudaMalloc(&ctx->evals, sizeof(int) * items));
    CHECK("cudaMalloc", cudaMalloc(&ctx->score, sizeof(double) * items));
    ctx->capacity = count;
    return 0;
}

/* Climb every setting of one chunk.  Launches are kept short (batch settings
   each) so a display watchdog never sees a long kernel. */
int ec_run(void* handle, const unsigned char* rotors, unsigned int notch_middle,
           unsigned int notch_right, const unsigned char* settings, int count, int batch,
           unsigned char* board, int* evals, double* score) {
    Context* ctx = (Context*)handle;
    if (count <= 0) return 0;
    if (reserve(ctx, count)) return -1;
    size_t items = (size_t)count * ctx->climb.nwin;
    CHECK("cudaMemcpy", cudaMemcpy(ctx->rotors, rotors, 6 * 676 + 26, cudaMemcpyHostToDevice));
    CHECK("cudaMemcpy", cudaMemcpy(ctx->settings, settings, 6 * (size_t)count, cudaMemcpyHostToDevice));
    if (batch <= 0) batch = count;
    for (int base = 0; base < count; base += batch) {
        int n = count - base < batch ? count - base : batch;
        climb_kernel<<<n * ctx->climb.nwin, NSLOT, ctx->shared_bytes>>>(
            ctx->climb, ctx->windows, ctx->bigram, ctx->combined, ctx->rotors, notch_middle,
            notch_right, ctx->settings, base, count, ctx->board, ctx->evals, ctx->score);
        CHECK("climb_kernel launch", cudaGetLastError());
    }
    CHECK("climb_kernel", cudaDeviceSynchronize());
    CHECK("cudaMemcpy", cudaMemcpy(board, ctx->board, 26 * items, cudaMemcpyDeviceToHost));
    CHECK("cudaMemcpy", cudaMemcpy(evals, ctx->evals, sizeof(int) * items, cudaMemcpyDeviceToHost));
    CHECK("cudaMemcpy", cudaMemcpy(score, ctx->score, sizeof(double) * items, cudaMemcpyDeviceToHost));
    return 0;
}

void ec_destroy(void* handle) {
    Context* ctx = (Context*)handle;
    if (!ctx) return;
    cudaFree(ctx->windows); cudaFree(ctx->bigram); cudaFree(ctx->combined); cudaFree(ctx->rotors);
    cudaFree(ctx->settings); cudaFree(ctx->board); cudaFree(ctx->evals); cudaFree(ctx->score);
    free(ctx);
}

/* The position tables the climb builds, for testing against enigma_fast. */
int ec_tables(const unsigned char* rotors, unsigned int notch_middle, unsigned int notch_right,
              const unsigned char* settings, int count, int length, unsigned char* out) {
    unsigned char *d_rotors = 0, *d_settings = 0, *d_out = 0;
    size_t bytes = (size_t)count * length * 26;
    CHECK("cudaMalloc", cudaMalloc(&d_rotors, 6 * 676 + 26));
    CHECK("cudaMalloc", cudaMalloc(&d_settings, 6 * (size_t)count));
    CHECK("cudaMalloc", cudaMalloc(&d_out, bytes));
    CHECK("cudaMemcpy", cudaMemcpy(d_rotors, rotors, 6 * 676 + 26, cudaMemcpyHostToDevice));
    CHECK("cudaMemcpy", cudaMemcpy(d_settings, settings, 6 * (size_t)count, cudaMemcpyHostToDevice));
    table_kernel<<<count, 128, 6 * 676 + 26 + 3 * length>>>(d_rotors, notch_middle, notch_right, d_settings, length, d_out);
    CHECK("table_kernel launch", cudaGetLastError());
    CHECK("table_kernel", cudaDeviceSynchronize());
    CHECK("cudaMemcpy", cudaMemcpy(out, d_out, bytes, cudaMemcpyDeviceToHost));
    cudaFree(d_rotors); cudaFree(d_settings); cudaFree(d_out);
    return 0;
}

/* The sweep's streaming statistics, in its order and its arithmetic:
   delta = x - mean; mean += delta / count; m2 += delta * (x - mean). */
void ec_welford(const double* x, long long n, double* out) {
    double mean = 0.0, m2 = 0.0;
    for (long long i = 0; i < n; ++i) {
        double delta = x[i] - mean;
        mean += delta / (double)(i + 1);
        double after = x[i] - mean;
        double term = delta * after;
        m2 += term;
    }
    out[0] = mean;
    out[1] = m2;
}

}  /* extern "C" */
"""


class _WindowDesc(ctypes.Structure):
    _fields_ = [
        ("first", ctypes.c_int),
        ("length", ctypes.c_int),
        ("letters", ctypes.c_int),
        ("scorable", ctypes.c_int),
        ("ntri", ctypes.c_int),
        ("nbi", ctypes.c_int),
        ("ntri_tok", ctypes.c_int),
        ("nbi_tok", ctypes.c_int),
        ("tri_tok", ctypes.c_int * MAX_TOKENS),
        ("bi_tok", ctypes.c_int * MAX_TOKENS),
        ("cipher", ctypes.c_byte * MAX_LENGTH),
        ("tripos", ctypes.c_ushort * MAX_LENGTH),
        ("bipos", ctypes.c_ushort * MAX_LENGTH),
    ]


class _ClimbDesc(ctypes.Structure):
    _fields_ = [
        ("nphases", ctypes.c_int),
        ("phases", ctypes.c_int * MAX_PHASES),
        ("max_pairs", ctypes.c_int),
        ("max_passes", ctypes.c_int),
        ("nwin", ctypes.c_int),
        ("maxlen", ctypes.c_int),
        ("min_gain", ctypes.c_double),
    ]


_LIBRARY: Any = None
_LOAD_ERROR: str | None = None
# Settings per kernel launch inside one chunk call; short launches keep a
# display watchdog from ever firing and cost nothing measurable.
LAUNCH_BATCH = 8192


def cache_directory() -> pathlib.Path:
    configured = os.environ.get("ENIGMA_ATTACK_CUDA_CACHE")
    if configured:
        return pathlib.Path(configured)
    return pathlib.Path.home() / ".cache" / "enigma-attack" / "cuda"


def _nvcc() -> str | None:
    found = shutil.which("nvcc")
    if found:
        return found
    candidate = pathlib.Path("/usr/local/cuda/bin/nvcc")
    return str(candidate) if candidate.exists() else None


NVCC_FLAGS = (
    "-O3", "-arch=native", "-shared", "-Xcompiler", "-fPIC,-ffp-contract=off",
    "-fmad=false", "-prec-div=true", "-prec-sqrt=true",
)


def library_path(nvcc: str) -> pathlib.Path:
    version = subprocess.run([nvcc, "--version"], capture_output=True, text=True, check=True).stdout
    digest = hashlib.sha256(
        "\0".join([CUDA_SOURCE, version, *NVCC_FLAGS]).encode("utf-8")
    ).hexdigest()[:16]
    return cache_directory() / f"stecker_cuda-{digest}.so"


def _load() -> Any:
    """Compile (once per source and toolchain) and load the kernel library."""

    global _LIBRARY, _LOAD_ERROR
    if _LIBRARY is not None or _LOAD_ERROR is not None:
        return _LIBRARY
    try:
        if np is None:
            raise RuntimeError("numpy is not installed")
        nvcc = _nvcc()
        if nvcc is None:
            raise RuntimeError("nvcc was not found on PATH or in /usr/local/cuda/bin")
        target = library_path(nvcc)
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            source = target.with_suffix(".cu")
            source.write_text(CUDA_SOURCE, encoding="utf-8")
            partial = target.with_suffix(f".{os.getpid()}.tmp")
            completed = subprocess.run(
                [nvcc, *NVCC_FLAGS, "-o", str(partial), str(source)],
                capture_output=True, text=True,
            )
            if completed.returncode != 0:
                raise RuntimeError(f"nvcc failed: {completed.stderr.strip()}")
            os.replace(partial, target)
        library = ctypes.CDLL(str(target))
        library.ec_last_error.restype = ctypes.c_char_p
        library.ec_device_count.restype = ctypes.c_int
        library.ec_window_desc_size.restype = ctypes.c_int
        library.ec_climb_desc_size.restype = ctypes.c_int
        library.ec_create.argtypes = [
            ctypes.POINTER(_ClimbDesc), ctypes.POINTER(_WindowDesc),
            ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p),
        ]
        library.ec_run.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p,
            ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ]
        library.ec_destroy.argtypes = [ctypes.c_void_p]
        library.ec_destroy.restype = None
        library.ec_tables.argtypes = [
            ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p, ctypes.c_int,
            ctypes.c_int, ctypes.c_void_p,
        ]
        library.ec_welford.argtypes = [ctypes.c_void_p, ctypes.c_longlong, ctypes.c_void_p]
        library.ec_welford.restype = None
        library.ec_device_info.argtypes = [ctypes.c_char_p, ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
        if library.ec_window_desc_size() != ctypes.sizeof(_WindowDesc) or (
            library.ec_climb_desc_size() != ctypes.sizeof(_ClimbDesc)
        ):
            raise RuntimeError("the kernel library's structure layout does not match this module")
        if library.ec_device_count() < 1:
            raise RuntimeError("no CUDA device is available")
        _LIBRARY = library
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        _LOAD_ERROR = str(error)
    return _LIBRARY


def available() -> bool:
    return _load() is not None


def unavailable_reason() -> str | None:
    _load()
    return _LOAD_ERROR


def _require() -> Any:
    library = _load()
    if library is None:
        raise RuntimeError(f"the cuda climb engine is unavailable: {_LOAD_ERROR}")
    return library


def _check(status: int) -> None:
    if status != 0:
        raise RuntimeError(f"cuda climb: {_LIBRARY.ec_last_error().decode()}")


def device_info() -> dict[str, Any]:
    library = _require()
    name = ctypes.create_string_buffer(256)
    timeout = ctypes.c_int(0)
    _check(library.ec_device_info(name, 256, ctypes.byref(timeout)))
    return {"name": name.value.decode(), "kernel_exec_timeout": bool(timeout.value)}


def pairwise_plan(count: int) -> list[int]:
    """numpy's pairwise-summation recursion over ``count`` terms, in postorder.

    A non-negative entry is a leaf of that many terms (summed with eight
    accumulators from 8 terms up, sequentially below); ``-1`` adds the two
    partial sums above it.  numpy splits a block of more than 128 terms at half
    its length rounded down to a multiple of eight.
    """

    if count <= 128:
        return [count]
    half = count // 2
    half -= half % 8
    return pairwise_plan(half) + pairwise_plan(count - half) + [-1]


def rotor_bytes(names: Sequence[str], reflector: Sequence[int]) -> tuple[bytes, int, int]:
    """Forward and reverse offset tables of a wheel order, its reflector and notch masks."""

    wheels = [enigma_fast.rotor_tables(name) for name in names]
    data = bytearray()
    for wheel in wheels:
        for row in wheel.forward:
            data.extend(row)
    for wheel in wheels:
        for row in wheel.reverse:
            data.extend(row)
    data.extend(reflector)
    middle = sum(1 << notch for notch in wheels[1].notches)
    right = sum(1 << notch for notch in wheels[2].notches)
    return bytes(data), middle, right


def settings_array(rule: Any, names: Sequence[str], starts: Sequence[Sequence[int]]) -> "np.ndarray":
    """``rule.settings(names, starts)`` as an ``(n, 6)`` array: rings, then start.

    Built with numpy in the same order (start, then middle phase, then right
    ring), so the row index is the CPU sweep's ``local`` index.
    """

    starts_array = np.asarray(starts, dtype=np.int64).reshape(-1, 3)
    rings = np.asarray(rule.right_rings, dtype=np.int64)
    phases = rule.middle_phases(names[1])
    held_left, held_middle = rule.held[0], rule.held[1]
    n, r = len(starts_array), len(rings)
    if phases is None:
        out = np.empty((n, r, 6), dtype=np.int64)
        out[:, :, 0] = held_left
        out[:, :, 1] = held_middle
        out[:, :, 2] = rings[None, :]
        out[:, :, 3:] = starts_array[:, None, :]
        return out.reshape(-1, 6)
    phase = np.asarray(phases, dtype=np.int64)
    p = len(phase)
    out = np.empty((n, p, r, 6), dtype=np.int64)
    out[..., 0] = held_left
    out[..., 1] = (phase[None, :, None] - starts_array[:, 1, None, None]) % 26
    out[..., 2] = rings[None, None, :]
    out[..., 3] = ((starts_array[:, 0] + held_left) % 26)[:, None, None]
    out[..., 4] = phase[None, :, None]
    out[..., 5] = starts_array[:, 2, None, None]
    return out.reshape(-1, 6)


def position_tables(
    names: Sequence[str], settings: "np.ndarray", length: int, reflector: Sequence[int]
) -> "np.ndarray":
    """The GPU's per-position tables for each setting row, ``(n, length * 26)``."""

    library = _require()
    rotors, middle, right = rotor_bytes(names, reflector)
    rows = np.ascontiguousarray(np.asarray(settings, dtype=np.uint8).reshape(-1, 6))
    out = np.empty((len(rows), length * 26), dtype=np.uint8)
    if len(rows) == 0:
        return out
    _check(library.ec_tables(
        rotors, middle, right, rows.ctypes.data, len(rows), length, out.ctypes.data
    ))
    return out


def welford(scores: "np.ndarray") -> tuple[int, float, float]:
    """``(count, mean, m2)`` exactly as the CPU sweep's streaming update computes them."""

    library = _require()
    values = np.ascontiguousarray(scores, dtype=np.float64)
    out = (ctypes.c_double * 2)()
    library.ec_welford(values.ctypes.data, len(values), out)
    return len(values), out[0], out[1]


class CudaClimber:
    """The configured climb over one message, run for many rotor settings at once.

    Mirrors what ``stecker_sweeps`` does per setting with the batched engine:
    without ``settings['window']`` the whole body is climbed with
    ``BatchedClimber`` and scored per letter; with it, each window is climbed and
    the higher per-letter window score wins (an exact tie keeps the earlier
    window), with evaluations summed over the windows.
    """

    def __init__(
        self,
        bigram: Sequence[float],
        combined: Sequence[float],
        body: Sequence[int],
        settings: Mapping[str, Any],
        reflector: Sequence[int],
    ) -> None:
        library = _require()
        if settings.get("split") is not None:
            raise ValueError(
                "the cuda engine does not implement the split-point climb "
                "(stecker_split.SplitClimber); use climb.engine 'batched'"
            )
        phases = list(settings["phases"])
        if not phases or len(phases) > MAX_PHASES:
            raise ValueError(f"the cuda engine runs 1 to {MAX_PHASES} climb phases, not {len(phases)}")
        for phase in phases:
            if phase not in OBJECTIVES:
                raise ValueError(f"unknown climb objective: {phase!r}")
        if len(body) > MAX_LENGTH:
            raise ValueError(f"the cuda engine climbs bodies of at most {MAX_LENGTH} letters")
        self.body = list(body)
        self.reflector = list(reflector)
        self.windowed = settings.get("window") is not None
        self.windows = climb_windows(len(body), settings.get("window"))
        descriptors = (_WindowDesc * len(self.windows))()
        scorable = []
        for descriptor, (_, first, stop) in zip(descriptors, self.windows):
            part = self.body[first:stop]
            valid = [value >= 0 for value in part]
            letters = sum(valid)
            trigram = [
                t for t in range(len(part)) if t >= 2 and valid[t] and valid[t - 1] and valid[t - 2]
            ]
            bigram_positions = [
                t for t in range(len(part))
                if t >= 1 and valid[t] and valid[t - 1] and not (t >= 2 and valid[t - 2])
            ]
            descriptor.first = first
            descriptor.length = len(part)
            descriptor.letters = letters
            descriptor.scorable = int(letters >= 2)
            descriptor.ntri = len(trigram)
            descriptor.nbi = len(bigram_positions)
            for name, positions in (("tri", trigram), ("bi", bigram_positions)):
                plan = pairwise_plan(len(positions))
                if len(plan) > MAX_TOKENS:
                    raise ValueError("the pairwise plan does not fit the kernel's token table")
                setattr(descriptor, f"n{name}_tok", len(plan))
                getattr(descriptor, f"{name}_tok")[: len(plan)] = plan
            descriptor.cipher[: len(part)] = [value if value >= 0 else -1 for value in part]
            descriptor.tripos[: len(trigram)] = trigram
            descriptor.bipos[: len(bigram_positions)] = bigram_positions
            scorable.append(letters >= 2)
        if not any(scorable):
            raise ValueError("no climb window holds two scorable letters")
        self.scorable = scorable
        climb = _ClimbDesc()
        climb.nphases = len(phases)
        climb.phases[: len(phases)] = [OBJECTIVES[phase] for phase in phases]
        climb.max_pairs = int(settings["max_pairs"])
        climb.max_passes = int(settings["max_passes"])
        climb.min_gain = float(settings["minimum_gain"])
        climb.nwin = len(self.windows)
        climb.maxlen = max(stop - first for _, first, stop in self.windows)
        self._bigram = np.ascontiguousarray(bigram, dtype=np.float64)
        self._combined = np.ascontiguousarray(combined, dtype=np.float64)
        if self._bigram.shape != (676,) or self._combined.shape != (17576,):
            raise ValueError("the n-gram tables must hold 676 and 17,576 entries")
        handle = ctypes.c_void_p()
        _check(library.ec_create(
            ctypes.byref(climb), descriptors, self._bigram.ctypes.data,
            self._combined.ctypes.data, ctypes.byref(handle),
        ))
        self._handle = handle
        self._library = library

    def close(self) -> None:
        if getattr(self, "_handle", None):
            self._library.ec_destroy(self._handle)
            self._handle = None

    def __del__(self) -> None:  # pragma: no cover - interpreter shutdown order varies
        try:
            self.close()
        except Exception:
            pass

    def climb_windows_raw(
        self, names: Sequence[str], settings: "np.ndarray"
    ) -> tuple["np.ndarray", "np.ndarray", "np.ndarray"]:
        """Per (setting, window): final plugboard, evaluations and score per letter."""

        rotors, middle, right = rotor_bytes(names, self.reflector)
        rows = np.ascontiguousarray(np.asarray(settings, dtype=np.uint8).reshape(-1, 6))
        count, windows = len(rows), len(self.windows)
        boards = np.empty((count, windows, 26), dtype=np.uint8)
        evaluations = np.empty((count, windows), dtype=np.int32)
        scores = np.empty((count, windows), dtype=np.float64)
        if count:
            _check(self._library.ec_run(
                self._handle, rotors, middle, right, rows.ctypes.data, count, LAUNCH_BATCH,
                boards.ctypes.data, evaluations.ctypes.data, scores.ctypes.data,
            ))
        return boards, evaluations, scores

    def climb_settings(
        self, names: Sequence[str], settings: "np.ndarray"
    ) -> tuple["np.ndarray", "np.ndarray", "np.ndarray", "np.ndarray"]:
        """Climb every row of ``settings`` (rings, then start, as from :func:`settings_array`).

        Returns the winning plugboards ``(n, 26)``, the evaluations summed over
        the windows, the winning score per letter, and the winning window index.
        """

        boards, evaluations, scores = self.climb_windows_raw(names, settings)
        count = len(scores)
        winner = np.zeros(count, dtype=np.int64)
        best = np.full(count, -np.inf)
        seen = False
        for index, scorable in enumerate(self.scorable):
            if not scorable:
                continue
            if not seen:
                winner[:] = index
                best = scores[:, index].copy()
                seen = True
                continue
            better = scores[:, index] > best
            winner[better] = index
            best = np.where(better, scores[:, index], best)
        rows = np.arange(count)
        total = evaluations[:, self.scorable].astype(np.int64).sum(axis=1)
        return boards[rows, winner].astype(np.int64), total, best, winner

    def climb_one(
        self, names: Sequence[str], rings: Sequence[int], start: Sequence[int]
    ) -> tuple[list[int], int, float, str]:
        """One setting: plugboard, evaluations, score per letter, window name."""

        boards, evaluations, scores, winner = self.climb_settings(
            names, np.asarray([list(rings) + list(start)])
        )
        return (
            [int(x) for x in boards[0]],
            int(evaluations[0]),
            float(scores[0]),
            self.windows[int(winner[0])][0],
        )

    def chunk(
        self, names: Sequence[str], settings: "np.ndarray", keep: int
    ) -> dict[str, Any]:
        """The chunk record fields ``stecker_sweeps._worker_chunk`` returns, for these settings."""

        boards, evaluations, scores, winner = self.climb_settings(names, settings)
        count = len(scores)
        _, mean, m2 = welford(scores)
        best = float(scores.max()) if count else -float("inf")
        order = np.lexsort((np.arange(count), -scores))[:keep]
        top = []
        for local in order.tolist():
            plugboard = [int(x) for x in boards[local]]
            row = settings[local]
            top.append(
                {
                    "local": local,
                    "score_per_letter": float(scores[local]),
                    "rotor_order": list(names),
                    "rings": [int(x) for x in row[:3]],
                    "start": [int(x) for x in row[3:]],
                    "plugboard": plugboard,
                    "plugboard_pairs": sum(1 for x in range(26) if plugboard[x] > x),
                    "evaluations": int(evaluations[local]),
                    **({"window": self.windows[int(winner[local])][0]} if self.windowed else {}),
                }
            )
        return {"evaluated": count, "mean": mean, "m2": m2, "max": best, "top": top}
