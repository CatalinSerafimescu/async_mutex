import os

from conan import ConanFile
from conan.tools.build import check_min_cppstd
from conan.tools.files import copy, get
from conan.tools.layout import basic_layout

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
