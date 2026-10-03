import pytest

from fakturnik import mf

ODPOWIEDZ = {"result": {"subject": {
    "name": "FIRMA MEDICA SPÓŁKA Z OGRANICZONĄ ODPOWIEDZIALNOŚCIĄ", "nip": "1234563218", "statusVat": "Czynny",
    "regon": "123456785", "pesel": None, "krs": "0000123456", "residenceAddress": None,
    "workingAddress": "UL. DŁUGA 1/2, 00-001 WARSZAWA", "accountNumbers": ["61109010140000071219812874"]},
    "requestId": "abc", "requestDateTime": "03-10-2026 12:00:00"}}


def test_dane_firmy_z_odpowiedzi():
    f = mf.z_odpowiedzi(ODPOWIEDZ)
    assert (f.nip, f.status_vat, f.regon) == ("1234563218", "Czynny", "123456785")
    assert f.konta == ["61109010140000071219812874"]
    assert mf.adres_dwulinijkowy(f.adres) == "ul. Długa 1/2, 00-001 Warszawa"
    assert mf.z_odpowiedzi({"result": {"subject": None}}) is None
    with pytest.raises(mf.BladMF):
        mf.z_odpowiedzi({"code": "WL-113", "message": "Pole 'NIP' ma nieprawidłową długość."})


def test_zly_nip_nie_idzie_do_internetu():
    with pytest.raises(mf.BladMF):
        mf.szukaj("123-456-32-19")
