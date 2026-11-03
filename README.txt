CORPUS VIANOVA - 4 FUENTES OFICIALES

Este paquete contiene un descargador y metadatos para 4 fuentes oficiales:
1. NCI - Consejos de alimentación (actualizado 2024)
2. NCI - La radioterapia y usted (actualizado 2016)
3. INEN - Paciente oncológico inmunodeprimido (2020)
4. INEN - Administración de agentes antineoplásicos (2023, V1)

USO RECOMENDADO DESDE LA RAÍZ DE rag-engine:

python /ruta/al/zip/descomprimido/descargar_corpus.py corpus/aprobados

El script descargará cada PDF desde su URL oficial y creará un JSON al lado con:
- titulo
- entidad
- version
- url_origen
- vigencia = por revisar

Luego inspecciona cada PDF antes de indexarlo:
python scripts/inspect_pdf.py corpus/aprobados/<archivo>.pdf --chunks

No se marca ninguna fuente como clínicamente vigente; queda "por revisar" hasta curaduría.
