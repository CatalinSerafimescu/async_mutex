# async_mutex

[![Linux](https://github.com/CatalinSerafimescu/async_mutex/actions/workflows/ci-linux.yml/badge.svg)](https://github.com/CatalinSerafimescu/async_mutex/actions/workflows/ci-linux.yml)
[![Linux libc++](https://github.com/CatalinSerafimescu/async_mutex/actions/workflows/ci-linux-libcxx.yml/badge.svg)](https://github.com/CatalinSerafimescu/async_mutex/actions/workflows/ci-linux-libcxx.yml)
[![Windows](https://github.com/CatalinSerafimescu/async_mutex/actions/workflows/ci-windows.yml/badge.svg)](https://github.com/CatalinSerafimescu/async_mutex/actions/workflows/ci-windows.yml)
[![macOS](https://github.com/CatalinSerafimescu/async_mutex/actions/workflows/ci-macos.yml/badge.svg)](https://github.com/CatalinSerafimescu/async_mutex/actions/workflows/ci-macos.yml)
[![Coverage](https://codecov.io/gh/CatalinSerafimescu/async_mutex/branch/main/graph/badge.svg)](https://codecov.io/gh/CatalinSerafimescu/async_mutex)
[![C++23](https://img.shields.io/badge/C%2B%2B-23-blue)](https://en.cppreference.com/w/cpp/23)

[![License: AGPL-3.0-or-later](https://img.shields.io/badge/license-AGPL--3.0--or--later-blue.svg)](LICENSE)
[![Commercial license available](https://img.shields.io/badge/commercial-available-blue)](LICENSE-COMMERCIAL.md)

A header-only, awaitable mutex for C++23 coroutines and standalone [Asio](https://think-async.com/Asio/) — lock-free, zero-global-heap, cancellation- and strand-aware. Dual-licensed: AGPL-3.0-or-later, with a [commercial license](LICENSE-COMMERCIAL.md) available.

> 🧩 Extracted from **[fixpp](https://github.com/CatalinSerafimescu/fixpp)** — a modern, low-latency C++ FIX protocol engine built on C++23 coroutines and standalone Asio. If you like the allocation discipline and lock-free design here, that's where it comes from.

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

## Testing & coverage

The full `sync_*` test matrix (46 tests) — uncontended/contended latency, FIFO fairness, cancellation, strand-reap/drain, PMR fallback, the layout golden, and dedicated ASan/UBSan/TSan lanes — runs on every CI platform. Header coverage is **~91% line / ~78% branch** (scoped to `async_mutex.hpp`, the only production code). The remaining uncovered lines are defensive `std::terminate()` traps (witnessed by death tests) plus a few unreachable/uninjectable arms — each carries a written waiver in [docs/COVERAGE.md](docs/COVERAGE.md), so no uncovered line is a genuine untested path.

## Requirements

- A C++23 compiler (`<coroutine>`, `<expected>`, `<memory_resource>`).
- Standalone Asio (developed against `asio/1.38.0`); Boost is **not** required.

## Consuming this library

Header-only — link the `catseraf::async_mutex` target, then `#include "catseraf/sync/async_mutex.hpp"`. You supply [standalone Asio](https://think-async.com/Asio/) yourself (Conan / vcpkg / `find_package` / FetchContent); the exported package config declares it via `find_dependency(asio)`. Pick whichever integration you use:

**FetchContent**

```cmake
include(FetchContent)
FetchContent_Declare(async_mutex
  GIT_REPOSITORY https://github.com/CatalinSerafimescu/async_mutex.git
  GIT_TAG main)                       # or a released tag
FetchContent_MakeAvailable(async_mutex)

target_link_libraries(your_app PRIVATE catseraf::async_mutex)
```

**Install + `find_package`**

```bash
cmake -S . -B build
cmake --install build --prefix /path/to/prefix
```

```cmake
find_package(catseraf-async-mutex CONFIG REQUIRED)   # declares find_dependency(asio)
target_link_libraries(your_app PRIVATE catseraf::async_mutex)
```

**`add_subdirectory`** (vendored copy)

```cmake
add_subdirectory(external/async_mutex)
target_link_libraries(your_app PRIVATE catseraf::async_mutex)
```

When consumed via FetchContent / `add_subdirectory`, this project's tests and install rules are off by default (they enable only when async_mutex is the top-level project; force install with `-DASYNC_MUTEX_INSTALL=ON`). Conan Center packaging is planned.

## License

Dual-licensed:

- **[AGPL-3.0-or-later](LICENSE)** for open-source use.
- **[Commercial license](LICENSE-COMMERCIAL.md)** for use in proprietary/closed-source products without the AGPL copyleft obligations.

The lock-free state-encoding core is derived from the **BSL-1.0** design published by Lewis Baker in [cppcoro](https://github.com/lewissbaker/cppcoro) and independently described in [avast/asio-mutex](https://github.com/avast/asio-mutex); that attribution is carried in the header.
