import os

from conan import ConanFile
from conan.errors import ConanInvalidConfiguration
from conan.tools.build import check_min_cppstd
from conan.tools.files import copy, get
from conan.tools.layout import basic_layout
from conan.tools.scm import Version

required_conan_version = ">=2.1"


class AsyncMutexConan(ConanFile):
    name = "async-mutex"
    description = (
        "Awaitable, header-only, Asio-based asynchronous mutex for C++23 coroutines."
    )
    license = "AGPL-3.0-or-later"
    url = "https://github.com/conan-io/conan-center-index"
    homepage = "https://github.com/CatalinSerafimescu/async_mutex"
    topics = ("mutex", "async", "coroutines", "asio", "concurrency", "header-only")

    package_type = "header-library"
    settings = "os", "arch", "compiler", "build_type"
    no_copy_source = True

    @property
    def _min_cppstd(self):
        return 23

    @property
    def _compilers_minimum_version(self):
        # Best-effort C++23 floors (std::expected + coroutines). Only clang 22 /
        # gcc 13 / MSVC 2022 / Homebrew-LLVM are actually exercised in CI; CCI
        # reviewers may tune these. apple-clang is intentionally absent — the
        # header needs libc++'s <expected>, which AppleClang lags on.
        return {
            "gcc": "13",
            "clang": "17",
            "msvc": "193",
        }

    def layout(self):
        basic_layout(self, src_folder="src")

    def requirements(self):
        # transitive_headers: the public header #includes <asio/...>, so any
        # consumer must see Asio's include dirs at compile time.
        self.requires("asio/1.38.0", transitive_headers=True)

    def package_id(self):
        self.info.clear()

    def validate(self):
        check_min_cppstd(self, self._min_cppstd)
        minimum = self._compilers_minimum_version.get(str(self.settings.compiler))
        if minimum and Version(self.settings.compiler.version) < minimum:
            raise ConanInvalidConfiguration(
                f"{self.ref} requires C++{self._min_cppstd}, which needs "
                f"{self.settings.compiler} >= {minimum} "
                f"(have {self.settings.compiler.version})."
            )

    def source(self):
        get(self, **self.conan_data["sources"][self.version], strip_root=True)

    def package(self):
        copy(
            self,
            "LICENSE",
            self.source_folder,
            os.path.join(self.package_folder, "licenses"),
        )
        copy(
            self,
            "*.hpp",
            os.path.join(self.source_folder, "include"),
            os.path.join(self.package_folder, "include"),
        )

    def package_info(self):
        self.cpp_info.bindirs = []
        self.cpp_info.libdirs = []

        # Match the in-tree CMake package so `find_package` consumers (e.g.
        # fixpp) keep linking the exact target the repo advertises.
        self.cpp_info.set_property("cmake_file_name", "catseraf-async-mutex")
        self.cpp_info.set_property("cmake_target_name", "catseraf::async_mutex")
        self.cpp_info.requires = ["asio::asio"]

        if self.settings.os in ("Linux", "FreeBSD"):
            self.cpp_info.system_libs.append("pthread")
