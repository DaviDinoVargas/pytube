class StorageError(Exception):
    """Falha de armazenamento. `code` é uma chave estável que a interface traduz."""

    def __init__(self, code, detail=""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


class DuplicateError(StorageError):
    def __init__(self, detail=""):
        super().__init__("duplicate", detail)


class NotFoundError(StorageError):
    def __init__(self, detail=""):
        super().__init__("not_found", detail)
