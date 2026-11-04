from pipeline.text import canonical_url, clean_html, first_image_in_html, is_http_url, looks_like_f1


def test_canonical_url_strips_tracking_and_fragment():
    url = "HTTP://Example.com/a?utm_source=rss&id=1&at_medium=x#frag"
    assert canonical_url(url) == "https://example.com/a?id=1"


def test_is_http_url_rejects_dangerous_schemes():
    assert is_http_url("https://x.com/a")
    assert not is_http_url("javascript:alert(1)")
    assert not is_http_url(None)


def test_clean_html_removes_tags_and_truncates():
    assert clean_html("<p>Olá &amp; <b>mundo</b></p>") == "Olá & mundo"
    out = clean_html("palavra " * 100, max_len=30)
    assert out.endswith("…") and len(out) <= 31


def test_first_image_in_html():
    assert first_image_in_html('<img src="https://a.com/i.png">') == "https://a.com/i.png"
    assert first_image_in_html('<img src="data:image/png;base64,xx">') is None


def test_looks_like_f1_pt_and_en():
    assert looks_like_f1("Hamilton no GP de Mônaco")
    assert looks_like_f1("Formula 1 testing")
    assert looks_like_f1(None, "Fórmula 1")
    assert not looks_like_f1("MotoGP em Valência", "Bagnaia venceu")
