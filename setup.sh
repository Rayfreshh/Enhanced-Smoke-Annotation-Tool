#!/bin/bash

# Detect OS
OS_TYPE="$(uname -s)"

if [[ "$OS_TYPE" == "Linux" ]]; then
  python3.13 -m PyInstaller \
    --onefile \
    --hidden-import PIL._tkinter_finder \
    --noconsole \
    --name="Smoke_Annotation_Linux" \
    --distpath=./ \
    Video_segment_editor.py

  rm -rf build
  rm "Smoke_Annotation_Linux.spec"

elif [[ "$OS_TYPE" == MINGW* || "$OS_TYPE" == MSYS* || "$OS_TYPE" == CYGWIN* ]]; then
  python3.13 -m PyInstaller \
    --onefile \
    --hidden-import PIL._tkinter_finder \
    --noconsole \
    --icon=Smoke_application_image.ico \
    --name="Smoke Annotation (windows)" \
    --distpath=./ \
    Video_segment_editor.py

  rm -rf build
  rm "Smoke Annotation (windows).spec"

else
  echo "Unsupported OS: $OS_TYPE"
  exit 1
fi
