cmake_minimum_required(VERSION 3.16)
project(synapse_abi VERSION 1.0.0 LANGUAGES C)

include(GNUInstallDirs)

add_library(synapse_abi SHARED src/synapse.c)
target_compile_features(synapse_abi PUBLIC c_std_11)
target_compile_definitions(synapse_abi PRIVATE SYNAPSE_ABI_BUILD_SHARED)
target_include_directories(synapse_abi
  PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>
)
set_target_properties(synapse_abi PROPERTIES
  VERSION ${PROJECT_VERSION}
  SOVERSION 1
  OUTPUT_NAME synapse_abi
)

add_library(synapse_abi_static STATIC src/synapse.c)
target_compile_features(synapse_abi_static PUBLIC c_std_11)
target_include_directories(synapse_abi_static
  PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>
)
set_target_properties(synapse_abi_static PROPERTIES OUTPUT_NAME synapse_abi)

add_executable(synapse_abi_test tests/test_synapse.c)
target_link_libraries(synapse_abi_test PRIVATE synapse_abi)

enable_testing()
add_test(NAME synapse_abi_test COMMAND synapse_abi_test)

configure_file(synapse-abi.pc.in synapse-abi.pc @ONLY)
install(TARGETS synapse_abi synapse_abi_static
  LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
  ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
  RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
)
install(DIRECTORY include/ DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})
install(FILES ${CMAKE_CURRENT_BINARY_DIR}/synapse-abi.pc DESTINATION ${CMAKE_INSTALL_LIBDIR}/pkgconfig)
