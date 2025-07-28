python3.13 -m PyInstaller ^
  --onefile ^
  --hidden-import PIL._tkinter_finder ^
  --noconsole ^
  --icon=Smoke_application_image.ico ^
  --name="Smoke Annotation (windows)" ^
  --distpath=./ ^
  Video_segment_editor.py

rm -rf build
rm "Smoke Annotation (windows).spec"