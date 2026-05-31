from app.services.docking import classify_contact, parse_vina_modes


def test_parse_vina_modes() -> None:
    log = """
-----+------------+----------+----------
mode | affinity   | dist from best mode
     | (kcal/mol) | rmsd l.b.| rmsd u.b.
   1       -8.7      0.000      0.000
   2       -7.9      1.312      2.108
"""
    modes = parse_vina_modes(log)
    assert modes[0]["mode"] == 1
    assert modes[0]["affinity_kcal_mol"] == -8.7
    assert modes[1]["rmsd_ub"] == 2.108

