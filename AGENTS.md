# Agentes

Guía mínima. El uso para personas está en `README.md`.

## Stack

- Python `>=3.11`. Paquete `papel`.
- Dependencias: `numpy`, `pillow`, `pymupdf`, `reedsolo`.
- Tests: `pytest` (extra `test`).
- Importar `pymupdf`, no `fitz`.
- Lint, typecheck, build, migrate, Makefile y CI: no detectado.

## Comandos

```bash
python -m venv .venv
.venv/bin/pip install -e ".[test]"
.venv/bin/papel encode ARCHIVO -o backup.pdf
.venv/bin/papel decode escaneo.png -o ARCHIVO
.venv/bin/pytest
.venv/bin/pytest tests/test_codec.py -q
```

Correr pytest desde la raíz del repo, con el intérprete del venv. No hay servidor de desarrollo.

## Estructura

- `papel/`: CLI, trama, PDF, localización de la grilla y ruido de prueba.
- `tests/`: pytest. Rasterizan el PDF a 300 dpi y le aplican ruido.
- `ejemplo.pdf`: muestra para mirar. No es código.
- `upstream.html`: página original de PaperBack. No es código.

Módulos de `papel/`: `cli`, `document` (encode/decode de archivo), `codec` (cabecera, zlib, CRC, Reed-Solomon), `grid`, `paint`, `render`, `locate`, `decode_page`, `noise`, `constants`, `errors`.

## Convenciones

- Nombres de código, errores y logs en inglés. Comentarios y documentación en español.
- El backup es la hoja impresa. El PDF es lo que se manda a la impresora. `decode` lee PNG, JPEG, TIFF o un PDF rasterizado.
- Formato propio, no compatible con los bitmaps de PaperBack 1.10.
- Modo por defecto `bw`. Color opcional `cmy` (`--mode cmy`). Esos dos son los que ofrece el CLI.
- Punto por defecto `0.45` mm (`DEFAULT_MODULE_MM`). Por debajo de 3 px a 300 dpi no se genera grilla (`MIN_MODULE_MM`).
- `0.40` mm no se recupera con el perfil `HARSH`. `0.48` mm tampoco, aunque `0.45` y `0.50` sí: la fase no es monótona.
- Varias hojas: el orden de los escaneos no importa. Si falta una, `IncompleteBackup` y no se escribe un archivo a medias.
- Los bytes de cada símbolo Reed-Solomon viajan juntos y los grupos se esparcen por la hoja. Una mancha no debe caer siempre en los mismos bloques.

## Tests

- `tests/test_codec.py`: cabecera, esparcido y Reed-Solomon, sin imagen.
- `tests/test_roundtrip.py`: PDF limpio, grilla sin PDF, ruido `MILD` / `HARSH` / `FATAL`, CLI.
- `tests/test_color.py`: con `HARSH`, `cmy` recupera y guarda al menos 1,5 veces lo de `bw`.
- `tests/test_density.py`: el módulo por defecto está sobre el piso de Nyquist y una hoja `bw` se lee.
- `tests/test_multipage.py`: hojas fuera de orden, y una hoja faltante no devuelve un archivo parcial.
- Un daño más grande que `HARSH` (`FATAL`) tiene que fallar. No aflojar `FATAL` para que un test pase.
- Un test de imagen es lento: rasteriza A4 a 300 dpi. No lanzar varios pytest en paralelo.

## Qué no hacer

- No cambiar `DEFAULT_MODULE_MM`, `LASER_MODE` ni `COLOR_MODE` sin volver a medir `HARSH` y ajustar el comentario de `papel/constants.py` y el README.
- No bajar de `MIN_MODULE_MM`. No asumir que un punto más grande siempre se lee mejor.
- No tratar el PDF como el medio de backup.
- No commitear `.venv/`, `__pycache__/` ni `ejemplo.pdf` salvo que se pida.
