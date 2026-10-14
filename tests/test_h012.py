from pmq import h012


def test_salto_detectado_y_causal():
    h = [{"t": 0, "p": 0.40}, {"t": 3600, "p": 0.52}, {"t": 7200, "p": 0.30}]
    assert h012.first_jump(h, 10 ** 6) == (3600, 1, 0.52)


def test_sin_salto_por_extremo_o_cercania():
    assert h012.first_jump([{"t": 0, "p": 0.85}, {"t": 3600, "p": 0.97}], 10 ** 6) is None
    assert h012.first_jump([{"t": 0, "p": 0.40}, {"t": 3600, "p": 0.55}], 3600 + 100) is None
    assert h012.first_jump([{"t": 0, "p": 0.40}, {"t": 4 * 3600, "p": 0.55}], 10 ** 6) is None
