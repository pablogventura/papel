# Papel

Guarda un archivo en una hoja A4 para imprimir y lo recupera desde un escaneo.

El PDF no es el backup. Es la página que va a la impresora. Después se escanea en gris (o en color, si se usó ese modo) a 300 dpi y `decode` reconstruye el archivo. El orden de las hojas no importa. Si falta una, no escribe un archivo a medias.

## Uso

```bash
python -m venv .venv
.venv/bin/pip install -e ".[test]"
.venv/bin/papel encode ARCHIVO -o backup.pdf
.venv/bin/papel decode escaneo.png otro.png -o ARCHIVO
```

`decode` también acepta el PDF, para probar sin impresora: lo rasteriza a 300 dpi.

Modos:

- `bw` (el que usa por defecto). Negro sobre blanco. Es el que imprime una láser.
- `cmy`. Una capa binaria por tinta (cian, magenta, amarillo). En la medición con ruido de papel mete unas tres veces más bytes.

```bash
.venv/bin/papel encode ARCHIVO -o backup.pdf --mode cmy
```

El punto por defecto mide 0,45 mm. A 300 dpi son unos 5 píxeles por punto, por encima del límite de un muestreo por punto. En esa densidad una hoja en blanco y negro lleva unos 25 KB y una en CMY unos 77 KB, después de la corrección de errores. Con 0,40 mm el mismo ruido ya no alcanza.

## Pruebas

```bash
.venv/bin/pytest
```

El banco rasteriza el PDF y le aplica desenfoque, ruido, rotación, desplazamiento y una mancha. En color, además, un desregistro de 0,1 mm entre tintas. Un daño más grande tiene que fallar sin devolver datos incorrectos.
