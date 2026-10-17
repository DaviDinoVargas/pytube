from app.domain.queue import PlayQueue


def test_add_keeps_order_and_ignores_duplicates():
    q = PlayQueue()
    q.add([1, 2, 2, 3])
    q.add([2])  # já estava: vai para o fim
    assert q.ids == [1, 3, 2] and len(q) == 3 and 3 in q and 9 not in q


def test_play_next_inserts_after_the_current_one():
    q = PlayQueue([1, 2, 3], current=1)
    q.add([9, 8], play_next=True)
    assert q.ids == [1, 9, 8, 2, 3]
    q.add([3], play_next=True)
    assert q.ids == [1, 3, 9, 8, 2]


def test_adding_the_current_video_again_does_nothing():
    q = PlayQueue([1, 2], current=1)
    q.add([1])
    assert q.ids == [1, 2] and q.current == 1


def test_next_and_previous_follow_the_order():
    q = PlayQueue([1, 2, 3], current=2)
    assert q.next_id() == 3 and q.previous_id() == 1
    assert q.next_id(3) is None and q.previous_id(1) is None
    q.set_current(3)
    assert q.next_id() is None


def test_next_without_current_starts_the_queue():
    q = PlayQueue([5, 6])
    assert q.current is None and q.next_id() == 5
    assert PlayQueue().next_id() is None


def test_video_outside_the_queue_has_no_next():
    q = PlayQueue([1, 2], current=1)
    assert q.next_id(77) is None and q.previous_id(77) is None


def test_remove_current_clears_it_and_remove_unknown_is_a_noop():
    q = PlayQueue([1, 2, 3], current=2)
    q.remove(2)
    assert q.ids == [1, 3] and q.current is None
    q.remove(99)
    assert q.ids == [1, 3]


def test_move_and_set_order():
    q = PlayQueue([1, 2, 3, 4])
    q.move(4, 0)
    assert q.ids == [4, 1, 2, 3]
    q.move(4, 99)
    assert q.ids == [1, 2, 3, 4]
    q.set_order([3, 1, 99])
    assert q.ids == [3, 1, 2, 4]


def test_set_current_only_accepts_queued_videos_and_clear_resets():
    q = PlayQueue([1, 2])
    q.set_current(2)
    assert q.current == 2
    q.set_current(7)
    assert q.current is None
    q.set_current(1)
    q.clear()
    assert q.ids == [] and q.current is None


def test_prune_removes_deleted_videos():
    q = PlayQueue([1, 2, 3], current=2)
    q.prune([1, 3])
    assert q.ids == [1, 3] and q.current is None


def test_constructor_dedupes_and_ignores_a_current_outside_the_list():
    q = PlayQueue([1, 1, 2], current=5)
    assert q.ids == [1, 2] and q.current is None
