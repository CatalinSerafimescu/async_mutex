# async_mutex

A header-only, awaitable mutex for C++23 coroutines and standalone [Asio](https://think-async.com/Asio/) — lock-free, zero-global-heap, cancellation- and strand-aware.

## Overview

`async_mutex` is a single-header mutual-exclusion primitive for C++23 coroutines built on standalone Asio. You `co_await` the lock instead of blocking a thread:

```cpp
asio::awaitable<void> critical_section(async_mutex& m) {
    auto guard = co_await m.async_lock();   // suspends, never blocks the executor
    if (!guard) co_return;                  // unexpected{lock_aborted} if drained/cancelled
    // ... exclusive section ...
}                                           // guard destructor releases + hands off the next waiter
```

It is designed for latency-sensitive, allocation-disciplined systems (it was extracted from a FIX engine's session core): on the uncontended path, and on the contended path when HALO fires, an acquire performs **zero global heap allocations** — waiter state is held frame-local in the awaiter's inline buffer, with a `std::pmr::memory_resource*` fallback for the over-capacity case.

## Features

- **Header-only**, C++23 (`<coroutine>`, `<expected>`), standalone Asio (no Boost).
- **Awaitable API:** `async_lock()` returns `asio::awaitable<expected<async_lock_guard>>`; the guard releases and hands off on scope exit.
- **Error-as-value:** acquisition yields `std::expected` — a drained or cancelled wait returns `unexpected{lock_aborted}` rather than throwing.
- **Lock-free core:** atomic state word with a LIFO waiter list and exchange-based drain; **FIFO/fair** grant order to waiters.
- **Cancellation-aware:** per-waiter three-state phase machine (`queued → granted | cancelled`) integrates with Asio cancellation slots.
- **Strand-aware teardown:** `cancel_and_drain()` for deterministic single-pass quiescence before destruction.
- **Configurable handoff:** `completion_policy::{dispatch, post}` controls inline-vs-post resumption.
- **Bounded footprint:** fixed 512-slot waiter pool; awaiter ≤ 96 B; a compile-time layout-golden static-assert guards the size invariants.

## Status

This repository is being extracted from its origin project. Landing here in order:

1. The `async_mutex.hpp` header.
2. The full test suite (the `sync_*` seams: contention, cancellation, strand-reap, layout-golden, sanitizer and stress lanes).
3. Standalone cleanup — decoupling the internal `error` dependency, simplifying the `fixpp::sync` namespace, and generalizing the header comments.

Until step 3 lands, the header still references `fixpp/core/error.hpp` and lives in `namespace fixpp::sync`.

## Requirements

- A C++23 compiler (`<coroutine>`, `<expected>`, `<memory_resource>`).
- Standalone Asio (developed against `asio/1.38.0`); Boost is **not** required.

## License

Dual-licensed:

- **[AGPL-3.0-or-later](LICENSE)** for open-source use.
- **[Commercial license](LICENSE-COMMERCIAL.md)** for use in proprietary/closed-source products without the AGPL copyleft obligations.

The lock-free state-encoding core is derived from the **BSL-1.0** design published by Lewis Baker in [cppcoro](https://github.com/lewissbaker/cppcoro) and independently described in [avast/asio-mutex](https://github.com/avast/asio-mutex); that attribution is carried in the header.
