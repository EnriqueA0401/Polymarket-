from pmq import h033


def test_pair_por_nombre():
    pres = [{"question": "Will JD Vance win the 2028 US Presidential Election?"},
            {"question": "Will Gavin Newsom win the 2028 US Presidential Election?"}]
    noms = [{"question": "Will JD Vance win the 2028 Republican presidential nomination?"},
            {"question": "Will Someone Else win the 2028 Democratic presidential nomination?"}]
    r = h033.pair(pres, noms)
    assert [x[0] for x in r] == ["JD Vance"]
