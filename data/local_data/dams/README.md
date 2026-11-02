# Dams

Extracted from local decoded OpenInfraMap/PostGIS layers.

Filters: `waterway=dam`, `man_made=dam`, or `building=dam`.

Feature count: 704

Representação de origem para revisão/versionamento: `dams.geojson`.

Formato distribuído ao runtime (um `Feature` JSON por linha):
`dams.geojsonl`. Ambos são mantidos **intencionalmente**: um facilita
inspeção da coleção e o outro leitura incremental. Não apague um deles
sem verificar consumidores e licenciamento.

O teste automatizado `tests/test_dams_formats.py` valida os 704 elementos
e compara cada geometria/propriedade dos dois formatos. Ao atualizar a
origem, regenere o JSONL e rode esse teste antes de publicar.

License: Open Database License (ODbL) 1.0. Keep the OpenStreetMap contributor
attribution and the Open Infrastructure Map source credit when redistributing
this derived database.

The public-release snapshot removes contact-oriented fields and note values
that contain email or phone identifiers. The runtime layer does not display or
depend on those fields. Both `dams.geojson` and the runtime JSONL form carry the
same privacy transform.
