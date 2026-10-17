import pytest

from app.domain.errors import DuplicateError, NotFoundError, StorageError
from app.domain.query import LibraryQuery
from app.infrastructure.providers.chain import ProviderChain
from app.services.library_service import LibraryService
from app.services.organization_service import OrganizationService
from app.services.storage_service import StorageManager
from app.services.thumbnail_service import ThumbnailService
from tests.fakes import FakeProvider


@pytest.fixture(params=["sqlite", "json"])
def env(request, settings, tmp_path, qapp):
    storage = StorageManager(settings, tmp_path / "ad")
    storage.configure(tmp_path / "lib", "folder", request.param)
    provider = FakeProvider("f")
    library = LibraryService(storage, ProviderChain([provider]), ThumbnailService(lambda u: b""))
    videos = [library.save_info(FakeProvider("f", title=t).fetch_info(f"vid{i:08d}"))[0] for i, t in enumerate(["Alfa", "Beta", "Gama"])]
    return OrganizationService(library), library, videos


# ---------- categorias ----------
def test_category_crud_validates_and_keeps_videos(env, qtbot):
    org, library, videos = env
    with qtbot.waitSignal(library.changed):
        cat = org.create_category("  Estudos   de   Python ", "descrição", "#8b7cf6")
    assert cat.name == "Estudos de Python" and cat.color == "#8B7CF6"
    org.assign_categories([videos[0].id], add=[cat.id])
    org.update_category(cat.id, "Estudos", "nova", None)
    got = org.get_category(cat.id)
    assert (got.name, got.description, got.color) == ("Estudos", "nova", None)
    org.delete_category(cat.id)
    assert org.categories() == [] and len(library.list_videos()) == 3  # vídeos intactos
    assert org.video_category_ids(videos[0].id) == []


@pytest.mark.parametrize("name,code", [("", "name_empty"), ("   ", "name_empty"), ("x" * 61, "name_too_long")])
def test_invalid_category_names(env, name, code):
    org, *_ = env
    with pytest.raises(StorageError) as exc:
        org.create_category(name)
    assert exc.value.code == code


@pytest.mark.parametrize("color", ["red", "#12345", "#GGGGGG", "8b7cf6", "#1234567"])
def test_invalid_colors_are_rejected(env, color):
    org, *_ = env
    with pytest.raises(StorageError) as exc:
        org.create_category("Ok", color=color)
    assert exc.value.code == "color_invalid"


def test_duplicate_category_names_ignore_case(env):
    org, *_ = env
    org.create_category("Estudos")
    with pytest.raises(DuplicateError):
        org.create_category("estudos")
    other = org.create_category("Música")
    with pytest.raises(DuplicateError):
        org.update_category(other.id, "ESTUDOS")


def test_update_unknown_category(env):
    org, *_ = env
    with pytest.raises(NotFoundError):
        org.update_category(99, "x")


def test_bulk_assign_and_remove_categories(env):
    org, library, videos = env
    a, b = org.create_category("A"), org.create_category("B")
    ids = [v.id for v in videos]
    org.assign_categories(ids, add=[a.id, b.id])
    assert all(set(org.video_category_ids(i)) == {a.id, b.id} for i in ids)
    org.assign_categories(ids[:2], remove=[a.id])
    assert org.video_category_ids(ids[0]) == [b.id] and set(org.video_category_ids(ids[2])) == {a.id, b.id}
    assert org.category_counts() == {a.id: 1, b.id: 3}


def test_assign_is_idempotent_and_does_not_reorder(env):
    org, library, videos = env
    a, b = org.create_category("A"), org.create_category("B")
    org.assign_categories([videos[0].id], add=[b.id, a.id])
    first = org.video_category_ids(videos[0].id)
    org.assign_categories([videos[0].id], add=[a.id])
    assert org.video_category_ids(videos[0].id) == first


