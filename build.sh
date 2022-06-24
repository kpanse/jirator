cd app/

pyinstaller jirator.py --onefile --specpath ../build --distpath ../build --workpath ../work --clean -y -n jirator


# ----------------------------------------------------------------------------
# Update build meta info

python3 ../build_helper.py -j jirator.json
cp jirator.json ../build


# ----------------------------------------------------------------------------
# Clean build directory

rm -r ../build/jirator
rm ../build/jirator.spec
rm ../build/exports/*
rm ../build/logs/*


# ----------------------------------------------------------------------------
# Copy assets and app files
cp config.json ../build
cp auth.pickle ../build
cp jira_user_cache.pickle ../build
cp rm_user_cache.pickle ../build
cp -r assets ../build/assets


# ----------------------------------------------------------------------------
# Create release archive

python3 ../build_helper.py -z jirator.json
