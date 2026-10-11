from tablatura.t2m import nome_file, somiglianza_impronte


def test_nome_del_file():
    assert nome_file("AC/DC", "Back: in Black") == "AC DC - Back  in Black.t2m"
    assert nome_file("", "") == "Unknown - Untitled.t2m"


def test_la_stessa_registrazione_si_riconosce():
    a = {"duration": 200.0, "chroma2s": ["0123456789" * 3, "9876543210" * 3] + ["5555555555" * 3] * 10}
    b = {"duration": 201.5, "chroma2s": ["0123456789" * 3, "9876543210" * 3] + ["5555555555" * 3] * 10}
    diversa = {"duration": 200.0, "chroma2s": ["9876543210" * 3, "0123456789" * 3] + ["5555555555" * 3] * 10}
    lontana = {"duration": 260.0, "chroma2s": a["chroma2s"]}
    assert somiglianza_impronte(a, b) > 0.99
    assert somiglianza_impronte(a, diversa) < 0.5
    assert somiglianza_impronte(a, lontana) == 0.0
