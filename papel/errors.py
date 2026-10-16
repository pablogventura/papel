"""Errores de codificacion y de lectura."""


class PapelError(Exception):
    """Fallo al armar o leer un backup en papel."""


class DecodeError(PapelError):
    """La hoja no se pudo leer, o el CRC no cierra."""


class IncompleteBackup(DecodeError):
    """Faltan paginas. No se escribe un archivo a medias."""

    def __init__(self, missing: list[int]):
        self.missing = missing
        pages = ", ".join(str(index + 1) for index in missing)
        super().__init__(f"missing pages: {pages}")
