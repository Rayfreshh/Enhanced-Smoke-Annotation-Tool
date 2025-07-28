python3.13 -m PyInstaller \
    --onefile \
    --hidden-import PIL._tkinter_finder \
    --noconsole \
    --add-data "Smoke_application_image.ico:." \
    --icon=Smoke_application_image.ico \
    --name="Smoke_Annotation_Linux" \
    --distpath=./ \
    Video_segment_editor.py

rm -rf build
rm "Smoke_Annotation_Linux.spec"
