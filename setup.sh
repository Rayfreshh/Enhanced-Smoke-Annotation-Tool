#!/bin/bash

OS_TYPE="$(uname -s)"

COMMON_ARGS=(
  --onefile
  --hidden-import PIL._tkinter_finder
  --noconsole
  --distpath=./
  Video_segment_editor.py
)

if [[ "$OS_TYPE" == "Linux" ]]; then
  NAME="Smoke Annotation (Linux)"
  ICON=""
elif [[ "$OS_TYPE" == MINGW* || "$OS_TYPE" == MSYS* || "$OS_TYPE" == CYGWIN* ]]; then
  NAME="Smoke Annotation (Windows)"
  ICON="--icon=Smoke_application_image.png"
else
  echo "Unsupported OS: $OS_TYPE"
  exit 1
fi

py -m PyInstaller \
  --name="$NAME" \
  $ICON \
  "${COMMON_ARGS[@]}"

rm -rf build
rm "${NAME}.spec"