#!/bin/bash

build_path="./build"
program_basename="FRCTools"
zip_exe="/mnt/c/Program Files/7-Zip/7z.exe"
makensis="/mnt/c/Program Files (x86)/NSIS/makensis.exe"
version=`gawk '/version/ {gsub(/\042|,|\r/, ""); print $2 }' ./FRCTools.manifest`

echo "Extracted version is '${version}'"

"$zip_exe" d $build_path/$program_basename.zip *

"$zip_exe" a $build_path/$program_basename.zip \
    *.py *.manifest -ir!lib/* -ir!commands/* -ir!generators/* -xr!__pycache__

"$makensis" -V4 ./win_install.nsi

echo
echo
echo "Moving $build_path/$program_basename.zip to $build_path/$program_basename-$version.zip"
mv $build_path/$program_basename.zip $build_path/$program_basename-$version.zip
echo "Moving $build_path/$program_basename-win.exe to $build_path/$program_basename-win-$version.exe"
mv $build_path/$program_basename-win.exe $build_path/$program_basename-win-$version.exe

echo
echo "Done."