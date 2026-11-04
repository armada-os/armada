cmake_minimum_required(VERSION 3.20)
project(armada-autohdr VERSION 0.1.0 LANGUAGES C CXX)

include(GNUInstallDirs)
include(CTest)

option(ARMADA_AUTOHDR_FAST_MATH "Match Gamescope's floating-point build flags" ON)

add_library(armada-autohdr SHARED src/armada-autohdr.cpp)
target_compile_features(armada-autohdr PRIVATE cxx_std_20)
target_compile_definitions(armada-autohdr PRIVATE ARMADA_AUTOHDR_BUILDING_LIBRARY)
target_include_directories(armada-autohdr PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:${CMAKE_INSTALL_INCLUDEDIR}>)
set_target_properties(armada-autohdr PROPERTIES
    VERSION ${PROJECT_VERSION}
    SOVERSION 1
    CXX_VISIBILITY_PRESET hidden
    VISIBILITY_INLINES_HIDDEN YES)

if(ARMADA_AUTOHDR_FAST_MATH AND CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(armada-autohdr PRIVATE -ffast-math)
endif()

install(TARGETS armada-autohdr
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR})
install(FILES include/armada-autohdr.h DESTINATION ${CMAKE_INSTALL_INCLUDEDIR})
configure_file(armada-autohdr.pc.in armada-autohdr.pc @ONLY)
install(FILES ${CMAKE_CURRENT_BINARY_DIR}/armada-autohdr.pc
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/pkgconfig)

if(BUILD_TESTING)
    add_executable(core-test tests/core-test.cpp)
    target_compile_features(core-test PRIVATE cxx_std_20)
    target_link_libraries(core-test PRIVATE armada-autohdr)
    add_test(NAME core COMMAND core-test)

    add_executable(api-test tests/api-test.c)
    target_compile_features(api-test PRIVATE c_std_99)
    target_link_libraries(api-test PRIVATE armada-autohdr)
    add_test(NAME c-api COMMAND api-test)
endif()
