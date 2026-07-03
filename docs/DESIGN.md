# `catseraf::sync::async_mutex` — Design Notes

Design and invariant notes for the awaitable mutex. The header
(`include/catseraf/sync/async_mutex.hpp`) keeps the per-site erratum/task
anchors (`E-1`, `048`, `058 T0xx`, `RC-*`) that document each load-bearing
invariant; this file collects the higher-level design context that used to live
in the header banner.

## Algorithm attribution (BSL-1.0)

The lock-free state encoding — `std::atomic<uintptr_t> state_` with
`not_locked` / `locked_no_waiters` sentinels, a LIFO waiter-list pointer in the
high bits, and the acquire / unlock CAS protocol — is derived from the
public-domain / BSL-1.0-licensed design published by Lewis Baker in
[cppcoro](https://github.com/lewissbaker/cppcoro) and independently described in
the [avast/asio-mutex](https://github.com/avast/asio-mutex) repository. The
algorithm core (LIFO push / exchange-based drain / FIFO grant) is due to Lewis
Baker / cppcoro; all additions listed below are original work.

Extensions over that core:

- a mutex-owned residual FIFO (`next_drain_head_`) replacing the awaiter-owned
  `residual_` field (RC-A);
- a three-state per-waiter phase machine — `queued` / `granted` / `cancelled`
  (RC-A);
- strand-local single-pass reap with the `in_flight_resumers_` barrier (048);
- an `active_holders_count_` epoch counter (RC-α); and
- a PMR-aware `slot_allocator` for the cancellation-handler closure (RC-C).

## Erratum E-1 — frame-local awaiter (zero global heap)

The `async_mutex_awaiter` is a frame-local variable inside `async_lock()`'s own
coroutine frame — **not** separately heap-allocated via global `operator new`.
The Asio completion handler produced by `use_awaitable` is stored via
placement-new into the awaiter's inline `slot_storage_` buffer (32 B). This
achieves zero global heap allocation on both the uncontended and contended paths
when `mr == nullptr` and the coroutine HALO elision fires.

## Erratum E-5 (048) — strand-local reap

`cancel_and_drain()` is narrowed to the strand-serialised contract its consumers
actually use. The earlier cross-thread convergence machinery (drain-latch state /
concurrent channel / Dekker handshake / `active_acquirers_count_` / quiescence
park) is removed. The terminal condition (INV-D) is:

    (active_holders_count_ == 0) AND
    (in_flight_resumers_  == 0) AND
    (both lists empty in one pass)

The drain is **uninterruptible** (`disable_cancellation`). Reentrant callers on
the owning strand await `draining_complete_` and then return the terminal
result — never `ok` eagerly.

`in_flight_resumers_` is the use-after-free barrier: the mutex must not be
destroyed until every posted resumer has decremented it. The decrement is
`release`; the drain's terminal read and the destructor guard read it with
`acquire`, establishing the happens-before that makes drain-then-destroy
memory-safe even for a waiter resumed on a different executor.

### Drain contract (caller obligations)

- Call `cancel_and_drain()` on the owning strand, co-located with **all**
  `async_lock` / cancel / `unlock` of the same mutex.
- Drain overlap with another thread's `async_lock` / `unlock` is **undefined**.
- Ordinary cross-thread `async_lock` / `unlock` contention (outside a drain)
  stays supported.

## Layout golden

The header asserts these invariants at compile time; they guard the ABI-ish
storage budget the free-list and HALO paths depend on:

- `sizeof(waiter_pool_slot) == 256` (per-slot pool storage);
- `sizeof(waiter_record) <= 248` (fits the slot storage);
- `sizeof(async_mutex_awaiter) <= 96` (HALO-eligibility budget);
- `alignof(async_mutex_awaiter) >= 8` and `alignof(waiter_record) >= 8` (so the
  low-bit `not_locked` sentinel is distinguishable from a real waiter pointer).
