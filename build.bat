@echo off
cd app

pyinstaller jirator.py --onefile --specpath ..\build --distpath ..\build --workpath ..\work --clean -y -n jirator


rem ----------------------------------------------------------------------------
rem Update build meta info

python ..\build_helper.py -j jirator.json
copy jirator.json ..\build


rem ----------------------------------------------------------------------------
rem Clean build directory

rmdir ..\build\jirator /S /Q
del ..\build\jirator.spec
del ..\build\exports\*.csv
del ..\build\logs\*.log


rem ----------------------------------------------------------------------------
rem Copy assets and app files

copy config.json ..\build
copy auth.pickle ..\build
copy jira_user_cache.pickle ..\build
copy rm_user_cache.pickle ..\build
Xcopy /E /I /Y assets ..\build\assets


rem ----------------------------------------------------------------------------
rem Create release archive

python ..\build_helper.py -z jirator.json
