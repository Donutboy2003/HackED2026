# Generated Cmake Pico project file

cmake_minimum_required(VERSION 3.13)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# Initialise pico_sdk from installed location
# (note this can come from environment, CMake cache etc)

# == DO NOT EDIT THE FOLLOWING LINES for the Raspberry Pi Pico VS Code Extension to work ==
if(WIN32)
    set(USERHOME $ENV{USERPROFILE})
else()
    set(USERHOME $ENV{HOME})
endif()
set(sdkVersion 2.2.0)
set(toolchainVersion 14_2_Rel1)
set(picotoolVersion 2.2.0-a4)
set(picoVscode ${USERHOME}/.pico-sdk/cmake/pico-vscode.cmake)
if (EXISTS ${picoVscode})
    include(${picoVscode})
endif()
# ====================================================================================
set(PICO_BOARD pico CACHE STRING "Board type")

# Pull in Raspberry Pi Pico SDK (must be before project)
include(pico_sdk_import.cmake)

project(text-controller-mvp C CXX ASM)

# Initialise the Raspberry Pi Pico SDK
pico_sdk_init()

# Add executable. 
# We include main.cpp AND our new adxl343.cpp driver implementation
add_executable(text-controller-mvp 
    src/sensor/main.cpp 
    src/sensor/adxl343.cpp
)

pico_set_program_name(text-controller-mvp "text-controller-mvp")
pico_set_program_version(text-controller-mvp "0.1")

# IMPORTANT: Enable USB output so you can see the text UI on your computer
pico_enable_stdio_uart(text-controller-mvp 1)
pico_enable_stdio_usb(text-controller-mvp 0)

# Add the standard library AND hardware_i2c to the build
target_link_libraries(text-controller-mvp
        pico_stdlib
        hardware_i2c
        hardware_adc
)

# Add the standard include files to the build
target_include_directories(text-controller-mvp PRIVATE
        ${CMAKE_CURRENT_LIST_DIR}
        src  # Allow including headers from src/ folder easily
        sensor
)

pico_add_extra_outputs(text-controller-mvp)
