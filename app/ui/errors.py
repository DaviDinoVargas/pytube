def describe_error(translator, code):
    """Mensagem traduzida para um código de erro estável (de provedor, mídia ou armazenamento)."""
    for key in (f"error.provider_{code}", f"error.{code}"):
        text = translator.t(key)
        if text != key:
            return text
    return translator.t("error.unknown")
