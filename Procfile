release: if $SAMPLE_ZIP_URL; then curl -sS $SAMPLE_ZIP_URL > sample_files.zip && unzip sample_files.zip -d sample_files && rm sample_files.zip; fi
web: gunicorn photo_manager.wsgi
