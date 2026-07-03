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

- [x] **In scope (async_mutex):** the `sync_*` seams —
      uncontended/contended latency, fifo_fairness, contention_stress, executor_compat,
      dispatch_vs_post, cross_strand_acquire, guard_destructive_move, unlock_reaper_splice,
      result_write_race, cancellation_mid_wait, race_cancel_pre_drain, race_multi_cancel,
      race_cancel_during_resume, residual_cancel_graceful, tsan_clean, asan_clean, halo_firing,
      pmr_fallback, slot_allocator_storage, destructor_release_death, cancel_and_drain(+concurrent),
      drain_latch_holder_lifecycle, in_flight_acquirer_coverage, drain_awaitable_cancellation,
      drain_strand_local_reap, drain_immediate_destroy, drain_reentrant_during_active,
      drain_onstrand_cancel, drain_predrain_holder, async_mutex_layout_golden, arm64_weak_memory,
      consumer_contract_compile, no_std_mutex_ci_gate. Plus `sync_test_support.hpp` + `fixtures/`.
- [x] **Out of scope (confirmed, not a dependency):** `test_atomic_shared_ptr_primitive.cpp` /
      `test_atomic_shared_ptr_concurrency.cpp` test the **046 `atomic_shared_ptr` primitive**.
      Verified: `async_mutex.hpp` uses **zero `shared_ptr`** — `atomic_shared_ptr` is NOT a
      dependency and is **not needed even for libc++** builds of async_mutex (the libc++ fallback
      matters only for fixpp's `session`/`engine`/`tls`/`transport`, which hold `atomic<shared_ptr>`).
      **Leave `atomic_shared_ptr` + its tests in fixpp.** It's a clean standalone lift on its own
      merits if you later want it as `catseraf::sync` family member #2 — independent of this package.
- [x] Audit every ported test's `#include`s for residual fixpp coupling (error codes, core helpers,
      the layout-golden's `sizeof` constants) and rewire to the new namespace / error type.
- [x] Port the `add_sync_test()` registration from `tests/sync/CMakeLists.txt` into a standalone
      `tests/CMakeLists.txt`. **Drop the ctest LABELS** (sanitizer/stress/death groupings) — this
      suite is small and every CI lane runs the full `ctest`, so no label filtering is needed.
- [x] **GoogleTest** via Conan, pinned at **`gtest/1.17.0`** (mirrors the origin's pin; static —
      `gtest*:shared=False`). Settled — not FetchContent.
- [x] **Acceptance:** `ctest` green locally on the primary toolchain; layout-golden `sizeof`
      asserts pass unchanged (they guard the 256 B slot / ≤96 B awaiter invariants).

---

## Phase 3 — Build system (mirror fixpp's Conan + CMakePresets toolchain)

Reuse the origin's proven mechanism verbatim, trimmed to this package's deps: a **dev/test
`conanfile.py`** (a *consumer* recipe — NOT the Phase 6 CCI package recipe), **per-preset Conan
profiles**, and a **`CMakePresets.json`** that consumes the Conan-generated toolchain. The
build/test loop is identical to fixpp's:
`conan install . -pr conan/profiles/<preset> -of build/<preset>` → `cmake --preset <preset>` →
`cmake --build --preset <preset>` → `ctest --preset <preset>`.

- [x] Root `CMakeLists.txt`: `INTERFACE` target `catseraf::async_mutex`, `cxx_std_23`,
      install + export set for `find_package(catseraf-async-mutex)`.
- [x] `option(ASYNC_MUTEX_BUILD_TESTS)` (default ON when top-level, OFF when consumed);
      Werror on (mirrors fixpp's `_base` preset `FIXPP_WERROR=ON`).
- [x] **`conanfile.py`** — a *consumer* recipe modelled on fixpp's (Conan 2):
      `settings = "os", "compiler", "build_type", "arch"`;
      `generators = "CMakeToolchain", "CMakeDeps"`;
      `requires = ["asio/1.38.0", "gtest/1.17.0"]`;
      `default_options = {"gtest*:shared": False}`. Asio is **not** bundled — pulled via `CMakeDeps`.
      (Origin's openssl / otel / pugixml / crc32c / tomlplusplus etc. are all out of scope here.)
- [x] **Conan profiles** under `conan/profiles/` — copy the origin's async_mutex-relevant set,
      trimmed: `linux-clang-{debug,release,asan,ubsan,tsan}`, `linux-gcc-release`,
      `linux-clang-coverage`, `linux-clang-libc++{,-asan,-ubsan,-tsan}`,
      `windows-msvc-{debug,release,asan}`, plus a **net-new** `macos-clang-{release,asan,ubsan}`
      set (no origin equivalent — Homebrew LLVM `clang++`, `compiler.libcxx=libc++`). Each pins the
      exact toolchain and `compiler.cppstd=23`
      (`compiler=clang`/`version=22` + `libcxx=libstdc++11` or `libc++`; or `gcc`/`13`),
      `[buildenv] CC/CXX`, and `[conf] ...cmaketoolchain:generator=Ninja`. Sanitizer flags live
      **inside the profile** (`[buildenv] CXXFLAGS/LDFLAGS` + `[conf] tools.build:cxxflags`/
      `sharedlinkflags`/`exelinkflags`), plus `tools.info.package_id:confs=[...]` so each sanitizer
      profile gets a **distinct Conan cache entry** (else asan/ubsan/tsan share a `package_id` and
      poison each other's link step with the wrong sanitizer runtime).
- [x] **`CMakePresets.json`** — one configure preset per profile (name-matched), all inheriting a
      `_base` (Ninja; `binaryDir=${sourceDir}/build/${presetName}`; `CMAKE_EXPORT_COMPILE_COMMANDS`;
      tests + Werror on). Each sets `CMAKE_BUILD_TYPE`, `CMAKE_C/CXX_COMPILER`, and
      `CMAKE_TOOLCHAIN_FILE=${sourceDir}/build/${presetName}/conan_toolchain.cmake` (written by the
      matching `conan install -of build/<preset>`). Add matching build + test presets.

---

## Phase 4 — GitHub Actions CI (`.github/workflows/`)

**Approach:** mirror the origin's **tier1 / tier2 / tier3-libcxx** *compile + sanitizer* phases,
one workflow file **per platform** (each yields its own status badge — GitHub badges are
per-workflow, not per-job). Keep it **fast and minimal**: bring only the compile + sanitizer
lanes and **drop fixpp's orchestration cruft** — the gate-precheck / relevance-gating jobs, the
python-wheel + binding-sanitizer legs, the ~30 GB disk-reclaim step, and the ctest LABELS. This
suite is ~40 files, so every lane just runs the full `ctest` on every push. Each lane is the
origin's exact flow: install Clang 22 (apt.llvm.org `llvm.sh`) / GCC 13 / libc++-22 as needed →
`conan profile detect` + teach Conan about Clang 22 → `conan install . -pr conan/profiles/<preset>
-of build/<preset>` → `cmake --preset` → `cmake --build --preset` → `ctest --preset`.

- [x] `ci-linux.yml` (≙ **tier1**) — `ubuntu-24.04`, Clang 22 + GCC 13. Preset matrix:
      `linux-clang-{debug,release,asan,ubsan,tsan}` + `linux-gcc-release`.
- [x] `ci-linux-libcxx.yml` (≙ **tier3-libcxx**) — `ubuntu-24.04`, Clang 22 + libc++-22. Preset
      matrix: `linux-clang-libc++{,-asan,-ubsan,-tsan}`. (Catches libc++ `<expected>` / coroutine
      divergences early.)
- [x] `ci-windows.yml` (≙ **tier2**) — `windows-2022`, MSVC. Preset matrix:
      `windows-msvc-{debug,release,asan}` (vcvars + Ninja; TSan N/A on MSVC).
- [x] `coverage.yml` — `ubuntu-24.04`, Clang 22 + `llvm-cov` (origin's `linux-clang-coverage`
      preset): merge profiles → LCOV → upload to **Codecov**. **Scope the report to the header**
      `include/catseraf/sync/async_mutex.hpp` (the only production code — header-only). Target =
      the origin's feature-058 baseline on this exact header: **91.1% line / 72.3% branch**. Add a
      non-brittle floor gate (fail if line < 90% or branch < 71%) so a broken/partial test port is
      caught; echo the actual line%/branch% in the job log.
- [x] `ci-macos.yml` — `macos-14` (Apple Silicon), **Homebrew LLVM** (`brew install llvm`) — NOT
      AppleClang, which lags on C++23 `<expected>` + coroutines. Preset matrix:
      `macos-clang-{release,asan,ubsan}` (TSan is unreliable under the macOS sanitizer runtime).
      Net-new — no origin lane to mirror; reuse the same Conan-profile-per-preset flow.

> **C++23 toolchain spike — RESOLVED by reuse.** The Linux/Windows toolchains already build
> async_mutex **green in fixpp CI**: Clang 22, GCC 13, MSVC 2022, libc++-22, `cppstd=23`,
> `asio/1.38.0`, `gtest/1.17.0`. Pin those versions directly — zero C++23-maturity risk there.
> **macOS is the one net-new lane** (no fixpp precedent): use **Homebrew LLVM**, which sidesteps
> AppleClang's `<expected>`/coroutine gap. Validate the Homebrew LLVM version's C++23 support on
> first CI run and pin it (the `brew install llvm` clang is well ahead of AppleClang).

---

## Phase 5 — README badges

Add a badge row under the title. Targets:

- [x] **Linux** — `ci-linux.yml` status
- [x] **Linux libc++** — `ci-linux-libcxx.yml` status
- [x] **Windows** — `ci-windows.yml` status
- [x] **macOS** — `ci-macos.yml` status
- [x] **Coverage** — Codecov/Coveralls badge
- [x] **License** — AGPL-3.0-or-later (shields.io) + a note that a commercial license is available
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
- ✅ **Toolchains:** reuse fixpp's proven pins verbatim — Clang 22 (apt.llvm.org `llvm.sh`), GCC 13,
  MSVC 2022, libc++-22, Ninja, `compiler.cppstd=23`; deps `asio/1.38.0` + `gtest/1.17.0`. Same
  Conan-profile-per-preset + `CMakePresets.json` (`conan_toolchain.cmake`) mechanism as the origin.
- ✅ **GoogleTest source:** Conan `gtest/1.17.0` (mirrors the origin), static — NOT FetchContent.
- ✅ **macOS lane:** included (net-new — no fixpp precedent). `macos-14` + **Homebrew LLVM**
  (`brew install llvm` clang), `libcxx=libc++`, `cppstd=23`; release + asan/ubsan. AppleClang is
  NOT used (C++23 `<expected>`/coroutine gap).

**Open (resolve at kickoff):**
1. **Conan Center name:** `async-mutex` vs `catseraf-async-mutex`.
