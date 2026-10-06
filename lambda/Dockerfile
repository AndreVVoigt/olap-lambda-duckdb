# Imagem oficial da AWS para Lambda em Python: já traz o runtime e o emulador
FROM public.ecr.aws/lambda/python:3.13

# A Lambda só permite escrita em /tmp
ENV HOME=/tmp
ENV DUCKDB_EXTENSION_DIR=/opt/duckdb_extensions

# Dependências primeiro: o Docker reaproveita esta camada se só o handler mudar
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Extensões de S3 instaladas no build, não no cold start
RUN python -c "import duckdb; c = duckdb.connect(config={'extension_directory': '/opt/duckdb_extensions'}); c.install_extension('httpfs'); c.install_extension('aws')"

COPY handler.py ${LAMBDA_TASK_ROOT}/

# Formato: arquivo.função
CMD ["handler.lambda_handler"]