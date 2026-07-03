# Extraction & Release Plan — `catseraf::sync::async_mutex`

Plan for lifting `async_mutex` out of [fixpp](https://github.com/CatalinSerafimescu/fixpp)
into this standalone repo, wiring up cross-platform CI + coverage, and publishing it as
a **public Conan Center** package.

> **Do not start until the active fixpp feature (`058-async-mutex-hardening`) is merged.**
> Extract from a stable, hardened header — not mid-flight. Every source path below refers to
> the fixpp submodule at `research/G19-fix-fpml-iso20022/library/`.

---

## Phase 0 — Prerequisites (on the fixpp side, before extraction)

- [x] `058-async-mutex-hardening` merged (AM-P1 Treiber free-list redesign landed; the header is final). — fixpp `edad623` + close-out `082ae30`.
- [x] Full `sync_*` suite green on fixpp CI (sanitizer + stress lanes included). — merged via #162; hardening close-out.
- [x] Decide the **error-type strategy** (see Phase 1, the load-bearing decision). — inline 3-code `enum class error`.

---

## Phase 1 — Header extraction & decoupling

**Source:** `include/fixpp/core/sync/async_mutex.hpp` (1221 lines, all bodies inline).
Its *only* non-std / non-Asio include is `#include "fixpp/core/error.hpp"`.

- [x] Copy the header to `include/catseraf/sync/async_mutex.hpp`.
- [x] **Inline the 3 needed error codes into the header — do NOT copy the 1033-line
      `fixpp::core::error` enum, and do NOT add a separate `error.hpp`.** async_mutex references
      exactly three codes: `sync_lock_aborted`, `sync_lock_drained`, `sync_lock_alloc_failed`.
      Define a small `enum class error : std::uint8_t { lock_aborted = 1, lock_drained,
      lock_alloc_failed };` (drop the now-redundant `sync_` prefix) directly in
      `namespace catseraf::sync`, and keep `expected_t<T> = std::expected<T, error>`. True
      single-file, zero-dependency-beyond-Asio. *(Optional polish: give it a `std::error_category`
      so codes interop with `std::error_code`; not required.)*
- [x] Rename namespace `fixpp::sync` → `catseraf::sync` throughout; drop the `fixpp::core::error`
      qualifier (references become `error::lock_aborted`, etc.). Also renamed the test-seam macro
      `FIXPP_ASYNC_MUTEX_TEST_SEAM` → `CATSERAF_ASYNC_MUTEX_TEST_SEAM` (load-bearing for Phase 2 tests).
- [x] Generalize the header banner comments (keep the **BSL-1.0 attribution** to Lewis Baker /
      cppcoro / avast-asio-mutex — it is mandatory; strip fixpp-specific spec/errata anchors or
      relocate them to a `docs/DESIGN.md`). — banner generalized; design anchors + errata E-1/E-5
      relocated to `docs/DESIGN.md`. Per-site invariant anchors left in place (surgical).
- [x] **Acceptance:** the header compiles standalone against only `asio/1.38.0` + a C++23 stdlib —
      no fixpp include remains. (`grep -r fixpp include/` returns nothing.) — verified: `grep -rin fixpp
      include/` empty; `-fsyntax-only -std=c++23` OK on **GCC 13** and **Clang 22** (libstdc++), all
      layout-golden static_asserts fire and pass.

---

## Phase 2 — Tests

**Source:** `tests/sync/`. Bring the **async_mutex** tests; consciously scope out the unrelated ones.

- [ ] **In scope (async_mutex):** the `sync_*` seams —
      uncontended/contended latency, fifo_fairness, contention_stress, executor_compat,
      dispatch_vs_post, cross_strand_acquire, guard_destructive_move, unlock_reaper_splice,
      result_write_race, cancellation_mid_wait, race_cancel_pre_drain, race_multi_cancel,
      race_cancel_during_resume, residual_cancel_graceful, tsan_clean, asan_clean, halo_firing,
      pmr_fallback, slot_allocator_storage, destructor_release_death, cancel_and_drain(+concurrent),
      drain_latch_holder_lifecycle, in_flight_acquirer_coverage, drain_awaitable_cancellation,
      drain_strand_local_reap, drain_immediate_destroy, drain_reentrant_during_active,
      drain_onstrand_cancel, drain_predrain_holder, async_mutex_layout_golden, arm64_weak_memory,
      consumer_contract_compile, no_std_mutex_ci_gate. Plus `sync_test_support.hpp` + `fixtures/`.
- [ ] **Out of scope (confirmed, not a dependency):** `test_atomic_shared_ptr_primitive.cpp` /
      `test_atomic_shared_ptr_concurrency.cpp` test the **046 `atomic_shared_ptr` primitive**.
      Verified: `async_mutex.hpp` uses **zero `shared_ptr`** — `atomic_shared_ptr` is NOT a
      dependency and is **not needed even for libc++** builds of async_mutex (the libc++ fallback
      matters only for fixpp's `session`/`engine`/`tls`/`transport`, which hold `atomic<shared_ptr>`).
      **Leave `atomic_shared_ptr` + its tests in fixpp.** It's a clean standalone lift on its own
      merits if you later want it as `catseraf::sync` family member #2 — independent of this package.
- [ ] Audit every ported test's `#include`s for residual fixpp coupling (error codes, core helpers,
      the layout-golden's `sizeof` constants) and rewire to the new namespace / error type.
- [ ] Port the `add_sync_test()` registration + LABELS (sanitizer/stress/death groupings) from
      `tests/sync/CMakeLists.txt` into a standalone `tests/CMakeLists.txt`.
- [ ] **GoogleTest** via Conan (`gtest/1.15.x`) or FetchContent — pick one and pin it.
- [ ] **Acceptance:** `ctest` green locally on the primary toolchain; layout-golden `sizeof`
      asserts pass unchanged (they guard the 256 B slot / ≤96 B awaiter invariants).

---

## Phase 3 — Build system

- [ ] Root `CMakeLists.txt`: `INTERFACE` target `catseraf::async_mutex`, `cxx_std_23`,
      install + export set for `find_package(catseraf-async-mutex)`.
- [ ] `option(ASYNC_MUTEX_BUILD_TESTS)` (default ON when top-level, OFF when consumed).
- [ ] CMake presets for the CI lanes: base, `asan`, `tsan`, `ubsan`, `coverage`, and a
      `libc++` preset (clang + `-stdlib=libc++`).
- [ ] Wire Asio in via Conan `CMakeDeps` (no bundled Asio).

---

## Phase 4 — GitHub Actions CI (`.github/workflows/`)

**Approach:** one workflow file **per platform** so each yields its own status badge
(GitHub badges are per-workflow, not per-job). Each builds + `ctest`s the suite.

- [ ] `ci-linux.yml` — Ubuntu, GCC (libstdc++). Debug + Release; asan/tsan/ubsan lanes; stress.
- [ ] `ci-linux-libcxx.yml` — Ubuntu, Clang + libc++. Same lanes. (Catches libc++ `<expected>` /
      coroutine divergences early.)
- [ ] `ci-windows.yml` — Windows, MSVC (latest). Debug + Release. (ASan optional on MSVC; TSan N/A.)
- [ ] `ci-macos.yml` — macOS, AppleClang **and/or** Homebrew LLVM. Release + asan/ubsan.
- [ ] `coverage.yml` — GCC `--coverage` or `clang` + `llvm-cov`, upload to **Codecov** (or Coveralls).
- [ ] Each workflow installs deps via Conan (Asio, GoogleTest), configures the matching preset.

> **⚠ C++23 toolchain risk to validate first (spike before writing the matrix):**
> `std::expected` + coroutine maturity varies by platform. Rough floors: GCC ≥ 12, Clang ≥ 16–17
> (libc++ `<expected>` needs a recent libc++), MSVC ≥ 19.35, **AppleClang is the weakest link** —
> may need Homebrew LLVM on macOS. Confirm the real minimums and pin CI images accordingly; this
> decides whether macOS uses AppleClang or LLVM.

---

## Phase 5 — README badges

Add a badge row under the title. Targets:

- [ ] **Linux** — `ci-linux.yml` status
- [ ] **Linux libc++** — `ci-linux-libcxx.yml` status
- [ ] **Windows** — `ci-windows.yml` status
- [ ] **macOS** — `ci-macos.yml` status
- [ ] **Coverage** — Codecov/Coveralls badge
- [ ] **License** — AGPL-3.0-or-later (shields.io) + a note that a commercial license is available
- [ ] *(later)* **Conan Center** version badge once published

Format: GitHub Actions badge = `![Linux](https://github.com/CatalinSerafimescu/async_mutex/actions/workflows/ci-linux.yml/badge.svg)`.

---

## Phase 6 — Public Conan Center (high-level — details deferred)

Not detailed here by request; the shape:

- [ ] Recipe: header-only (`package_type = "header-library"`, `package_id → info.clear()`),
      `requires("asio/…", transitive_headers=True)`, `check_min_cppstd(23)`, `test_package/`.
- [ ] **Name availability** on Conan Center (`async-mutex` vs `catseraf-async-mutex`) — check before PR.
- [ ] **CCI submission path:** fork `conan-io/conan-center-index`, add `recipes/<name>/all/` +
      `config.yml`, pass the CCI hooks + their CI matrix, address reviewer feedback.
- [ ] **Gate:** only submit once the API is stable, the header is fully standalone (Phase 1 done),
      and the package name is decided. Align the Asio version pin with fixpp to avoid diamond conflicts.
- [ ] Before CCI, a **self-hosted / local remote** (`conan create` + `conan upload`) is enough to
      consume it back into fixpp for validation.

---

## Phase 7 — Consume back into fixpp

- [ ] Replace fixpp's vendored `async_mutex.hpp` with `requires("<pkg>/<ver>")`; link
      `catseraf::async_mutex`; delete the in-tree copy + its `tests/sync/` async_mutex tests.
- [ ] Keep fixpp's Asio pin aligned with the package's.

---

## Decisions

**Settled:**
- ✅ **Error type:** inline a 3-code `enum class error` in `async_mutex.hpp` (no separate `error.hpp`).
- ✅ **`atomic_shared_ptr`:** out of scope — verified not a dependency of async_mutex; stays in fixpp.

**Open (resolve at kickoff):**
1. **Conan Center name:** `async-mutex` vs `catseraf-async-mutex`.
2. **macOS compiler:** AppleClang vs Homebrew LLVM — settled by the Phase 4 C++23 spike.
3. **GoogleTest source:** Conan pin vs FetchContent.
