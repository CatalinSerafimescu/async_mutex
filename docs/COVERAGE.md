# Coverage rationale & waiver ledger — `async_mutex.hpp`

This document defends the coverage number for the library's only production code,
`include/catseraf/sync/async_mutex.hpp` (header-only). It is persisted here on
purpose: the authoritative origin records (below) are **local-only / gitignored**
in the source project and do not travel with the extracted package. If anyone
challenges why coverage is not 100%, this is the answer.

## Numbers (origin, fixpp feature 058, fresh llvm-cov profraw)

| Metric   | Raw            | Artifact-adjusted† |
|----------|----------------|--------------------|
| Line     | **91.1%** (586/643) | ≈ 92.9% |
| Branch   | **72.3%** (81/112)  | ≈ 78.6% |
| Function | 27/29          | —       |
| Region   | 73.9%          | —       |

† `push_residual` is an anonymous-namespace (internal-linkage) function; llvm-cov's
aggregate attributes a 0% instance from one TU even though the two call sites are hit
hundreds of thousands of times and `sync_fifo_across_cycles` covers the body. See
"measurement artifact" below.

**The raw branch number is low BY CONSTRUCTION**: this primitive deliberately adds
defensive impossible-state `std::terminate()` traps and reachable-but-forced-interleaving
CAS arms whose correctness is carried by death-tests and seam witnesses, not by the
seam-OFF coverage lane. Below-threshold coverage is admissible only because every
uncovered line/branch carries a written risk assessment and **no uncovered branch is a
genuine untested error path**.

## Why uncovered ≠ untested — the four buckets

Every uncovered line/branch falls into exactly one of these:

1. **Measurement artifact (actually covered).** `push_residual` (the residual-FIFO
   splice helper): internal-linkage, so llvm-cov under-reports it on the aggregate;
   the call sites fire 315k+ / 5k+ times and the body lines are hit. Not a real gap.

2. **Defensive impossible-state terminate-traps, witnessed by death tests.** The
   null-`attached_awaiter_` trap in the resume runner, the destructor precondition
   guard, and the chain-walk `granted`-record traps (residual + FIFO walks). These
   `execute → abort()`, so no profraw is flushed → **coverage-uncapturable**. They are
   witnessed by `sync_destructor_release_death` and `sync_am_p3_impossible_state_traps`
   (EXPECT_DEATH), each mutation-killed.

3. **Reachable arms witnessed by forced interleaving (seam), not countable on the
   seam-OFF coverage lane.** These are real, reachable branches whose organic
   occurrence is too rare/flaky to count on the coverage build, so they are pinned
   deterministically by a compile-gated test seam (`CATSERAF_ASYNC_MUTEX_TEST_SEAM`)
   in a separate target. lcov LINE is waived on the seam-OFF lane; correctness is
   witnessed. See F4, F6, W-12, and the acquire-livelock arm below.

4. **Unreachable / uninjectable arms waived with a source-level proof.** See the
   ledger.

## Waiver ledger

Status legend: **WAIVED** = uncovered with written proof (unreachable or uninjectable);
**WITNESSED** = reachable, discharged by a death/seam test (lcov-line waived only on the
seam-OFF lane); **DISCHARGED** = superseded by a real witness or removed in code.

