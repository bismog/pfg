
# git clone repository

# install pyinstaller
pip install pyinstaller

# build, this will create `dist/pfg`
pyinstaller --onefile --add-data "FlameGraph:FlameGraph" pfg.py

# capture and output access url
./dist/pfg {pid}

# access via browser

