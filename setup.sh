#!/bin/bash

if command -v py >/dev/null 2>&1; then
  PYTHON="py -3"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON="python"
else
  echo "Python is not installed or not executable."
  exit 1
fi

OS_TYPE="$(uname -s)"

# Check if PyInstaller is installed, install if not
if ! $PYTHON -c "import PyInstaller" >/dev/null 2>&1; then
  echo "Installing..."
  $PYTHON -m pip install pyinstaller >/dev/null 2>&1
  if [ $? -ne 0 ]; then
    echo "Installation failed. Please install PyInstaller manually with: $PYTHON -m pip install pyinstaller"
    exit 1
  fi
fi

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

echo "Installing Smoke Annotation Tool...
!!! Don't close this window until the installation is complete. !!!"
$PYTHON -m PyInstaller \
  --name="$NAME" \
  $ICON \
  "${COMMON_ARGS[@]}" >/dev/null 2>&1

if [ $? -eq 0 ]; then
  rm -rf build && rm "${NAME}.spec"
  echo "Build completed successfully. The executable is located in the current directory."
else
  echo "Build failed. Please check your Python environment and dependencies."
  exit 1
fi
exit 0
# End of setup.sh
