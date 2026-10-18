from app.domain.notes import parse_markers


def test_minutes_seconds_and_hours():
    marks = parse_markers("[0:05] início\n[12:34] índices\n[1:02:03] fim")
    assert [(m.seconds, m.label) for m in marks] == [(5, "início"), (754, "índices"), (3723, "fim")]


def test_label_is_the_rest_of_the_line_and_can_come_before_the_mark():
    marks = parse_markers("rever isto [3:10] - ótimo trecho")
    assert marks[0].seconds == 190 and "rever isto" in marks[0].label and "ótimo trecho" in marks[0].label


def test_invalid_marks_are_ignored():
    assert parse_markers("[99:99] [1:75] [abc] [12:3] texto") == []


def test_several_marks_on_one_line_and_empty_text():
    assert [m.seconds for m in parse_markers("[0:10] e [0:20] juntos")] == [10, 20]
    assert parse_markers("") == [] and parse_markers(None) == []


def test_long_labels_are_cut():
    assert len(parse_markers("[0:01] " + "x" * 500)[0].label) == 80
