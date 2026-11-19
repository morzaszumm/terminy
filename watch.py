#!/usr/bin/env python3
"""Pilnuje terminów: DCG Powstańców, Ginekologia i położnictwo, NFZ,
Konsultacja Położnicza – Kolejna NFZ, lek. Buganiuk Michał.

Portal zwraca listę lekarzy z polem "CzyMaTermin". Gdy u dr. Buganiuka zmieni się na true,
wysyłamy push (ntfy.sh). Jedno uruchomienie = jedno sprawdzenie (odpalaj co 15 min z crona / Harmonogramu zadań).
Tylko biblioteka standardowa Pythona 3.8+.
"""
import json, os, re, sys, time, uuid, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = {
    "ntfy_topic": os.environ.get("NTFY_TOPIC", "ZMIEN-NA-SWOJ-DLUGI-LOSOWY-TEMAT"),
    "user_ref": "mbuganiuk",          # lekarz: Buganiuk Michał
    "venue_id": "1",                  # 1 = DCG Powstańców, 43 = DCG Krynicka
    "service_id": "52558",            # Konsultacja Położnicza – Kolejna NFZ
    "renotify_min": 30,               # ile minut przerwy między kolejnymi alarmami, gdy termin nadal jest
}
API = "https://portal-doctor.eleks.com/api/runanonymous"
LINK = ("https://portal-doctor.eleks.com/web/dcg/#/?action=spzIBWebAnonymousPatientStep0"
        f"&id={CFG['venue_id']}&idName=VenueId")
STATE = os.path.join(HERE, "state.json")
# Publiczne ID instalacji portalu DCG (to samo dla każdego anonimowego odwiedzającego; losowe ID jest odrzucane)
INSTALLATION_ID = "920746A2-8EF2-4A09-BFF7-EC1CF151B2F9"


def has_slot():
    payload = {
        "name": "spzIBWebAnonymousPatientStep2",
        "params": [
            {"value": CFG["venue_id"], "name": "VenueID"},
            {"value": CFG["service_id"], "name": "ServiceID"},
            {"value": "NFZ", "name": "ScheduleKind"},
            {"value": "NFZ", "name": "ScheduleServiceKind"},
            {"value": "GIN", "name": "SpecialityRef"},
        ],
        "installationId": INSTALLATION_ID,
    }
    req = urllib.request.Request(API, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))
    body = data["markupPatientContact2ContainerSetting"][0]["body"]
    m = re.search(r'"UserRef":"%s"[^}]*?"CzyMaTermin":(true|false)' % re.escape(CFG["user_ref"]), body)
    if not m:
        raise RuntimeError("Nie znaleziono lekarza na liście (zmiana w portalu?)")
    return m.group(1) == "true"


def notify(title, msg, urgent=True):
    headers = {"Title": title.encode("utf-8"), "Click": LINK}
    if urgent:
        headers.update({"Priority": "urgent", "Tags": "rotating_light"})
    urllib.request.urlopen(urllib.request.Request(
        f"https://ntfy.sh/{CFG['ntfy_topic']}", data=msg.encode("utf-8"), headers=headers), timeout=15)


def load():
    try:
        return json.load(open(STATE))
    except Exception:
        return {}


def main():
    st = load()
    now = time.time()
    try:
        slot = has_slot()
    except Exception as e:
        print("BŁĄD:", e, file=sys.stderr)
        if now - st.get("last_error_notify", 0) > 86400:   # o awarii dajemy znać max raz na dobę
            notify("Watcher terminów: błąd", str(e)[:300], urgent=False)
            st["last_error_notify"] = now
            json.dump(st, open(STATE, "w"))
        return
    if slot and now - st.get("last_alert", 0) > CFG["renotify_min"] * 60:
        notify("JEST TERMIN: lek. Buganiuk!", "Pojawił się termin (DCG Powstańców, położnicza NFZ). Rezerwuj od razu!")
        st["last_alert"] = now
    if not slot:
        st["last_alert"] = 0
    st["last_check"], st["has_slot"] = now, slot
    json.dump(st, open(STATE, "w"))
    print(time.strftime("%Y-%m-%d %H:%M"), "termin:", "TAK" if slot else "nie")


if __name__ == "__main__":
    main()