| ID | Arm | Status | Basis |
|----|-----|--------|-------|
| **W-1** | 2nd `draining_` check in `async_lock` initiation (`error::lock_drained` return) | WAIVED | Initiation is synchronous; `draining_` can flip between the two checks only via cross-thread drain/acquire overlap, which is the documented **out-of-contract UNDEFINED** case. The `lock_drained` outcome itself IS exercised by the drain-reap-of-parked-acquirer path. |
| **W-2** | (early) chain-walk `granted` trap | DISCHARGED | Superseded by the `sync_am_p3_impossible_state_traps` EXPECT_DEATH witness. |
| **W-3** | (early) null-awaiter trap | DISCHARGED | Superseded by the same death-test witness. |
| **W-4** | `drain_in_progress_` defensive re-entry arm | WAIVED | No suspension point before the store; the only way to reach it is a cross-thread drain, which is out-of-contract. |
| **W-5** | `cancel_and_drain` finalize-CAS fail / assert | WAIVED | Loop-break invariant: the quiescence loop only exits with both lists empty, so the finalize CAS is invariant (asserted). |
| **W-6** | `store_executor` size-fail arm + `destroy_executor` null-fn guard | WAIVED | `static_assert(sizeof(asio::any_io_executor) <= exec_storage_)`; only `any_io_executor` is ever instantiated, so `if constexpr` compiles the arm out. Structurally unreachable. |
| **W-7** | `on_cancel` `record_ == nullptr` early-return | WAIVED | Slot connect/clear ordering: the cancellation slot is assigned only after `record_` is set and cleared only at the coroutine tail. |
| **W-8** | dead `destroy_handler()` | DISCHARGED | Grep-verified zero call sites → removed in code (not waived at 0%). |
| **W-9** | cancellation-slot `assign()`-throws catch arm (`lock_alloc_failed`) | WAIVED | Reachable-but-uninjectable: the allocation is `std::aligned_alloc` (asio, source-verified), not malloc/`operator new`, so the allocation-counter fault harness cannot trigger it. |
| **W-11** | `push_residual` weak-CAS back-edge (a.k.a. **F7**) | WAIVED | Single-writer: both callers are inside holder-serialized `unlock()`; the only competing `next_drain_head_` writer is the out-of-contract drain exchange. Plus x86 `lock cmpxchg` has no spurious weak-CAS failures (weak==strong) → the back-edge cannot be taken on the coverage lane. |
| **W-12** | chain-walk `queued→granted` CAS-loss arms (`ph = expected_ph`, residual + FIFO walks) | WITNESSED | **Formerly a mislabeled "W-7" waived as "hard to force" — corrected at Gate B.** It is REACHABLE via an `on_cancel`-wins-grant race. Discharged by the `sync_async_mutex_chain_walk_cas_loss` seam witnesses (FIFO + residual), oracle = cancelled future resolves aborted AND slot refcount == 0 (membership released exactly once), mutation cross-leg isolated. |
| **F4** | `unlock` fast-path terminal-CAS-fail → recursive-unlock | WITNESSED | Reachable in-contract (a waiter arriving in the terminal-CAS window) but flaky-organic on the seam-OFF lane. Deterministic seam witness (`sync_async_mutex_terminal_cas_recursive_unlock`); lcov-line waived on the seam-OFF lane. |
| **F6** | post-FIFO-walk terminal-CAS-fail → recursive-unlock (all-cancelled chain) | WITNESSED | Same as F4; sibling seam witness, mutation cross-leg isolated. |
| **acquire-livelock** | contended-acquire `not_locked`-branch CAS-loss | WITNESSED | A pre-existing livelock (CAS on a stale `old_state`) fixed in 058; the arm is seam-witnessed (`sync_async_mutex_acquire_livelock`) with a bounded-probe oracle. |

**Net:** LIVE proof-waivers = **W-1, W-4, W-5, W-6, W-7, W-9, W-11 (=F7)**. Witnessed
reachable (seam-OFF-lane lcov-line waived) = **F4, F6, W-12, acquire-livelock**.
Discharged in code / by witness = **W-2, W-3, W-8**.

## Coverage lane caveat (why seams don't count)

The coverage build is **seam-OFF** (`CATSERAF_ASYNC_MUTEX_TEST_SEAM` undefined), so the
deterministic interleavings that witness F4/F6/W-12/acquire-livelock run in *separate*
seam-ON targets and their line hits are structurally uncountable on the coverage lane.
This is the same bucket as the AM-P1 ABA seam arms. It is a *countability* caveat, not a
reachability waiver.

## Provenance — authoritative origin records (local-only, gitignored)

These live in the source project and are **not** committed there, hence this copy:

1. **Compressed ledger (waiver IDs)** — origin project memory
   `project_async_mutex_cluster4_hardening.md`.
2. **Authoritative verify record (full per-waiver reasoning)** — the § *Step 4 Coverage
   gate* + § *Waivers* sections of
   `research/G19-fix-fpml-iso20022/library/.specify/decisions/058-async-mutex-hardening-verify.md`.
3. **Coverage-design origin (W-1…W-11 + F4/F6/F7, incl. the empirical-correction
   section)** —
   `research/G19-fix-fpml-iso20022/library/.specify/decisions/058-async-mutex-hardening-coverage-design.md`.

Line-number anchors in the origin records refer to the fixpp header; the code bodies are
identical here, so map arms by function/branch name rather than absolute line.
