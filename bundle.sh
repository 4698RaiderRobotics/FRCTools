#!/bin/bash

build_path="./build"
program_basename="FRCTools"
version=`gawk '/version/ {gsub(/\042|,/, ""); print $2 }' ./FRCTools.manifest`

echo "Extracted version is $version"

"C:/Program Files/7-Zip/7z.exe" d $build_path/$program_basename.zip *

"C:/Program Files/7-Zip/7z.exe" a $build_path/$program_basename.zip \
    *.py *.manifest -ir!lib/* -ir!commands/* -ir!generators/* -xr!__pycache__

"C:/Program Files (x86)/NSIS/makensis.exe" -V4 ./win_install.nsi

echo
echo
echo "Moving $build_path/$program_basename.zip to $build_path/$program_basename-$version.zip"
mv $build_path/$program_basename.zip $build_path/$program_basename-$version.zip
echo "Moving $build_path/$program_basename-win.exe to $build_path/$program_basename-win-$version.exe"
mv $build_path/$program_basename-win.exe $build_path/$program_basename-win-$version.exe

echo
echo "Done."