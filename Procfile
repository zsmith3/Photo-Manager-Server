release: if ! test -z "$SAMPLE_ZIP_URL"; then curl -LsS "$SAMPLE_ZIP_URL" > sample_files.zip && ls && cat sample_files.zip && unzip sample_files.zip -d sample_files && rm sample_files.zip; fi
web: gunicorn photo_manager.wsgi