# ---------- playlists ----------
def test_playlist_order_add_remove_move(env, qtbot):
    org, library, videos = env
    a, b, c = (v.id for v in videos)
    pl = org.create_playlist("Fila")
    assert org.add_to_playlist(pl.id, [c, a, c, b]) == 3  # repetidos ignorados
    assert org.playlist_video_ids(pl.id) == [c, a, b]
    assert org.add_to_playlist(pl.id, [a]) == 0
    org.move_in_playlist(pl.id, b, 0)
    assert org.playlist_video_ids(pl.id) == [b, c, a]
    org.move_in_playlist(pl.id, b, 99)  # além do fim: vai para o fim
    assert org.playlist_video_ids(pl.id) == [c, a, b]
    org.remove_from_playlist(pl.id, [a])
    assert org.playlist_video_ids(pl.id) == [c, b] and [v.title for v in org.playlist_videos(pl.id)] == ["Gama", "Beta"]
    with pytest.raises(NotFoundError):
        org.move_in_playlist(pl.id, a, 0)


def test_deleting_playlist_or_removing_item_never_touches_videos(env):
    org, library, videos = env
    pl = org.create_playlist("P")
    org.add_to_playlist(pl.id, [v.id for v in videos])
    org.remove_from_playlist(pl.id, [videos[0].id])
    assert len(library.list_videos()) == 3
    org.delete_playlist(pl.id)
    assert org.playlists() == [] and len(library.list_videos()) == 3


def test_playlist_in_multiple_playlists_and_counts(env):
    org, library, videos = env
    p1, p2 = org.create_playlist("P1"), org.create_playlist("P2")
    org.add_to_playlist(p1.id, [videos[0].id, videos[1].id])
    org.add_to_playlist(p2.id, [videos[0].id])
    assert org.playlist_counts() == {p1.id: 2, p2.id: 1}


def test_rename_playlist_validates(env):
    org, *_ = env
    pl = org.create_playlist("Velho")
    assert org.update_playlist(pl.id, " Novo ", "d").name == "Novo"
    with pytest.raises(StorageError):
        org.update_playlist(pl.id, "  ")
    with pytest.raises(NotFoundError):
        org.update_playlist(99, "x")


def test_next_in_playlist_for_sequential_playback(env):
    org, library, videos = env
    a, b, c = (v.id for v in videos)
    pl = org.create_playlist("Seq")
    org.add_to_playlist(pl.id, [b, c, a])
    assert org.next_in_playlist(pl.id, b).id == c and org.next_in_playlist(pl.id, c).id == a
    assert org.next_in_playlist(pl.id, a) is None and org.next_in_playlist(pl.id, 999) is None


def test_removing_a_video_cleans_playlists_and_categories(env):
    org, library, videos = env
    cat, pl = org.create_category("C"), org.create_playlist("P")
    org.assign_categories([videos[0].id], add=[cat.id])
    org.add_to_playlist(pl.id, [v.id for v in videos])
    library.remove(videos[0].id)
    assert org.playlist_video_ids(pl.id) == [videos[1].id, videos[2].id] and org.category_counts() == {}


# ---------- consulta pelo serviço ----------
def test_query_through_service_uses_real_store_data(env):
    org, library, videos = env
    cat = org.create_category("Estudos")
    org.assign_categories([videos[1].id], add=[cat.id])
    pl = org.create_playlist("Fila")
    org.add_to_playlist(pl.id, [videos[2].id, videos[0].id])
    org.store.save_progress(__import__("app.domain.models", fromlist=["Progress"]).Progress(videos[0].id, position=30, duration=100))
    assert [v.title for v in org.query(LibraryQuery(category_ids=frozenset({cat.id})))] == ["Beta"]
    assert [v.title for v in org.query(LibraryQuery(playlist_id=pl.id))] == ["Gama", "Alfa"]
    assert [v.title for v in org.query(LibraryQuery(text="estudos"))] == ["Beta"]
    assert [v.title for v in org.query(LibraryQuery(watch="in_progress"))] == ["Alfa"]
    assert len(org.query(LibraryQuery())) == 3


def test_service_is_inert_without_storage(settings, tmp_path, qapp):
    library = LibraryService(StorageManager(settings, tmp_path / "ad"), ProviderChain([FakeProvider("f")]))
    org = OrganizationService(library)
    assert org.query(LibraryQuery()) == [] and org.categories() == [] and org.playlists() == []
