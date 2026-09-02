cmake_minimum_required(VERSION 3.20)
project(wallpha-plasma VERSION 2.1.0)

# wallpha-plasma — backend Plasma do wallpha (wallpha = wallpaper) — plasmóide unificado imagem+vídeo, leve, sem painel
# Instala via: cmake -B build && cmake --install build --prefix ~/.local
# ou: kpackagetool6 -t Plasma/Wallpaper --install .

find_package(ECM 6.0.0 QUIET NO_MODULE)
if(ECM_FOUND)
    set(CMAKE_MODULE_PATH ${ECM_MODULE_PATH})
    include(KDEInstallDirs)
    include(KDECMakeSettings)
    include(KDECompilerSettings NO_POLICY_SCOPE)
    find_package(Qt6 QUIET COMPONENTS Quick Multimedia)
    find_package(KF6 QUIET COMPONENTS Plasma)
else()
    include(GNUInstallDirs)
    if(NOT KDE_INSTALL_PLASMAWALLPAPERDIR)
        set(KDE_INSTALL_PLASMAWALLPAPERDIR "${CMAKE_INSTALL_DATAROOTDIR}/plasma/wallpapers")
    endif()
endif()

# Plasmóide QML puro (KPackage) — sem C++. Só instala metadata + contents.
# Funciona com ECM presente ou não (fallback GNUInstallDirs).
install(FILES metadata.json DESTINATION ${KDE_INSTALL_PLASMAWALLPAPERDIR}/com.wallpha.wallpaper)
install(DIRECTORY contents/ DESTINATION ${KDE_INSTALL_PLASMAWALLPAPERDIR}/com.wallpha.wallpaper/contents)
