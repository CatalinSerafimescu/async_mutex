from conan import ConanFile


class AsyncMutexConan(ConanFile):
    name = "async-mutex"
    version = "0.1.0"

    settings = "os", "compiler", "build_type", "arch"

    generators = "CMakeToolchain", "CMakeDeps"

    requires = [
        "asio/1.38.0",
        "gtest/1.17.0",
    ]

    default_options = {
        "gtest*:shared": False,
    }
