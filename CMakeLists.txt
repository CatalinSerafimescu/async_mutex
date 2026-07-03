cmake_minimum_required(VERSION 3.28)

project(async_mutex VERSION 0.1.0 LANGUAGES CXX)

include(CMakePackageConfigHelpers)
include(GNUInstallDirs)

set(ASYNC_MUTEX_TOP_LEVEL OFF)
if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR)
  set(ASYNC_MUTEX_TOP_LEVEL ON)
endif()

option(ASYNC_MUTEX_BUILD_TESTS "Build tests" ${ASYNC_MUTEX_TOP_LEVEL})
option(ASYNC_MUTEX_WERROR "Enable warnings as errors for tests" OFF)
option(ASYNC_MUTEX_INSTALL "Generate install + export rules" ${ASYNC_MUTEX_TOP_LEVEL})

# A FetchContent / add_subdirectory consumer may already provide asio::asio by
# other means (its own find_package / FetchContent); only look it up ourselves if
# the target isn't already defined.
if(NOT TARGET asio::asio)
  find_package(asio REQUIRED)
endif()

add_library(catseraf_async_mutex INTERFACE)
add_library(catseraf::async_mutex ALIAS catseraf_async_mutex)

target_compile_features(catseraf_async_mutex INTERFACE cxx_std_23)
target_include_directories(catseraf_async_mutex
  INTERFACE
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>
)
target_link_libraries(catseraf_async_mutex INTERFACE asio::asio)

# Export under the short name so the INSTALLED target matches the in-tree ALIAS:
# with NAMESPACE catseraf:: the export would otherwise be
# catseraf::catseraf_async_mutex, breaking find_package consumers that link the
# advertised catseraf::async_mutex.
set_target_properties(catseraf_async_mutex PROPERTIES EXPORT_NAME async_mutex)

# Install/export rules are for top-level (or opt-in) use only. A FetchContent /
# add_subdirectory consumer must NOT have this subproject attach its own install
# + export set to their tree (which also errors if they link us into their own
# exported target). Set -DASYNC_MUTEX_INSTALL=ON to force it on when embedded.
if(ASYNC_MUTEX_INSTALL)

install(
  DIRECTORY include/
  DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
)

install(
  TARGETS catseraf_async_mutex
  EXPORT catseraf-async-mutexTargets
)

install(
  EXPORT catseraf-async-mutexTargets
  FILE catseraf-async-mutexTargets.cmake
  NAMESPACE catseraf::
  DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/catseraf-async-mutex
)

configure_package_config_file(
  ${CMAKE_CURRENT_SOURCE_DIR}/cmake/catseraf-async-mutexConfig.cmake.in
  ${CMAKE_CURRENT_BINARY_DIR}/catseraf-async-mutexConfig.cmake
  INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/catseraf-async-mutex
)

write_basic_package_version_file(
  ${CMAKE_CURRENT_BINARY_DIR}/catseraf-async-mutexConfigVersion.cmake
  VERSION ${PROJECT_VERSION}
  COMPATIBILITY SameMajorVersion
)

install(
  FILES
    ${CMAKE_CURRENT_BINARY_DIR}/catseraf-async-mutexConfig.cmake
    ${CMAKE_CURRENT_BINARY_DIR}/catseraf-async-mutexConfigVersion.cmake
  DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/catseraf-async-mutex
)

endif()  # ASYNC_MUTEX_INSTALL

if(ASYNC_MUTEX_BUILD_TESTS AND EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/tests/CMakeLists.txt")
  enable_testing()
  add_subdirectory(tests)
endif()
