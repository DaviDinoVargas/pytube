from app.infrastructure.providers import quality
from app.infrastructure.providers.base import TERMINAL_CODES, DownloadCancelled, ProviderError

DEFAULT_ORDER = ("pytubefix", "ytdlp")


class ProviderChain:
    """Tenta os provedores na ordem configurada. Se um quebrar (o YouTube muda), o próximo assume."""

    def __init__(self, providers, order=DEFAULT_ORDER):
        self._providers = {p.name: p for p in providers}
        self.order = order

    @property
    def order(self):
        return tuple(self._order)

    @order.setter
    def order(self, names):
        known = [n for n in names if n in self._providers]
        known += [n for n in self._providers if n not in known]  # os não listados vão ao final
        self._order = known

    def available(self):
        return [self._providers[n] for n in self._order if self._providers[n].is_available()]

    def names(self):
        return list(self._providers)

    def fetch_info(self, video_id):
        errors = []
        for provider in self.available():
            try:
                return provider.fetch_info(video_id)
            except ProviderError as exc:
                errors.append(exc)
                if exc.code in TERMINAL_CODES:
                    raise
        if not errors:
            raise ProviderError("not_installed", "nenhum provedor instalado")
        raise self._most_specific(errors)

    def download(self, info, stream, dest, on_progress, cancel_event):
        """Baixa pelo provedor que gerou `info`; se ele falhar, tenta o stream equivalente nos outros."""
        by_name = self._providers
        first = by_name.get(info.provider)
        errors = []
        if first is not None:
            try:
                first.download_stream(info.source_id, stream, dest, on_progress, cancel_event)
                return first.name
            except DownloadCancelled:
                raise
            except ProviderError as exc:
                errors.append(exc)
                if exc.code in TERMINAL_CODES:
                    raise
        for provider in self.available():
            if provider.name == info.provider:
                continue
            try:
                other = provider.fetch_info(info.source_id)
                match = quality.equivalent(stream, other.streams)
                if match is None:
                    errors.append(ProviderError("unsupported", f"{provider.name}: sem {stream.label or stream.kind}"))
                    continue
                provider.download_stream(info.source_id, match, dest, on_progress, cancel_event)
                return provider.name
            except DownloadCancelled:
                raise
            except ProviderError as exc:
                errors.append(exc)
                if exc.code in TERMINAL_CODES:
                    raise
        raise self._most_specific(errors) if errors else ProviderError("not_installed")

    @staticmethod
    def _most_specific(errors):
        """Prefere um erro com causa conhecida a um genérico ('failed' / 'network')."""
        for generic in (("failed",), ("network",)):
            specific = [e for e in errors if e.code not in generic and e.code != "not_installed"]
            if specific:
                return specific[0]
        return errors[0]
