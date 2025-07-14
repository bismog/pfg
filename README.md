
## git clone repository

## install pyinstaller
```bash
pip install pyinstaller
```

## build, this will create `dist/pfg`
```bash
pyinstaller --onefile --add-data "FlameGraph:FlameGraph" pfg.py
```

## install dependent packages
```bash
dnf install perf perl-open
```

## capture and output access url
```bash
./dist/pfg {pid}
```

## access via browser

