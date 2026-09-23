"""Kontoauszug-Formate - alle Beispiele erfunden (BLZ 00000000 bzw. Lehrbuch-IBAN)."""

import datetime as dt
import tempfile
import unittest
from pathlib import Path

from verwaltung.bank import FormatFehler, camt, csv_bank, lese_datei


class CsvTest(unittest.TestCase):
    def test_sparkasse_cp1252(self):
        text = ('"Auftragskonto";"Buchungstag";"Valutadatum";"Buchungstext";"Verwendungszweck";"Glaeubiger ID";'
                '"Mandatsreferenz";"Kundenreferenz (End-to-End)";"Sammlerreferenz";"Lastschrift Ursprungsbetrag";'
                '"Auslagenersatz Ruecklastschrift";"Beguenstigter/Zahlungspflichtiger";"Kontonummer/IBAN";'
                '"BIC (SWIFT-Code)";"Betrag";"Waehrung";"Info"\r\n'
                '"DE02000000000000100001";"01.10.26";"01.10.26";"GUTSCHR. UEBERWEISUNG";"Miete Oktober Müller";"";"";'
                '"NOTPROVIDED";"";"";"";"Max Müller";"DE89370400440532013000";"XXX";"1.250,00";"EUR";"Umsatz gebucht"\r\n'
                '"DE02000000000000100001";"02.10.26";"02.10.26";"FOLGELASTSCHRIFT";"Versicherung";"";"";"";"";"";"";'
                '"Muster AG";"DE02000000000000000001";"XXX";"-89,90";"EUR";"Umsatz gebucht"\r\n')
        fmt, umsaetze = csv_bank.lese(text.encode("cp1252"))
        self.assertEqual(fmt, "CSV (Sparkasse)")
        self.assertEqual(len(umsaetze), 2)
        a = umsaetze[0]
        self.assertEqual((a.datum, a.betrag_cent, a.name, a.iban), (dt.date(2026, 10, 1), 125000, "Max Müller",
                                                                    "DE89370400440532013000"))
        self.assertEqual(a.zweck, "Miete Oktober Müller")
        self.assertEqual(umsaetze[1].betrag_cent, -8990)

    def test_volksbank(self):
        text = ("Bezeichnung Auftragskonto;IBAN Auftragskonto;BIC Auftragskonto;Bankname Auftragskonto;Buchungstag;"
                "Valutadatum;Name Zahlungsbeteiligter;IBAN Zahlungsbeteiligter;BIC (SWIFT-Code) Zahlungsbeteiligter;"
                "Buchungstext;Verwendungszweck;Betrag;Waehrung;Saldo nach Buchung;Bemerkung\n"
                "Giro;DE02000000000000100001;X;VR;02.10.2026;02.10.2026;Erika Beispiel;DE89370400440532013000;X;"
                "Gutschrift;Miete WE 3;800,00;EUR;10.000,00;\n")
        fmt, (a,) = csv_bank.lese(text.encode("utf-8"))
        self.assertEqual(fmt, "CSV (Volksbank/Raiffeisen)")
        self.assertEqual((a.name, a.iban, a.konto, a.betrag_cent), ("Erika Beispiel", "DE89370400440532013000",
                                                                   "DE02000000000000100001", 80000))

    def test_ing_mit_vorspann(self):
        text = ("Umsatzanzeige;Datei erstellt am: 05.10.2026\n\nIBAN;DE02 0000 0000 0000 1000 01\nKontoname;Giro\n"
                "Kunde;Max Mustermann\n\n"
                "Buchung;Wertstellungsdatum;Auftraggeber/Empfänger;Buchungstext;Verwendungszweck;Saldo;Währung;Betrag;Währung\n"
                "01.10.2026;01.10.2026;Anna Probe;Gutschrift;Miete 10/2026;5.000,00;EUR;580,00;EUR\n")
        fmt, (a,) = csv_bank.lese(text.encode("utf-8"))
        self.assertEqual(fmt, "CSV (ING)")
        self.assertEqual((a.name, a.zweck, a.betrag_cent, a.iban), ("Anna Probe", "Miete 10/2026", 58000, ""))

    def test_dkb_und_vorgemerkt(self):
        text = ('"Konto";"Girokonto DE02000000000000100001"\n""\n'
                '"Buchungsdatum";"Wertstellung";"Status";"Zahlungspflichtige*r";"Zahlungsempfänger*in";'
                '"Verwendungszweck";"Umsatztyp";"IBAN";"Betrag (€)";"Gläubiger-ID";"Mandatsreferenz";"Kundenreferenz"\n'
                '"01.10.26";"01.10.26";"Gebucht";"Paul Probe";"Vermieter";"Miete";"Eingang";"DE89370400440532013000";'
                '"590";"";"";""\n'
                '"05.10.26";"05.10.26";"Vorgemerkt";"Anna Probe";"Vermieter";"Miete";"Eingang";"";"580";"";"";""\n')
        fmt, umsaetze = csv_bank.lese(text.encode("utf-8"))
        self.assertEqual(fmt, "CSV (DKB)")
        self.assertEqual([(x.name, x.betrag_cent) for x in umsaetze], [("Paul Probe", 59000)])

    def test_deutsche_bank_soll_haben(self):
        text = ("Kontoumsätze Girokonto\nBuchungstag;Wert;Umsatzart;Begünstigter / Auftraggeber;Verwendungszweck;IBAN;"
                "BIC;Kundenreferenz;Mandatsreferenz ;Gläubiger ID;Fremde Gebühren;Betrag;Abweichender Empfänger;"
                "Anzahl der Aufträge;Anzahl der Schecks;Soll;Haben;Währung\n"
                "01.10.2026;01.10.2026;Gutschrift;Otto Vorlage;Garage;DE89370400440532013000;X;;;;;;;;;;60,00;EUR\n"
                "02.10.2026;02.10.2026;Lastschrift;Stadtwerke;Strom;DE02000000000000000001;X;;;;;;;;;-45,00;;EUR\n"
                "Kontostand;;;;;;;;;;;;;;;;;\n")
        fmt, umsaetze = csv_bank.lese(text.encode("utf-8"))
        self.assertEqual(fmt, "CSV (Deutsche Bank)")
        self.assertEqual([x.betrag_cent for x in umsaetze], [6000, -4500])

    def test_unbekanntes_format(self):
        with self.assertRaises(FormatFehler):
            csv_bank.lese(b"Name;Alter\nMax;40\n")


CAMT = b"""<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.053.001.02"><BkToCstmrStmt><Stmt>
<Acct><Id><IBAN>DE02000000000000100001</IBAN></Id></Acct>
<Ntry><Amt Ccy="EUR">650.00</Amt><CdtDbtInd>CRDT</CdtDbtInd><Sts>BOOK</Sts><BookgDt><Dt>2026-10-01</Dt></BookgDt>
 <NtryDtls><TxDtls><RltdPties><Dbtr><Nm>Max Mustermann</Nm></Dbtr><DbtrAcct><Id><IBAN>DE89370400440532013000</IBAN></Id></DbtrAcct>
 </RltdPties><RmtInf><Ustrd>Miete Oktober</Ustrd><Ustrd>WE 1</Ustrd></RmtInf></TxDtls></NtryDtls></Ntry>
<Ntry><Amt Ccy="EUR">1100.00</Amt><CdtDbtInd>CRDT</CdtDbtInd><Sts>BOOK</Sts><BookgDt><Dt>2026-09-29</Dt></BookgDt>
 <NtryDtls>
  <TxDtls><Amt Ccy="EUR">580.00</Amt><RltdPties><Dbtr><Nm>Jobcenter Musterstadt</Nm></Dbtr>
   <UltmtDbtr><Nm>Anna Probe</Nm></UltmtDbtr></RltdPties><RmtInf><Ustrd>KdU 10.2026</Ustrd></RmtInf></TxDtls>
  <TxDtls><Amt Ccy="EUR">520.00</Amt><RltdPties><Dbtr><Nm>Jobcenter Musterstadt</Nm></Dbtr></RltdPties>
   <RmtInf><Ustrd>KdU 10.2026 Mustermann</Ustrd></RmtInf></TxDtls>
 </NtryDtls></Ntry>
<Ntry><Amt Ccy="EUR">20.00</Amt><CdtDbtInd>DBIT</CdtDbtInd><Sts>BOOK</Sts><BookgDt><Dt>2026-10-02</Dt></BookgDt></Ntry>
<Ntry><Amt Ccy="EUR">99.00</Amt><CdtDbtInd>CRDT</CdtDbtInd><Sts>PDNG</Sts><BookgDt><Dt>2026-10-03</Dt></BookgDt></Ntry>
</Stmt></BkToCstmrStmt></Document>"""


class CamtTest(unittest.TestCase):
    def test_camt053(self):
        umsaetze = camt.lese(CAMT)
        self.assertEqual([x.betrag_cent for x in umsaetze], [65000, 58000, 52000, -2000])
        a = umsaetze[0]
        self.assertEqual((a.name, a.iban, a.zweck, a.konto),
                         ("Max Mustermann", "DE89370400440532013000", "Miete Oktober WE 1", "DE02000000000000100001"))
        self.assertIn("für Anna Probe", umsaetze[1].zweck)             # Jobcenter zahlt fuer Mieter

    def test_erkennung_am_inhalt(self):
        with tempfile.TemporaryDirectory() as t:
            pfad = Path(t) / "auszug.txt"
            pfad.write_bytes(CAMT)
            fmt, umsaetze = lese_datei(pfad)
            self.assertEqual(fmt, "CAMT")
            self.assertEqual(len(umsaetze), 4)


if __name__ == "__main__":
    unittest.main()
