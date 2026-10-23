r"""
Tier 1 tests for FanzinesEditor: run after every change. About a minute, no network, nothing outside a temporary folder.

    venv12\Scripts\python.exe tests\tier1.py

Runs against a fake FTP server in memory (fakeftp.py), seeded with real fanzine index pages (tests/fixtures) and a
Classic list written by FE itself. Results: tests/results/tier1.txt. Exit code 0 if everything passed.
"""
from __future__ import annotations

import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness
from harness import Dialogs, MakePdf, PdfFacts

harness.Setup(1)

import wx
import wx.grid
import fakeftp
import FanzineIndexPageEdit as FIP
import FanzinesEditor as FE
from ClassicFanzinesLine import ClassicFanzinesLine, ClassicFanzinesDate
from DeltaTracker import DeltaTracker
from FanzineIndexPageTableRow import FanzineIndexPageTableRow
from FanzineNames import FanzineNames
from Settings import Settings
from WxDataGrid import ColDefinitionsList, ColDefinition

R=harness.Results("tier1")
TMP=harness.TMP
T=harness.TEST_ROOT
FIXTURE_DIRS={"Apollo": "Apollo", "Innuendo": "Innuendo", "Australian_SF_News": "Australian SF News"}


# ======================================================================================================================
# A fresh fake server, seeded with the fixture pages (under the real root, as on the live site), a small PDF for every
# PDF those pages link, and a Classic list written by FE's own PutClassicFanzineList.
def FreshServer() -> fakeftp.FakeServer:
    harness.Server=fakeftp.Install()
    S=harness.Server
    S.Put(f"/{T}/FanzinesEditor Log.txt", "")       # (The test root exists, with its log)
    for d in FIXTURE_DIRS:
        html=open(os.path.join(harness.FIXTURES_DIR, f"{d}.html"), encoding="utf-8").read()
        S.Put(f"/fanzines/{d}/index.html", html)
        for name in set(re.findall(r'href="([^"/:#?]+\.pdf)"', html, flags=re.IGNORECASE)):
            S.Put(f"/fanzines/{d}/{name}", open(MakePdf(os.path.join(TMP, "seed.pdf"), f"{d} {name}"), "rb").read())
    PutClassicList(0)
    Dialogs.Clear()
    return S


def MakeCfl(serverDir: str, name: str) -> ClassicFanzinesLine:
    c=ClassicFanzinesLine()
    c.ServerDir=serverDir
    c.Name=FanzineNames(name, "")
    c.Editors="Someone"
    c.Dates="1943-1946"
    c.Type="Genzine"
    c.Issues="3"
    c.Created=ClassicFanzinesDate("March 3, 2020")
    c.Updated=ClassicFanzinesDate("March 3, 2020")
    return c


def PutClassicList(extra: int, root: str="fanzines") -> None:
    """Write a Classic list with the fixture fanzines plus 'extra' made-up ones, using FE's own writer."""
    cfls=[MakeCfl(d, name) for d, name in FIXTURE_DIRS.items()]+[MakeCfl(f"Extra_{i:03}", f"Extra {i:03}") for i in range(extra)]
    FE.PutClassicFanzineList(cfls, root)


from harness import OpenPage, AddRow, EditFilename, Upload, MoveRows, Regenerate as RegenerateRow


def Page(d: str) -> str:
    return harness.Server.GetText(f"/{T}/{d}/index.html") or ""


def Files(d: str, root: str=T) -> list[str]:
    return harness.Server.Listing(f"/{root}/{d}")


def ServerPdf(path: str) -> dict:
    local=os.path.join(TMP, "downloaded.pdf")
    with open(local, "wb") as f:
        f.write(harness.Server.Get(path))
    return PdfFacts(local)


def Pdf(name: str, text: str="Test page", **kw) -> str:
    return MakePdf(os.path.join(TMP, name), text, **kw)


# ======================================================================================================================
def PureFunctions() -> None:
    R.Section("Dates, titles, headers")
    cd=ColDefinitionsList([ColDefinition(x) for x in ("Link", "Display Text", "Month", "Day", "Year")])
    for cells, want in ((["", "", "July", "4", "1978"], "July 4, 1978"), (["", "", "July", "", "1978"], "July 1978"),
                        (["", "", "", "", "1978"], "1978"), (["", "", "", "4", "1978"], "1978"), (["", "", "", "", ""], "")):
        got=FIP.DateFmt(FanzineIndexPageTableRow(cd, cells), cd)
        R.Check(got == want, f"DateFmt {cells[2:]} -> {want!r}", f"got {got!r}")
    cd2=ColDefinitionsList([ColDefinition(x) for x in ("Link", "Display Text", "Mo.", "Year")])
    try:
        got=FIP.ColSelect(FanzineIndexPageTableRow(cd2, ["", "", "July", "1978"]), cd2, "month")
    except Exception as e:
        got=f"{type(e).__name__}"
    R.Check(got == "July", "ColSelect finds a column only by its canonical name ('Mo.' for month)", f"got {got!r}")

    # Only column 0 holds the link's display text.  A later column named Issue or Title belongs to the page, and
    # renaming it here would publish the new name (Spectator has a published column headed "Display Text").
    for headers, wantNames, wantLabels, why in (
            (["Issue", "Editor", "Year"], ["Display Text", "Editor", "Year"], ["Display Text", "Editor", "Year"],
             "column 0 named Issue is the display text"),
            (["Title", "Editor", "Year"], ["Display Text", "Editor", "Year"], ["Display Text", "Editor", "Year"],
             "so is column 0 named Title, as on the old pages"),
            (["Issue", "Title", "Editor"], ["Display Text", "Title", "Editor"], ["Display Text", "Title", "Editor"],
             "but a later Title column keeps its name, and isn't labelled Display Text either"),
            (["Issue", "Issue", "Editor"], ["Display Text", "Issue", "Editor"], ["Display Text", "Issue", "Editor"],
             "a later Issue column keeps its name too (it was renamed '(Issue)' and published that way)"),
            (["Issue", "Vol", "Notes"], ["Display Text", "Volume", "Notes"], ["Display Text", "Vol", "Notes"],
             "other columns are still canonicized (Vol -> Volume, shown as 'Vol')")):
        cds=FIP.ColNamesToColDefs(headers)
        got=([c.Name for c in cds], [c.Preferred for c in cds])
        R.Check(got == (wantNames, wantLabels), why, f"got {got}")

    for series, issue, want in (("Quandry", "Quandry 13", "Quandry 13"), ("Quandry", "Q 13", "Quandry: Q 13"),
                                ("The Fantasy Rotator", "Fantasy Rotator 312", "Fantasy Rotator 312"),
                                ("MT VOID", "MT_VOID 1234", "MT_VOID 1234"), ("Fan", "Fanac 3", "Fan: Fanac 3"), ("Apollo", "", "Apollo")):
        got=FIP.PDFTitle(series, issue)
        R.Check(got == want, f"PDF title {series!r} + {issue!r} -> {want!r}", f"got {got!r}")

    root="https://www.fanac.org/fanzines/"
    fmt, items=FIP.PDFHeader("Quandry", "Quandry 13", "Quandry", "September 1951")
    R.Check(fmt == "{} ({})  --  from {}" and items == [root+"Quandry/", "Quandry 13", "September 1951", root, "fanac.org/fanzines"],
            "header: issue named after the fanzine -> one name, linked", f"{fmt!r} {items}")
    fmt, items=FIP.PDFHeader("Clubby News", "Bulletin 4", "Clubby_News", "")
    R.Check(fmt == "{}: {}  --  from {}" and items[:4] == [root+"Clubby_News/", "Clubby News", root+"Clubby_News/", "Bulletin 4"],
            "header: issue with its own name -> both names, both linked; no date, no parentheses", f"{fmt!r} {items}")


def PdfWork() -> None:
    R.Section("PDF metadata and headers (local files)")
    cd=ColDefinitionsList([ColDefinition(x) for x in ("Link", "Display Text", "Editor", "Month", "Day", "Year", "Mailing")])
    row=FanzineIndexPageTableRow(cd, ["x.pdf", "Rabanos 67", "", "January", "27", "1966", "Apa-L 67"])
    src=Pdf("meta.pdf", xmpTitle="Scan0001")
    copy=FIP.SetPDFMetadata(src, row, cd, editors="Fred Patten<br>Bruce Pelz", mainName="Rabanos", country="US", fanzineType="Apazine")
    f=PdfFacts(copy)
    md=f["metadata"]
    R.Check(md["title"] == "Rabanos 67", "title leaves off the fanzine name the issue name begins with", md["title"])
    R.Check(md["author"] == "Fred Patten, Bruce Pelz", "author: the fanzine's editors, <br> -> comma (no Editor in the row)", md["author"])
    R.Check(md["subject"] == "Fanzine; Rabanos; Apazine; fan history; fanac.org", "subject", md["subject"])
    R.Check(md["keywords"] == "Rabanos, January 27, 1966, Apa-L 67, US, fanac.org, fan history, science fiction fanzine", "keywords", md["keywords"])
    R.Check(f["xmp"] == "", "the scanner's XMP metadata (title 'Scan0001') is removed")
    os.remove(copy)

    bad=os.path.join(TMP, "bad.pdf")
    open(bad, "wb").write(b"%PDF-1.4\nthis is not really a pdf\n")
    import fitz
    enc=os.path.join(TMP, "enc.pdf")
    d=fitz.open(Pdf("plain.pdf"))
    d.save(enc, encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="secret", owner_pw="secret")
    d.close()
    for path, what in ((bad, "damaged"), (enc, "encrypted"), (os.path.join(TMP, "missing.pdf"), "missing")):
        try:
            got=FIP.SetPDFMetadata(path, row, cd, mainName="X")
        except Exception as e:
            got=f"raised {type(e).__name__}"
        R.Check(got == "", f"{what} PDF: refused cleanly", f"got {got!r}")

    copy, problem=FIP.PrepareIssuePdf(src, row, cd, "Rabanos", editors="Fred Patten", mainName="Rabanos")
    f=PdfFacts(copy)
    R.Check(problem == "" and f["hasHeader"] and "Rabanos 67 (January 27, 1966)" in f["header"], "header stamped on page 1", f["header"])
    R.Check(f["links"] == ["https://www.fanac.org/fanzines/Rabanos/", "https://www.fanac.org/fanzines/"], "header links", str(f["links"]))
    srcHeight=PdfFacts(src)["height"]
    title=[s for s in f["spans"] if s[0] == 11]
    eds=[s for s in f["spans"] if s[0] == 9]
    R.Check(len(eds) == 1 and eds[0][5] == "ed: Fred Patten" and abs(eds[0][1]-title[0][1]) < 0.1 and eds[0][2] >= title[0][4],
            "editor line: 9 point, below the title, starting where the title starts", f"{eds} {title[:1]}")
    R.Check(f["height"]-srcHeight == 33, "the editor line adds only 5 points to the header (28 -> 33)", f"{f['height']-srcHeight}")
    from PDFHelpers import AddPdfPageHeader
    AddPdfPageHeader(copy, "{}  --  from {}", ["https://www.fanac.org/fanzines/B/", "Replacement Header", "https://www.fanac.org/fanzines/", "fanac.org/fanzines"],
                     logo=FIP._g_headerLogo)
    f=PdfFacts(copy)
    R.Check("Replacement Header" in f["header"] and "Rabanos" not in f["header"] and "Fred" not in f["header"] and "\x00" not in f["header"],
            "a replaced header is readable, and the old one's text (editor line too) is gone", f["header"])
    R.Check(f["height"]-srcHeight == 28, "replacing it with a header without an editor line shrinks the page back to +28", f"{f['height']-srcHeight}")
    os.remove(copy)

    many="Terry Carr\nDave Rike\nRon Ellik\nBob Pavlat\nBill Rotsler\nBjo Trimble\nTed White\nWalt Willis\nBob Shaw"
    copy, problem=FIP.PrepareIssuePdf(src, row, cd, "Rabanos", editors=many, mainName="Rabanos")
    f=PdfFacts(copy)
    title=[s for s in f["spans"] if s[0] == 11]
    eds=[s for s in f["spans"] if s[0] == 9]
    R.Check(len(eds) == 1 and eds[0][5].startswith("ed: Terry Carr, Dave Rike") and eds[0][5].endswith("...") and eds[0][3] <= max(s[3] for s in title),
            "a long editor list is cut short with '...' before the title line's right end", f"{eds} title ends {max(s[3] for s in title)}")
    os.remove(copy)
    rowEd=FanzineIndexPageTableRow(cd, ["x.pdf", "Rabanos 68", "Bruce Pelz", "February", "", "1966", ""])
    copy, problem=FIP.PrepareIssuePdf(src, rowEd, cd, "Rabanos", editors="Fred Patten", mainName="Rabanos")
    eds=[s[5] for s in PdfFacts(copy)["spans"] if s[0] == 9]
    R.Check(eds == ["ed: Bruce Pelz"], "the issue's own Editor overrides the fanzine's", str(eds))
    os.remove(copy)
    for editors in ("", "(uncredited)"):
        copy, problem=FIP.PrepareIssuePdf(src, row, cd, "Rabanos", editors=editors, mainName="Rabanos")
        f=PdfFacts(copy)
        R.Check(problem == "" and f["hasHeader"] and not [s for s in f["spans"] if s[0] == 9] and f["height"]-srcHeight == 28,
                f"editors {editors!r}: no editor line, header as before (+28)", f"{f['spans']} {f['height']-srcHeight}")
        os.remove(copy)

    for rotation in (90, 180, 270):
        copy, problem=FIP.PrepareIssuePdf(Pdf(f"rot{rotation}.pdf", rotation=rotation), row, cd, "Rabanos", mainName="Rabanos")
        f=PdfFacts(copy)
        R.Check(not f["hasHeader"] and f["metadata"]["title"] == "Rabanos 67" and f"rotated {rotation}" in problem,
                f"page 1 rotated {rotation}: metadata, but no header, and says why", problem)
        os.remove(copy)


def Deltas() -> None:
    R.Section("Pending changes (DeltaTracker)")
    cd=ColDefinitionsList([ColDefinition("Link"), ColDefinition("Display Text")])
    mk=lambda name: FanzineIndexPageTableRow(cd, [name, "x"])
    dt=DeltaTracker(); r=mk("Apolo03.pdf"); dt.Add("C:/s/Apolo03.pdf", row=r); r.Cells[0]="Apollo03.pdf"; dt.Rename("Apolo03.pdf", "Apollo03.pdf", row=r)
    R.Check([d.Verb for d in dt.Deltas] == ["add"], "renaming a just-added file -> only the add")
    dt=DeltaTracker(); r=mk("a.pdf"); r.Cells[0]="b.pdf"; dt.Rename("a.pdf", "b.pdf", row=r); r.Cells[0]="c.pdf"; dt.Rename("b.pdf", "c.pdf", row=r)
    R.Check(len(dt.Deltas) == 1 and dt.Deltas[0].OldFilename == "a.pdf", "renamed twice -> one rename, from the original name")
    dt=DeltaTracker(); r=mk(""); r.Cells[0]="new.pdf"; dt.Rename("", "new.pdf", row=r)
    R.Check(dt.Deltas == [], "a filename typed into an empty row queues nothing")
    dt=DeltaTracker(); r=mk("a.pdf"); r.Cells[0]="b.pdf"; dt.Rename("a.pdf", "b.pdf", row=r); r.Cells[0]="c.pdf"
    dt.Replace(oldSourceFilename="b.pdf", newfilepathname="C:/s/c.pdf", row=r)
    R.Check([d.Verb for d in dt.Deltas] == ["replace"] and dt.Deltas[0].OldFilename == "a.pdf", "rename then Replace -> one replace of the original")
    dt=DeltaTracker(); r=mk("a.pdf"); dt.Add("C:/s/a.pdf", row=r); r.Cells[0]="b.pdf"
    dt.Replace(oldSourceFilename="a.pdf", newfilepathname="C:/t/b.pdf", row=r)
    R.Check([d.Verb for d in dt.Deltas] == ["add"], "add then Replace -> just the add")


def Uploads() -> None:
    R.Section("Uploading a fanzine page")
    S=FreshServer()
    w=OpenPage("Apollo")
    a=AddRow(w, "t_a.pdf", Pdf("t_a.pdf", "first"), "Apollo 91")
    b=AddRow(w, "t_b.pdf", Pdf("t_b.pdf", "second"), "Special Supplement")
    c=AddRow(w, "t_cx.pdf", Pdf("t_cx.pdf", "third"), "Apollo 93")
    EditFilename(w, c, "t_c.pdf")        # A typo fixed before uploading (FE-2)
    Upload(w)
    R.Check({"t_a.pdf", "t_b.pdf", "t_c.pdf"} <= set(Files("Apollo")) and "t_cx.pdf" not in Files("Apollo"), "files uploaded, the corrected name only")
    R.Check(all(n in Page("Apollo") for n in ("t_a.pdf", "t_b.pdf", "t_c.pdf")), "page published")
    R.Check(any(n.startswith("index - ") for n in Files("Apollo")), "the old page was backed up first")
    R.Check(not Dialogs.Messages and not Dialogs.Questions and w.deltaTracker.Deltas == [], "no messages; nothing pending", str(Dialogs.Messages))
    fa, fb=ServerPdf(f"/{T}/Apollo/t_a.pdf"), ServerPdf(f"/{T}/Apollo/t_b.pdf")
    R.Check(fa["hasHeader"] and fa["header"].startswith("Apollo 91") and fa["metadata"]["title"] == "Apollo 91", "PDF header and title", fa["header"])
    R.Check(fb["header"].startswith("Apollo: Special Supplement") and fb["links"].count("https://www.fanac.org/fanzines/Apollo/") == 2,
            "an issue with its own name gets both names, both linked", fb["header"])
    log=S.GetText(f"/{T}/FanzinesEditor Log.txt") or ""
    R.Check(log.count("<IssueName>") >= 3, "the uploads are in the FTP log")

    R.Check("t_a.pdf" in w.FilenamesInUse() and w.SplitOffFilenameClashes(["C:/x/T_A.PDF", "C:/y/new.pdf"])[0] == ["C:/y/new.pdf"],
            "a filename already in use (any case) is held back (FE-3)")

    R.Section("Upload failures leave the live page consistent (FE-4, FE-11)")
    d=AddRow(w, "t_d.pdf", Pdf("t_d.pdf"), "Apollo 94")
    EditFilename(w, a, "t_a2.pdf")
    before=Page("Apollo")
    S.Fail("stor", lambda p: p.endswith("/t_d.pdf"))
    Upload(w)
    S.ClearFailures()
    R.Check(Page("Apollo") == before and "t_a.pdf" in Files("Apollo") and "t_a2.pdf" not in Files("Apollo"), "an upload fails: page not published, rename not done")
    R.Check(sorted(x.Verb for x in w.deltaTracker.Deltas) == ["add", "rename"] and Dialogs.Questions and Dialogs.Messages and "not published" in Dialogs.Messages[-1],
            "both still pending; the user was asked and told")
    Upload(w)
    R.Check("t_a2.pdf" in Files("Apollo") and "t_d.pdf" in Files("Apollo") and w.deltaTracker.Deltas == [], "retry completes")

    EditFilename(w, b, "t_b2.pdf")
    EditFilename(w, c, "t_c2.pdf")
    before=Page("Apollo")
    S.Fail("stor", lambda p: p.endswith(f"/{T}/Apollo/index.html"))
    Upload(w)
    S.ClearFailures()
    R.Check(Page("Apollo") == before and {"t_b.pdf", "t_c.pdf"} <= set(Files("Apollo")) and not {"t_b2.pdf", "t_c2.pdf"} & set(Files("Apollo")),
            "the page itself fails to upload: both renames undone")
    Upload(w)
    EditFilename(w, b, "t_b3.pdf")
    EditFilename(w, c, "t_c3.pdf")
    S.Fail("rename", lambda p: p.endswith("/t_c3.pdf"))
    Upload(w)
    S.ClearFailures()
    R.Check("t_b2.pdf" in Files("Apollo") and "t_b3.pdf" not in Files("Apollo"), "the second rename fails: the first is undone")
    Upload(w)

    bad=os.path.join(TMP, "t_bad.pdf")
    open(bad, "wb").write(b"%PDF-1.4\nnot really\n")
    badrow=AddRow(w, "t_bad.pdf", bad, "Apollo 95")
    AddRow(w, "t_e.pdf", Pdf("t_e.pdf"), "Apollo 96")
    before=Page("Apollo")
    Upload(w)
    R.Check(Page("Apollo") == before and "t_e.pdf" in Files("Apollo") and any("could not be read as a PDF" in q for q in Dialogs.Questions),
            "a damaged PDF: asked about, page not published, the good file still uploaded")
    w.deltaTracker.Delete(serverDirName="Apollo", row=badrow)
    w.Datasource.Rows.remove(badrow)
    Upload(w)

    R.Section("Re-using a name (FE-4 ordering)")
    old=ServerPdf(f"/{T}/Apollo/t_e.pdf")["words"]
    erow=[x for x in w.Datasource.Rows if x[0] == "t_e.pdf"][0]
    w.deltaTracker.Delete(serverDirName="Apollo", row=erow)
    w.Datasource.Rows.remove(erow)
    AddRow(w, "t_e.pdf", Pdf("t_e_new.pdf", "REPLACEMENT"), "Apollo 96")
    Upload(w)
    R.Check("t_e.pdf" in Files("Apollo") and "REPLACEMENT" in ServerPdf(f"/{T}/Apollo/t_e.pdf")["words"], "delete a row, re-add the name: the new file survives")
    EditFilename(w, d, "t_d4.pdf")
    AddRow(w, "t_d.pdf", Pdf("t_d_new.pdf", "NEWER"), "Apollo 97")
    Upload(w)
    R.Check("NEWER" not in ServerPdf(f"/{T}/Apollo/t_d4.pdf")["words"] and "NEWER" in ServerPdf(f"/{T}/Apollo/t_d.pdf")["words"],
            "rename a file away, add a new one under its old name: each keeps its own content")

    R.Section("Headers that can't be added")
    real=FIP.AddPdfPageHeader
    FIP.AddPdfPageHeader=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("simulated"))
    AddRow(w, "t_f.pdf", Pdf("t_f.pdf"), "Apollo 98")
    Upload(w)
    FIP.AddPdfPageHeader=real
    f=ServerPdf(f"/{T}/Apollo/t_f.pdf")
    R.Check("t_f.pdf" in Page("Apollo") and not f["hasHeader"] and f["metadata"]["title"] == "Apollo 98" and Dialogs.Messages and "without their page header" in Dialogs.Messages[-1],
            "the header fails: uploaded anyway with its metadata, and listed")
    AddRow(w, "t_rot.pdf", Pdf("t_rot.pdf", rotation=90), "Apollo 99")
    Upload(w)
    f=ServerPdf(f"/{T}/Apollo/t_rot.pdf")
    R.Check(not f["hasHeader"] and f["rotation"] == 90 and Dialogs.Messages and "rotated 90" in Dialogs.Messages[-1], "page 1 rotated: no header, and says why")

    R.Section("Issue counts for the Classic list (FE-6)")
    w.Datasource.AppendEmptyRows(2)         # A text row and an empty row: neither is an issue
    w.Datasource.Rows[-2].IsTextRow=True
    w.Datasource.Rows[-2][0]="Some notes about these issues"
    Upload(w)
    want=sum(1 for x in w.Datasource.Rows if x.IsNormalRow and x[0].strip())
    R.Check(w.CFL is not None and w.CFL.Issues == str(want) and want < len(w.Datasource.Rows), f"Apollo: {want} issues, not {len(w.Datasource.Rows)} rows", w.CFL and w.CFL.Issues)
    w.Destroy()
    w=OpenPage("Australian_SF_News")
    Upload(w)
    R.Check(w.CFL is not None and w.CFL.Issues == "52", "Australian SF News: 52, counting its three html-chain issues", w.CFL and w.CFL.Issues)
    w.Destroy()


def NamelessFiles() -> None:
    """A row with a file but no Display Text writes <a href="x.pdf"></A> -- a link with nothing to click on.  Pages
    like that are on the live site (FanacAnalyzer read their raw HTML as the issue's name), so FE must say which rows
    they are rather than publish them silently or invent a name for them."""
    R.Section("A file with no Display Text is reported, not published silently")
    FreshServer()
    w=OpenPage("Apollo")
    AddRow(w, "t_n1.pdf", Pdf("t_n1.pdf", "nameless"), "")
    AddRow(w, "t_n2.pdf", Pdf("t_n2.pdf", "also nameless"), "   ")
    AddRow(w, "t_n3.pdf", Pdf("t_n3.pdf", "named"), "Apollo 99")
    logged=[]
    realLogError=FIP.LogError
    FIP.LogError=lambda s, *a, **k: logged.append(s)
    try:
        Upload(w)
    finally:
        FIP.LogError=realLogError
    page=Page("Apollo")
    said=[s for s in logged if "no Display Text" in s]
    R.Check(len(said) == 1 and "t_n1.pdf" in said[0] and "t_n2.pdf" in said[0] and "t_n3.pdf" not in said[0],
            "both rows are named in one logged error; the row which has a name isn't", said[0][:200] if said else str(logged))
    R.Check('<a href="t_n1.pdf"></A>' in page, "the row is written as it stands: no name is invented for it")
    R.Check('<a href="t_n3.pdf">Apollo 99</A>' in page, "and a row which has a Display Text is unaffected")
    w.Destroy()


def Regenerate() -> None:
    R.Section("Regenerate PDF Header")
    S=FreshServer()
    w=OpenPage("Apollo")
    real=FIP.AddPdfPageHeader
    FIP.AddPdfPageHeader=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("simulated"))
    r=AddRow(w, "t_g.pdf", Pdf("t_g.pdf"), "Apollo 91")
    Upload(w)
    FIP.AddPdfPageHeader=real
    RegenerateRow(w, r)
    f=ServerPdf(f"/{T}/Apollo/t_g.pdf")
    R.Check(f["hasHeader"] and f["header"].startswith("Apollo 91") and Dialogs.Messages and "regenerated" in Dialogs.Messages[-1], "adds the missing header", f["header"])
    r[1]="Apollo 91 (corrected)"
    RegenerateRow(w, r)
    f=ServerPdf(f"/{T}/Apollo/t_g.pdf")
    R.Check(f["header"].startswith("Apollo 91 (corrected)") and f["metadata"]["title"] == "Apollo 91 (corrected)", "picks up an edited issue name", f["header"])
    EditFilename(w, r, "t_g2.pdf")
    RegenerateRow(w, r)
    R.Check(Dialogs.Messages and "not yet been uploaded" in Dialogs.Messages[-1], "a row with a change not yet uploaded is refused")
    w.deltaTracker.Deltas.clear()
    r[0]="t_g.pdf"

    live=next(x for x in w.Datasource.Rows if x.IsNormalRow and x[0].lower().endswith(".pdf") and not x[0].startswith("t_"))
    before=S.Get(f"/fanzines/Apollo/{live[0]}")
    RegenerateRow(w, live)
    R.Check(S.Get(f"/fanzines/Apollo/{live[0]}") == before and ServerPdf(f"/{T}/Apollo/{live[0]}")["hasHeader"],
            "test mode, a file only on the real site: re-done onto the test site; the real file untouched")
    w.Destroy()


def Moves() -> None:
    R.Section("Move to Different Fanzine (FE-25)")
    S=FreshServer()
    w=OpenPage("Apollo")
    rows={n: AddRow(w, n, Pdf(n, n) if n.endswith(".pdf") else _Html(n), f"Apollo {i}") for i, n in
          enumerate(("t_m1.pdf", "t_m2.html", "t_m3.pdf", "t_m4.pdf", "t_m5.pdf", "t_m6.pdf"), start=81)}
    Upload(w)

    def Move(*names: str) -> None:
        MoveRows(w, [rows[n] for n in names], "Innuendo")

    Move("t_m1.pdf")
    f=ServerPdf(f"/{T}/Innuendo/t_m1.pdf") if "t_m1.pdf" in Files("Innuendo") else {"links": [], "metadata": {"title": ""}}
    R.Check("t_m1.pdf" in Files("Innuendo") and "t_m1.pdf" not in Files("Apollo"), "a PDF: copied to the target, the original deleted")
    R.Check(f["links"][:1] == ["https://www.fanac.org/fanzines/Innuendo/"] and f["metadata"]["title"].startswith("Innuendo"), "re-stamped for the new fanzine", str(f["links"]))
    R.Check("t_m1.pdf" not in Page("Apollo") and "t_m1.pdf" in Page("Innuendo") and "move file" in (S.GetText(f"/{T}/FanzinesEditor Log.txt") or ""),
            "both pages updated; logged")
    Move("t_m2.html")
    R.Check("t_m2.html" in Files("Innuendo") and "t_m2.html" not in Files("Apollo") and "t_m2.html" in Page("Innuendo"), "an html page: copied, original deleted")

    realRestamp=FIP.FanzineIndexPageWindow.RestampPdfOnServer
    FIP.FanzineIndexPageWindow.RestampPdfOnServer=lambda self, *a, **k: "simulated re-stamp failure"
    Move("t_m3.pdf")
    FIP.FanzineIndexPageWindow.RestampPdfOnServer=realRestamp
    R.Check("t_m3.pdf" in Files("Innuendo") and "t_m3.pdf" not in Files("Apollo") and any("could not be updated" in m for m in Dialogs.Messages),
            "a PDF that can't be re-stamped is moved as it is, and the user is told")

    before=Page("Apollo")
    S.Fail("stor", lambda p: p.endswith("/Innuendo/t_m5.pdf"))
    Move("t_m4.pdf", "t_m5.pdf")
    S.ClearFailures()
    R.Check(not {"t_m4.pdf", "t_m5.pdf"} & set(Files("Innuendo")) and {"t_m4.pdf", "t_m5.pdf"} <= set(Files("Apollo")) and Page("Apollo") == before,
            "a copy fails part way: the copies already made are removed; nothing changed")
    R.Check(any("stopped" in m and "nothing has been changed" in m for m in Dialogs.Messages), "and the user is told")

    realOnUpload=FIP.FanzineIndexPageWindow.OnUpload
    tgtBefore, srcBefore=Page("Innuendo"), Page("Apollo")
    FIP.FanzineIndexPageWindow.OnUpload=lambda self, event: None if self.ServerDir == "Innuendo" else realOnUpload(self, event)
    Move("t_m4.pdf")
    FIP.FanzineIndexPageWindow.OnUpload=realOnUpload
    R.Check("t_m4.pdf" not in Files("Innuendo") and "t_m4.pdf" in Files("Apollo") and Page("Innuendo") == tgtBefore and Page("Apollo") == srcBefore,
            "the target page can't be uploaded: the move is undone")

    FIP.FanzineIndexPageWindow.OnUpload=lambda self, event: None if self.ServerDir == "Apollo" else realOnUpload(self, event)
    Move("t_m6.pdf")
    FIP.FanzineIndexPageWindow.OnUpload=realOnUpload
    R.Check("t_m6.pdf" in Files("Innuendo") and "t_m6.pdf" in Files("Apollo") and "t_m6.pdf" in Page("Apollo") and "t_m6.pdf" in Page("Innuendo"),
            "this page can't be uploaded afterwards: the file stays in both places, so both pages' links work")
    w.Destroy()


def _Html(name: str) -> str:
    path=os.path.join(TMP, name)
    open(path, "w", encoding="utf-8").write("<html><body>page one</body></html>")
    return path.replace("\\", "/")


def PageWindow() -> None:
    R.Section("The fanzine page window")
    FreshServer()
    w=OpenPage("Apollo")
    w._dataGrid.clickedRow, w._dataGrid.clickedColumn=2, 3
    n=w.Datasource.NumRows
    Dialogs.Clear()
    class Evt:
        def Skip(self): pass
    w.OnPopupInsertLinkLine(Evt())
    R.Check(w.Datasource.NumRows == n, "Insert a Link line, Cancel: nothing inserted (FE-9)")
    Dialogs.TextAnswers.extend(["https://example.org/x.html", "Some notes"])
    w.OnPopupInsertLinkLine(Evt())
    r=w.Datasource.Rows[2]
    R.Check(r.IsLinkRow and r[0] == "https://example.org/x.html" and r[1] == "Some notes", "Insert a Link line: URL and text in the link's own cells (FE-9)", str(r.Cells[:3]))

    for pasted, want in (("https://fanac.org/fanzines/Innuendo/Fanac%20%233.pdf", ("../Innuendo/Fanac%20%233.pdf", "")),
                         ('<a href="https://fanac.org/fanzines/Innuendo/">Innuendo &amp; more</a>', ("../Innuendo/", "Innuendo & more")),
                         ("<A HREF='https://example.org/x.php?a=1&amp;b=2'><b>X</b></A>", ("https://example.org/x.php?a=1&b=2", "X")),
                         ("www.example.org/x.html", ("https://www.example.org/x.html", "")),
                         ("fanac.org/fanzines/Innuendo/x.pdf", ("../Innuendo/x.pdf", "")),
                         ("  ../Other/x.pdf  ", ("../Other/x.pdf", ""))):
        got=FIP.LinkFromPaste(pasted, "Apollo", decode=False)
        R.Check(got == want, f"a link line accepts {pasted!r} -> {want!r}", f"got {got!r}")

    Dialogs.TextAnswers.extend(['<a href="https://fanac.org/fanzines/Innuendo/Fanac%20%233.pdf">Fanac 3</a>', "Fanac 3"])
    w.OnPopupInsertLinkLine(Evt())
    r=w.Datasource.Rows[2]
    R.Check(r.IsLinkRow and r[0] == "../Innuendo/Fanac%20%233.pdf" and r[1] == "Fanac 3", "a pasted HTML link: its URL, made relative and left encoded", str(r.Cells[:2]))
    Upload(w)
    R.Check('<a href="../Innuendo/Fanac%20%233.pdf">Fanac 3</a>' in Page("Apollo"), "and written to the page so (a link line's link isn't re-escaped)")
    w.Destroy()

    R.Section("Local directory (FE-7, FE-12)")
    table=Settings().Get("Server To Local Table Name")
    Settings("ServerToLocal").Load(table)
    harness.RemoveKey(Settings("ServerToLocal").Dict, "Innuendo")
    Settings("ServerToLocal").Save()        # (the temporary copy)
    w=OpenPage("Innuendo")
    R.Check(w.bUpload.IsEnabled() and w.tUploadNote.GetLabel().strip() == "", "no local root path: Upload is enabled without a local directory")
    w.Destroy()
    harness._SetSetting(Settings, "Local Directory Root Path", harness.TMP)
    w=OpenPage("Innuendo")
    w.EndModal=lambda *a, **k: None
    R.Check(not w.bUpload.IsEnabled() and w.tUploadNote.GetLabel().strip() == f"Upload needs a Local Directory -- type the name of this fanzine's folder in {harness.TMP}",
            "with one: Upload waits for it, and says what to type", w.tUploadNote.GetLabel())
    class Key:
        def __init__(self, c): self.c=c
        def GetKeyCode(self): return self.c
        def Skip(self): pass
    w.tLocalDirectory.SetInsertionPointEnd()
    for ch in "INNU":
        w.OnLocalDirectoryChar(Key(ord(ch)))
    R.Check(w.tLocalDirectory.GetValue() == "INNU" and w.bUpload.IsEnabled() and w.tUploadNote.GetLabel().strip() == "", "typing a name enables Upload")
    backups=lambda: [x for x in os.listdir(harness.TMP) if x.startswith("ServerToLocal - ")]
    w.OnClose(None)
    w.Destroy()
    Settings("ServerToLocal").Load(table)
    R.Check(Settings("ServerToLocal").Get("Innuendo") == "INNU" and len(backups()) == 1, "closing saves it (one backup of the table)")
    w=OpenPage("Innuendo")
    w.EndModal=lambda *a, **k: None
    w.OnClose(None)
    w.Destroy()
    R.Check(len(backups()) == 1, "closing again with no change writes nothing (FE-12)")
    harness._SetSetting(Settings, "Local Directory Root Path", "")


def MainWindow() -> None:
    R.Section("The main window's Classic list (FE-5, FE-8)")
    S=FreshServer()
    A=FE.FanzinesEditorWindow(None)
    B=FE.FanzinesEditorWindow(None)
    R.Check(not A.NeedsSaving() and len(A._fanzinesList) == len(FIXTURE_DIRS), "loads the list; nothing to save", str(len(A._fanzinesList)))
    A.tSearch.SetValue("Apollo")
    A.SearchFanzineList()
    R.Check(not A.NeedsSaving() and not A.GetTitle().rstrip().endswith("*"), "a search is not a change (FE-8)")
    A.OnClearSearch(None)

    def Edited(win, d, editors):
        c=[x for x in win._fanzinesList if x.ServerDir == d][0].Deepcopy()
        c.Editors=editors
        c._created=None
        return c
    A.MergeCFLIntoList(Edited(A, "Apollo", "EDITED BY A"))
    B.MergeCFLIntoList(Edited(B, "Innuendo", "EDITED BY B"))
    Dialogs.Clear()
    A.OnUploadPressed(None)
    B.OnUploadPressed(None)
    fresh={c.ServerDir: c for c in FE.GetClassicFanzinesList()}
    R.Check(fresh["Apollo"].Editors == "EDITED BY A" and fresh["Innuendo"].Editors == "EDITED BY B", "two sessions: both changes survive")
    R.Check(str(fresh["Apollo"].Created) == str(ClassicFanzinesDate("March 3, 2020")), "the creation date is kept (FE-1)", str(fresh["Apollo"].Created))
    R.Check(not A.NeedsSaving() and not B.NeedsSaving() and not Dialogs.Messages, "both saved, no messages", str(Dialogs.Messages))
    A._listChanges["australian_sf_news"]=None
    A.OnUploadPressed(None)
    B.MergeCFLIntoList(Edited(B, "Apollo", "EDITED BY B AGAIN"))
    B.OnUploadPressed(None)
    fresh={c.ServerDir: c for c in FE.GetClassicFanzinesList()}
    R.Check("Australian_SF_News" not in fresh and fresh["Apollo"].Editors == "EDITED BY B AGAIN", "a deletion isn't undone by the other session; the later edit wins")
    A.Destroy()
    B.Destroy()


def Safeguards() -> None:
    R.Section("Startup without the list (FE-10)")
    S=FreshServer()
    S.Files.pop("/fanzines/Classic_Fanzines.html")
    m=FE.FanzinesEditorWindow(None)
    R.Check(m.failure and any("could not be downloaded" in x for x in Dialogs.Messages),
            "the window says why and reports failure, so main() closes FE (was: an invisible window holding the lock)")
    m.Destroy()

    R.Section("A list that wasn't read completely (FE-28)")
    S=FreshServer()
    PutClassicList(40)
    m=FE.FanzinesEditorWindow(None)
    c=[x for x in m._fanzinesList if x.ServerDir == "Apollo"][0].Deepcopy()
    c.Editors="SHOULD NOT BE WRITTEN"
    m.MergeCFLIntoList(c)
    PutClassicList(2)       # What a partial read would look like: 5 entries where this session has 43
    before=S.Get("/fanzines/Classic_Fanzines.html")
    Dialogs.Clear()
    m.OnUploadPressed(None)
    R.Check(not S.Exists(f"/{T}/Classic_Fanzines.html") and S.Get("/fanzines/Classic_Fanzines.html") == before and m.NeedsSaving(),
            "nothing written; the change is still pending")
    R.Check(any("probably wasn't read completely" in x for x in Dialogs.Messages), "and the user is told why")
    PutClassicList(36)      # Seven fewer than this session has: other sessions' deletions, which is fine
    Dialogs.Clear()
    m.OnUploadPressed(None)
    back={x.ServerDir: x for x in FE.GetClassicFanzinesList()}
    R.Check(back["Apollo"].Editors == "SHOULD NOT BE WRITTEN" and not m.NeedsSaving() and not Dialogs.Messages,
            "a few fewer (other sessions' deletions) is fine: uploaded")
    m.Destroy()

    R.Section("No PDF library in the exe (FE-27)")
    FreshServer()
    w=OpenPage("Apollo")
    AddRow(w, "t_lib.pdf", Pdf("t_lib.pdf"), "Apollo 91")
    saved=sys.modules.get("fitz")
    sys.modules["fitz"]=None            # What an exe built without PyMuPDF looks like
    try:
        missing=FIP.PdfLibraryMissing()
        Upload(w)
    finally:
        sys.modules["fitz"]=saved
    R.Check(missing and any("missing PyMuPDF" in q for q in Dialogs.Questions), "the upload says the library is missing (was: 'could not be read as a PDF')",
            str(Dialogs.Questions[-1:]))
    R.Check(not FIP.PdfLibraryMissing(), "(and it's found again afterwards)")
    w.Destroy()


def TidyUps() -> None:
    R.Section("Updated only when something changed (FE-13)")
    S=FreshServer()
    w=OpenPage("Apollo")
    Upload(w)
    R.Check(w.CFL is not None and w.CFL._updated is None, "re-uploading a page unchanged leaves its Updated date unset")
    unchanged=w.CFL
    w.Datasource.Rows[0][1]=w.Datasource.Rows[0][1]+" (corrected)"
    Upload(w)
    R.Check(w.CFL._updated is not None and w.CFL.Updated.DaysAgo() == 0, "an upload that changes the page sets it to today")
    changed=w.CFL
    w.Destroy()
    m=FE.FanzinesEditorWindow(None)
    m.MergeCFLIntoList(unchanged)
    m.OnUploadPressed(None)
    entry={c.ServerDir: c for c in FE.GetClassicFanzinesList()}["Apollo"]
    R.Check(str(entry.Updated) == str(ClassicFanzinesDate("March 3, 2020")), "on the Classic list, the unchanged upload keeps the old date (no 'Updated' flag)",
            str(entry.Updated))
    m.MergeCFLIntoList(changed)
    m.OnUploadPressed(None)
    entry={c.ServerDir: c for c in FE.GetClassicFanzinesList()}["Apollo"]
    R.Check(entry.Updated.DaysAgo() == 0, "and the changed one is dated today", str(entry.Updated))
    m.Destroy()

    R.Section("No asserts in normal paths (FE-16)")
    S=FreshServer()
    S.Put("/fanzines/Classic_Fanzines.html", "<html><body>Not a list of fanzines</body></html>")
    try:
        got=FE.GetClassicFanzinesList()
    except Exception as e:
        got=f"raised {type(e).__name__}"
    R.Check(got is None, "a list file with no table in it: reported as unreadable (was: AssertionError)", str(got))
    FreshServer()
    w=OpenPage("Apollo")
    n=w.Datasource.NumRows
    w._dataGrid.clickedRow=1
    w.wxGrid.ClearSelection()
    w.OnPopupDelRow(None)
    R.Check(w.Datasource.NumRows == n-1 and [d.Verb for d in w.deltaTracker.Deltas] == ["delete"], "Delete Row(s) still works")
    w.Destroy()

    R.Section("A new Pages column goes before Notes (FE-19)")
    w=OpenPage("Apollo")
    w.Datasource.DeleteColumn(w.Datasource.ColHeaderIndex("pages"))
    before=[h for h in w.Datasource.ColHeaders]
    w.FillInPagesColumn()
    after=w.Datasource.ColHeaders
    R.Check(after.index("Pages") == after.index("Notes")-1 and [h for h in after if h != "Pages"] == before,
            "inserted just before Notes; the other columns unchanged", str(after))
    w.Destroy()


def TidyUps2() -> None:
    R.Section("Test mode read one way everywhere (FE-20)")
    S=FreshServer()
    S.Put(f"/{T}/Classic_Fanzines.html", S.Get("/fanzines/Classic_Fanzines.html").replace(b"Apollo</STRONG>", b"Apollo TEST ROOT</STRONG>"))
    harness._SetSetting(Settings, "Test mode", "yes")       # IsTrue accepts yes as well as True
    try:
        names=[c.Name.MainName for c in FE.GetClassicFanzinesList()]
    finally:
        harness._SetSetting(Settings, "Test mode", "True")
    R.Check("Apollo TEST ROOT" in names, "'Test mode=yes' reads the test root's list, like the rest of FE (was: the real one)", str(names))

    R.Section("Copying a main-list row (FE-21)")
    row=FE.FanzinesPageRow(["Apollo", "Innuendo"])
    copy=row.Copy()
    copy[0]="Changed"
    R.Check(row[0] == "Apollo", "changing the copy leaves the original alone")

    R.Section("Creating a fanzine in test mode (FE-29)")
    FreshServer()
    w=FIP.FanzineIndexPageWindow(None)
    w.tFanzineName.SetValue("Brand New Zine")
    w.tServerDirectory.ChangeValue("Brand_New_Zine")
    w.tDates.SetValue("1990-1991")
    AddRow(w, "bnz01.pdf", Pdf("bnz01.pdf"), "Brand New Zine 1")
    Upload(w)
    R.Check(not any("Attempt to copy" in x for x in Dialogs.Messages) and "bnz01.pdf" in Page("Brand_New_Zine") and w.CFL is not None,
            "uploaded without the spurious 'Attempt to copy index.html ... failed' message", str(Dialogs.Messages))
    w.Destroy()

    R.Section("An empty local directory stays typeable after an upload (FE-30)")
    harness.RemoveKey(Settings("ServerToLocal").Dict, "Innuendo")
    w=OpenPage("Innuendo")
    w.Datasource.Rows[0][1]+=" (corrected)"
    Upload(w)
    class Key:
        def __init__(self, c): self.c=c
        def GetKeyCode(self): return self.c
        def Skip(self): pass
    w.tLocalDirectory.SetInsertionPointEnd()
    w.OnLocalDirectoryChar(Key(ord("X")))
    R.Check(w.tLocalDirectory.GetValue() == "X", "typing still works (was: the box looked enabled but ignored keys)")
    w.Destroy()

    R.Section("Ticking Complete is a change (FE-32)")
    w=OpenPage("Apollo")
    w.cbComplete.SetValue(not w.cbComplete.GetValue())
    w.OnCheckComplete(None)
    R.Check(w.NeedsSaving() and w.GetTitle().rstrip().endswith("*"), "the page is marked as changed (was: no '*', no warning on closing)")
    Upload(w)
    R.Check(w.CFL is not None and w.CFL._updated is not None, "and its upload counts as a change (FE-13)")
    w.Destroy()


def Collections() -> None:
    R.Section("Collections: the collection's name is never in a PDF")
    cd=ColDefinitionsList([ColDefinition(x) for x in ("Link", "Display Text", "Editor", "Month", "Day", "Year", "Mailing")])
    src=Pdf("acrylic.pdf")

    def Prepare(rowEditor: str, editors: str, fanzineType: str="Collection") -> dict:
        row=FanzineIndexPageTableRow(cd, ["x.pdf", "Acrylic", rowEditor, "May", "", "1983", ""])
        copy, problem=FIP.PrepareIssuePdf(src, row, cd, "1980s_One_Shots", editors=editors, mainName="1980s One Shots", country="UK", fanzineType=fanzineType)
        f=PdfFacts(copy)
        os.remove(copy)
        f["problem"]=problem
        f["eds"]=[s[5] for s in f["spans"] if s[0] == 9]
        return f

    f=Prepare("", "various")
    md=f["metadata"]
    R.Check(md["title"] == "Acrylic", "title: just the fanzine's own name", md["title"])
    R.Check(f["problem"] == "" and f["header"].startswith("Acrylic (May 1983)") and "One Shots" not in f["header"], "header: just the fanzine's own name", f["header"])
    R.Check(f["links"][:1] == ["https://www.fanac.org/fanzines/1980s_One_Shots/"], "which still links to the collection's page (where the PDF is listed)", str(f["links"]))
    R.Check(md["subject"] == "Fanzine; fan history; fanac.org", "subject: neither the collection's name nor 'Collection'", md["subject"])
    R.Check("One Shots" not in md["keywords"] and md["keywords"].startswith("May 1983"), "keywords: no collection name", md["keywords"])
    R.Check(f["eds"] == [] and md["author"] == "", "the collection's editors are 'various' and the row has none: no editor line, no author", f"{f['eds']} {md['author']!r}")
    f=Prepare("Jane Doe", "various")
    R.Check(f["eds"] == ["ed: Jane Doe"] and f["metadata"]["author"] == "Jane Doe", "the row's own editor is used", str(f["eds"]))
    f=Prepare("", "Bruce Gillespie<br>Elaine Cochrane")
    R.Check(f["eds"] == ["ed: Bruce Gillespie, Elaine Cochrane"] and f["metadata"]["author"] == "Bruce Gillespie, Elaine Cochrane",
            "a collection with common editors: they're used", str(f["eds"]))
    f=Prepare("", "Meade Frierson III<br>various", fanzineType="Fanzine")
    R.Check(f["eds"] == [] and f["metadata"]["author"] == "", "'various' among the fanzine's editors (any type): no editor line, no author", str(f["eds"]))
    f=Prepare("", "Various Editors", fanzineType="Fanzine")
    R.Check(f["eds"] == [], "'Various Editors' too", str(f["eds"]))
    for cell, want in (("Avedon Carol / Rob Hansen", "Avedon Carol, Rob Hansen"), ("Alan Dorey  / Joseph Nicholas", "Alan Dorey, Joseph Nicholas"),
                       ("Diane  Goldman / Dana Siegel / David Singer", "Diane Goldman, Dana Siegel, David Singer"),
                       ("Len and June Moffatt", "Len and June Moffatt"), ("John Smith / various", "John Smith")):
        f=Prepare(cell, "Fred Patten", fanzineType="Fanzine")
        R.Check(f["eds"] == [f"ed: {want}"] and f["metadata"]["author"] == want, f"the issue's Editor cell {cell!r} -> {want!r}", f"{f['eds']} {f['metadata']['author']!r}")
    for cell in ("various", "uncredited", "(uncredited)"):
        f=Prepare(cell, "Fred Patten", fanzineType="Fanzine")
        R.Check(f["eds"] == [] and f["metadata"]["author"] == "", f"the issue's Editor cell {cell!r}: no editor, and not the series' editors instead",
                f"{f['eds']} {f['metadata']['author']!r}")
    f=Prepare("", "various", fanzineType="Fanzine")
    R.Check(f["metadata"]["title"] == "1980s One Shots: Acrylic" and f["header"].startswith("1980s One Shots: Acrylic"),
            "not a Collection: the fanzine's name is there as before", f["header"])

    R.Section("Changing a fanzine's type to or from Collection")
    FreshServer()
    w=OpenPage("Apollo")
    oldType=w.Datasource.FanzineType
    onSite=[f for f in (w.RowServerFilename(r) for r in w.Datasource.Rows) if f.lower().endswith(".pdf")]
    AddRow(w, "Apollo99.pdf", Pdf("Apollo99.pdf"), "Acrylic 1")

    def SetType(t: str) -> None:
        w.chFanzineType.SetSelection(w.chFanzineType.Items.index(t))
        w.OnFanzineTypeSelect(None)

    SetType("Collection")
    Upload(w)
    R.Check(len(Dialogs.Messages) == 1 and "changed from" in Dialogs.Messages[0] and f"{len(onSite)} PDFs" in Dialogs.Messages[0]
            and "include the collection's name, 'Apollo'" in Dialogs.Messages[0] and "Regenerate PDF Header" in Dialogs.Messages[0],
            f"{oldType} -> Collection: says the {len(onSite)} PDFs already on the site need regenerating (not the one just uploaded)", str(Dialogs.Messages))
    f=ServerPdf(f"/{T}/Apollo/Apollo99.pdf")
    R.Check(f["header"].startswith("Acrylic 1") and f["metadata"]["title"] == "Acrylic 1", "the one just uploaded is already right", f["header"])
    w.Datasource.Rows[-1][1]="Acrylic 1 (revised)"       # (Some change, so there's something to upload)
    Upload(w)
    R.Check(not any("changed from" in m for m in Dialogs.Messages), "uploading again: no warning", str(Dialogs.Messages))
    SetType(oldType)
    Upload(w)
    R.Check(len(Dialogs.Messages) == 1 and "leave out the fanzine's name, 'Apollo'" in Dialogs.Messages[0] and f"{len(onSite)+1} PDFs" in Dialogs.Messages[0],
            f"and back to {oldType}: says so again, for all {len(onSite)+1}", str(Dialogs.Messages))
    SetType("Genzine" if oldType != "Genzine" else "Fanzine")
    Upload(w)
    R.Check(not any("changed from" in m for m in Dialogs.Messages), "a change between two types that aren't Collection: no warning", str(Dialogs.Messages))
    w.Destroy()


def NewComputer() -> None:
    R.Section("On a new computer: missing local folders and table")
    S=FreshServer()
    table=Settings().Get("Server To Local Table Name")
    saved=open(table, encoding="utf-8").read()
    try:
        for what, content in (("missing", None), ("empty", "# nothing here yet\n")):
            if os.path.exists(table):
                os.remove(table)
            if content is not None:
                open(table, "w", encoding="utf-8").write(content)
            Dialogs.Clear()
            try:
                m=FE.FanzinesEditorWindow(None)
                got=m.failure
                m.Destroy()
            except BaseException as e:      # (SystemExit too: an empty table used to exit quietly)
                got=f"raised {type(e).__name__}"
            R.Check(got is True and len(Dialogs.Messages) == 1 and os.path.abspath(table) in Dialogs.Messages[0] and "copy" in Dialogs.Messages[0],
                    f"the server-to-local table {what}: FE says which file to copy over, and stops cleanly", f"{got} {Dialogs.Messages}")
    finally:
        open(table, "w", encoding="utf-8").write(saved)

    missingRoot=os.path.join(harness.TMP, "No such folder")
    harness._SetSetting(Settings, "Local Directory Root Path", missingRoot)
    try:
        Dialogs.Clear()
        m=FE.FanzinesEditorWindow(None)
        R.Check(not m.failure and len(Dialogs.Messages) == 1 and missingRoot in Dialogs.Messages[0] and "doesn't exist" in Dialogs.Messages[0]
                and "Local Directory Root Path" in Dialogs.Messages[0], "the local root folder missing: FE starts, and says which folder and how to fix it", str(Dialogs.Messages))
        m.Destroy()

        w=OpenPage("Apollo")
        w.tLocalDirectory.ChangeValue("APOLLO")
        AddRow(w, "Apollo98.pdf", Pdf("Apollo98.pdf"), "Apollo 98")
        before=S.Files.copy()
        Upload(w)
        R.Check(S.Files == before and len(Dialogs.Messages) == 1 and missingRoot in Dialogs.Messages[0] and "Nothing has been uploaded" in Dialogs.Messages[0]
                and w.NeedsSaving(), "and Upload stops before changing anything, saying why", str(Dialogs.Messages))
        os.makedirs(missingRoot)
        Upload(w)
        R.Check("Apollo98.pdf" in Files("Apollo") and os.path.exists(os.path.join(missingRoot, "APOLLO", "Apollo98.pdf")),
                "once the folder is created: uploaded, and filed in the fanzine's folder (created)", str(Dialogs.Messages))
        w.Destroy()
    finally:
        harness._SetSetting(Settings, "Local Directory Root Path", "")


def FtpFailures() -> None:
    R.Section("FTP failures can't hide a message box behind FE's windows")
    import ftplib
    import FTP as ftpmodule
    S=FreshServer()
    shown=[]
    stub=wx.MessageBox
    wx.MessageBox=lambda message, caption="", style=0, parent=None, *a, **k: shown.append((message, style, parent))
    realTls=ftplib.FTP_TLS
    def Refused(*a, **k):
        raise OSError("[WinError 10060] the connection attempt failed")
    ftplib.FTP_TLS=Refused
    m=FE.FanzinesEditorWindow(None)
    try:
        ftpmodule.FTP.g_credentials={"ID": "test", "PW": "", "host": "ftp.example.org"}
        ok=ftpmodule.FTP.RealReconnect(ftpmodule.FTP())
        R.Check(not ok and len(shown) == 1 and "Could not connect" in shown[0][0] and shown[0][2] is wx.GetApp().GetTopWindow()
                and shown[0][1] & wx.STAY_ON_TOP, "can't reconnect: the box has FE's window as its parent and stays on top (was: no parent)",
                str([(s[1], s[2]) for s in shown]))
        for kind, err in (("421 too many connections", ftplib.error_temp("421 Too many connections (8) from this IP")),
                          ("530 login refused", ftplib.error_perm("530 Login authentication failed")),
                          ("hangs up during login", EOFError("connection closed by the server"))):
            def Refuse(*a, **k):
                raise err
            ftplib.FTP_TLS=Refuse
            shown.clear()
            try:
                ok=ftpmodule.FTP.RealReconnect(ftpmodule.FTP())
            except Exception as e:
                ok=f"raised {type(e).__name__}"
            R.Check(ok is False and len(shown) == 1 and "Could not connect" in shown[0][0] and str(err) in shown[0][0],
                    f"the server refuses ({kind}): reported clearly, reconnect fails (was: escaped as an internal error)", f"{ok} {[s[0][:60] for s in shown]}")

        calls=[]
        class Old:              # The dead connection being replaced
            def close(self): calls.append("close")
            def quit(self): calls.append("quit")
        class New:              # A working new one
            def __init__(self, *a, **k): calls.append("connect")
            def prot_p(self): pass
            def cwd(self, d): return "250 OK. Current directory is /"
        ftpmodule.FTP.g_ftp=Old()
        ftpmodule.FTP.g_curdirpath="/"
        ftplib.FTP_TLS=New
        shown.clear()
        ok=ftpmodule.FTP.RealReconnect(ftpmodule.FTP())
        R.Check(ok is True and calls == ["close", "connect"] and isinstance(ftpmodule.FTP.g_ftp, New) and not shown,
                "a successful reconnect: the old connection is closed (not quit(), which waits out the timeout on a dead one)", str(calls))
    finally:
        ftplib.FTP_TLS=realTls
        wx.MessageBox=stub
        m.Destroy()

    def Dropped(*a):
        raise EOFError("connection dropped")
    S=FreshServer()
    S.nlst=Dropped
    ftpmodule.FTP.Reconnect=lambda self: False     # (FreshServer puts the fake one back)
    try:
        got=f"answered {ftpmodule.FTP().FileExists(f'/{T}/Apollo/index.html')}"
    except ConnectionError as e:
        got=str(e)
    except Exception as e:
        got=f"{type(e).__name__}: {e}"
    R.Check("Lost the connection" in got, "a check for a file, and the reconnect fails: stops with the error (was: answered 'no, it doesn't exist')", got)

    S=FreshServer()
    S.nlst=Dropped
    try:
        ftpmodule.FTP().FileExists(f"/{T}/Apollo/index.html")
        got="no exception"
    except ConnectionError as e:
        got=str(e)
    R.Check("Lost the connection" in got and len(Dialogs.Messages) == 0,
            "a check for a file fails twice: stops with a clear error, no parentless box (was: 'Exiting program' box, then NotImplementedError)", got)

    # (Nlst first moves into the folder, which lists its parent through FileExists; drop only the listing made in the folder)
    S=FreshServer()
    realNlst=S.nlst
    drops=[1]
    def DropsInApollo(*a):
        if S._cwd == "/fanzines/Apollo" and drops:
            drops.pop()
            raise EOFError("connection dropped")
        return realNlst(*a)
    S.nlst=DropsInApollo
    try:
        got=sorted(ftpmodule.FTP().Nlst("/fanzines/Apollo"))
    except Exception as e:
        got=f"{type(e).__name__}: {e}"
    R.Check(isinstance(got, list) and "index.html" in got and not drops, "a folder listing whose connection drops: retried after reconnecting (was: EOFError)", str(got)[:120])
    drops.extend([1, 1, 1])
    ftpmodule.FTP.Reconnect=lambda self: False     # (FreshServer puts the fake one back)
    try:
        got=f"answered {ftpmodule.FTP().Nlst('/fanzines/Apollo')}"
    except ConnectionError as e:
        got=str(e)
    except Exception as e:
        got=f"{type(e).__name__}: {e}"
    R.Check("Lost the connection" in got and "listing" in got,
            "and if reconnecting fails: stops with a clear error, not an empty list (callers copy or delete what's listed)", got)
    FreshServer()

    R.Section("The previous session's logs are kept")
    d=os.path.join(TMP, "logs")
    os.makedirs(d, exist_ok=True)
    for name in ("Log -- FanzinesEditor.txt", "Log (Errors) -- FanzinesEditor.txt"):
        open(os.path.join(d, name), "w", encoding="utf-8").write("last session "+name)
    FE.KeepPreviousLogs(d)
    kept=[open(os.path.join(d, n.replace(".txt", " (previous).txt")), encoding="utf-8").read() for n in ("Log -- FanzinesEditor.txt", "Log (Errors) -- FanzinesEditor.txt")]
    R.Check(kept == ["last session Log -- FanzinesEditor.txt", "last session Log (Errors) -- FanzinesEditor.txt"]
            and not os.path.exists(os.path.join(d, "Log -- FanzinesEditor.txt")), "both are kept as '(previous)' for the new session to start afresh", str(kept))
    FE.KeepPreviousLogs(d)
    R.Check(os.path.exists(os.path.join(d, "Log -- FanzinesEditor (previous).txt")), "and with no logs to keep, the previous ones are left alone")


def ReplaceURL() -> None:
    R.Section("Replace URL: links to fanac.org are stored relative to the page")
    for url, want in (("https://fanac.org/fanzines/Innuendo/Innuendo01.pdf", "../Innuendo/Innuendo01.pdf"),
                      ("https://www.fanac.org/fanzines/Other/Fanac%20%233.pdf", "../Other/Fanac #3.pdf"),
                      ("http://fanac.org/Fanac_Fan_History/x.html", "../../Fanac_Fan_History/x.html"),
                      ("//fanac.org/fanzines/Other/x.php?id=5", "../Other/x.php?id=5"),
                      ("https://fanac.org/fanzines/Other/", "../Other/"),
                      ("https://fanac.org/fanzines/Apollo/Apollo03.pdf", "Apollo03.pdf"),
                      ("https://example.org/zines/x.pdf", "https://example.org/zines/x.pdf"),
                      ("https://fanac.org.example.com/x.pdf", "https://fanac.org.example.com/x.pdf"),
                      ("../Other/x.pdf", "../Other/x.pdf")):
        got=FIP.RelativeFanacLink(url, "Apollo")
        R.Check(got == want, f"{url!r} -> {want!r}", f"got {got!r}")
    for url, want in (("", "https://fanac.org/fanzines/"), ("https://example.org/x", "https://example.org/x"),
                      ("../Other/Fanac #3.pdf", "https://fanac.org/fanzines/Other/Fanac %233.pdf")):
        got=FIP.BrowseTarget(url, "Apollo")
        R.Check(got == want, f"Browse opens {want!r} for {url!r}", f"got {got!r}")
    R.Check([FIP.IsLocalFilename(x) for x in ("Apollo03.pdf", "Fanac #3.pdf", "../Other/x.pdf", "https://x.org/y.pdf", "")] == [True, True, False, False, False],
            "only a plain filename is one of this fanzine's own files")

    opened=[]
    realOpen=FIP.webbrowser.open
    FIP.webbrowser.open=lambda u, *a, **k: opened.append(u)
    try:
        d=FIP.ReplaceURLDialog(None, "../Innuendo/Innuendo01.pdf", "Apollo")
        d.OnBrowse(None)
        d.Destroy()
    finally:
        FIP.webbrowser.open=realOpen
    R.Check(opened == ["https://fanac.org/fanzines/Innuendo/Innuendo01.pdf"], "the dialog's Browse opens the web browser there", str(opened))

    R.Section("Replace URL on a page")
    S=FreshServer()
    w=OpenPage("Apollo")
    items=[m.GetItemLabelText() for m in w.m_GridPopup.GetMenuItems()]
    R.Check("Replace URL" in items and items.index("Replace URL") == items.index("Replace w/new PDF")+1, "the menu item follows 'Replace w/new PDF'", str(items))

    answer=[]
    realShow, realValue=FIP.ReplaceURLDialog.ShowModal, FIP.ReplaceURLDialog.GetValue
    FIP.ReplaceURLDialog.ShowModal=lambda self: wx.ID_OK if answer else wx.ID_CANCEL
    FIP.ReplaceURLDialog.GetValue=lambda self: answer[0]
    def Replace(row, url: str|None) -> None:
        answer[:]=[url] if url is not None else []
        w._dataGrid.clickedRow=w.Datasource.Rows.index(row)
        Dialogs.Clear()
        w.OnPopupReplaceURL(None)
    try:
        row=[r for r in w.Datasource.Rows if r[0] == "Apollo03.pdf"][0]
        Replace(row, None)
        R.Check(row[0] == "Apollo03.pdf", "Cancel: nothing changes")
        Replace(row, "https://fanac.org/fanzines/Innuendo/Innuendo01.pdf")
        R.Check(row[0] == "../Innuendo/Innuendo01.pdf" and w.deltaTracker.Deltas == [] and w.NeedsSaving(), "OK: the row links there, nothing queued for the server", row[0])
        R.Check(w.RowServerFilename(row) == "" and "../innuendo/innuendo01.pdf" not in w.FilenamesInUse(),
                "and it isn't treated as one of this fanzine's files (no Regenerate PDF Header, Rename PDF or Move of it)")
        Upload(w)
        R.Check('href="../Innuendo/Innuendo01.pdf"' in Page("Apollo") and "Apollo03.pdf" in Files("Apollo", "fanzines") and not Dialogs.Messages,
                "uploaded: the page links there, and Apollo03.pdf is left on the server", str(Dialogs.Messages))

        other=[r for r in w.Datasource.Rows if r[0] == "Apollo04.pdf"][0]
        Replace(other, "https://fanac.org/fanzines/Apollo/Apollo05.pdf")
        R.Check(other[0] == "Apollo04.pdf" and Dialogs.Messages and "already the file of another issue" in Dialogs.Messages[0],
                "a link to a file another row already has: refused", str(Dialogs.Messages))

        new=AddRow(w, "Apollo98.pdf", Pdf("Apollo98.pdf"), "Apollo 98")
        try:
            Dialogs.Answer=wx.ID_NO
            Replace(new, "https://fanac.org/fanzines/Innuendo/Innuendo02.pdf")
            R.Check(len(Dialogs.Questions) == 1 and "'Apollo98.pdf', hasn't been uploaded yet" in Dialogs.Questions[0] and new[0] == "Apollo98.pdf"
                    and any(d.Row is new and d.Verb == "add" for d in w.deltaTracker.Deltas),
                    "a row whose PDF is still to be uploaded: asked first; No leaves it as it was", str(Dialogs.Questions))
            Dialogs.Answer=wx.ID_YES
            Replace(new, "https://fanac.org/fanzines/Innuendo/Innuendo02.pdf")
            R.Check(len(Dialogs.Questions) == 1 and new[0] == "../Innuendo/Innuendo02.pdf" and not any(d.Row is new for d in w.deltaTracker.Deltas)
                    and new.FileSourcePath == "", "Yes: it links there, and its PDF won't be uploaded (it would go to Innuendo's folder)",
                    str([str(d) for d in w.deltaTracker.Deltas]))
            Upload(w)
            R.Check("Apollo98.pdf" not in Files("Apollo") and not any("Innuendo02" in f for f in S.Files if "/Innuendo/" in f and T in f), "nothing uploaded for it")

            typed=AddRow(w, "Apollo97.pdf", Pdf("Apollo97.pdf"), "Apollo 97")
            Dialogs.Clear()
            Dialogs.Answer=wx.ID_NO
            EditFilename(w, typed, "../Innuendo/Innuendo04.pdf")
            R.Check(typed[0] == "Apollo97.pdf", "typing a link over such a row's filename: put back while the user decides", typed[0])
            wx.Yield()
            R.Check(len(Dialogs.Questions) == 1 and typed[0] == "Apollo97.pdf" and any(d.Row is typed and d.Verb == "add" for d in w.deltaTracker.Deltas),
                    "asked; No leaves it as it was", str(Dialogs.Questions))
            Dialogs.Clear()
            Dialogs.Answer=wx.ID_YES
            EditFilename(w, typed, "../Innuendo/Innuendo04.pdf")
            wx.Yield()
            R.Check(len(Dialogs.Questions) == 1 and typed[0] == "../Innuendo/Innuendo04.pdf" and not any(d.Row is typed for d in w.deltaTracker.Deltas),
                    "Yes: it links there, and its PDF won't be uploaded", f"{typed[0]} {[str(d) for d in w.deltaTracker.Deltas]}")
        finally:
            Dialogs.Answer=wx.ID_YES
        Upload(w)

        Dialogs.Clear()
        w._dataGrid.clickedRow=w.Datasource.Rows.index(row)
        w.wxGrid.ClearSelection()
        w.OnPopupDelRow(None)
        R.Check(not any(d.Verb == "delete" for d in w.deltaTracker.Deltas), "deleting a row that links elsewhere queues no server delete (was: of '../Innuendo/...')",
                str([str(d) for d in w.deltaTracker.Deltas]))
        Upload(w)

        five=[r for r in w.Datasource.Rows if r[0] == "Apollo05.pdf"][0]
        EditFilename(w, five, "../Innuendo/Innuendo03.pdf")
        R.Check(not any(d.Verb == "rename" for d in w.deltaTracker.Deltas), "typing a link over a filename queues no server rename (was: moving the file into Innuendo's folder)",
                str([str(d) for d in w.deltaTracker.Deltas]))
    finally:
        FIP.ReplaceURLDialog.ShowModal, FIP.ReplaceURLDialog.GetValue=realShow, realValue
        w.Destroy()


def ListRedrawFailure() -> None:
    R.Section("The list of fanzines survives a failed redraw (Edie, 2026-10-19)")
    FreshServer()
    m=FE.FanzinesEditorWindow(None)
    g=m.wxGrid
    realEndBatch=g.EndBatch
    failures=[1]
    def EndBatch():             # As wx did for Edie: the rebuild's EndBatch raises an assertion
        realEndBatch()
        if failures:
            failures.pop()
            raise wx.wxAssertionError('C++ assertion "idx >= 0 && idx < m_numRows" failed in GetRowPos(): invalid row index')
    g.EndBatch=EndBatch
    logged=[]
    realLogError=FE.LogError
    FE.LogError=lambda s, *a, **k: logged.append(s)
    try:
        try:
            m.tSearch.SetValue("Apol")
            got="no error escaped"
        except Exception as e:
            got=f"{type(e).__name__} escaped"
        R.Check(got == "no error escaped" and not g.IsFrozen() and g.GetBatchCount() == 0, "a keystroke whose redraw fails: no error escapes, and the grid isn't left frozen",
                f"{got} frozen={g.IsFrozen()} batch={g.GetBatchCount()}")
        R.Check(len(m.Datasource.FanzineList) == 1 and g.GetCellValue(0, 0) == "Apollo", "the list is redrawn, filtered", g.GetCellValue(0, 0))
        R.Check(len(logged) == 1 and "search='Apol'" in logged[0] and "grid rows=" in logged[0] and "cursor=" in logged[0],
                "the details needed to find the cause are logged", logged[0][:160] if logged else "")
        m.tSearch.SetValue("")
        m.tSearch.SetValue("Innu")
        R.Check(g.GetCellValue(0, 0) == "Innuendo" and not g.IsFrozen(), "and the next keystrokes work", g.GetCellValue(0, 0))
    finally:
        FE.LogError=realLogError
        m.Destroy()

    R.Section("A failed rebuild never leaves a grid frozen (shared WxDataGrid)")
    m=FE.FanzinesEditorWindow(None)
    g=m.wxGrid
    realEndBatch=g.EndBatch
    def Raise():
        realEndBatch()
        raise wx.wxAssertionError("test")
    g.EndBatch=Raise
    frozenBefore=g.IsFrozen()
    try:
        m._dataGrid.RefreshWxGridFromDatasource()
        got="no error"
    except wx.wxAssertionError:
        got="raised"
    R.Check(got == "raised" and not g.IsFrozen() and g.GetBatchCount() == 0, "the error still reaches the caller, but the grid is thawed (was: frozen for good)",
            f"{got} frozen={g.IsFrozen()} (before: {frozenBefore}) batch={g.GetBatchCount()}")
    m.Destroy()


def SearchAndWatchdog() -> None:
    R.Section("Search box: emptying it shows every fanzine again")
    FreshServer()
    m=FE.FanzinesEditorWindow(None)
    everything=len(m._fanzinesList)
    for text in ("A", "Ap", "A", ""):
        m.tSearch.SetValue(text)
    R.Check(len(m.Datasource.FanzineList) == everything, "backspacing to an empty box: the whole list (was: still the last search's)",
            f"{len(m.Datasource.FanzineList)} of {everything}")
    m.Destroy()

    R.Section("Hang watchdog")
    import threading
    logged=[]
    lock=threading.Lock()
    def Capture(s, *a, **k):
        with lock:
            logged.append(s)
    realLogError=FE.LogError
    FE.LogError=Capture
    m=FE.FanzinesEditorWindow(None)
    w=FE.HangWatchdog(m, limit=0.5, beat=0.1, poll=0.1, maxDumps=2)
    R.Check(w._timer.IsRunning() and w._timer.GetInterval() == 100, "the heartbeat timer is running", str(w._timer.GetInterval()))
    def Pump(seconds: float) -> None:      # FE responding for a while: as FE's MainLoop delivers the timer's beats (the tests run no MainLoop)
        end=time.monotonic()+seconds
        while time.monotonic() < end:
            w._Beat(None)
            time.sleep(0.05)
    def StuckInHere(seconds: float) -> None:
        time.sleep(seconds)
    try:
        Pump(0.6)
        R.Check(not logged, "responding: nothing logged", str(logged[:1]))
        StuckInHere(1.4)        # The main thread doesn't respond
        Pump(0.6)
        dumps=[s for s in logged if "hasn't responded" in s]
        R.Check(len(dumps) == 2 and "StuckInHere" in dumps[0] and "--- thread MainThread" in dumps[0],
                "not responding: what each thread is doing is logged, the main thread's stack included (at most maxDumps times)",
                f"{len(dumps)} dumps: {dumps[0][:200] if dumps else ''}")
        R.Check(any("responding again" in s for s in logged), "and when it responds again, that's logged too")
        logged.clear()
        FE.ProgressMessage._progressMessageDlg=object()     # A progress message is up: FE is visibly busy
        try:
            StuckInHere(1.0)
            Pump(0.3)
        finally:
            FE.ProgressMessage._progressMessageDlg=None
        R.Check(not any("hasn't responded" in s for s in logged), "busy behind a progress message (e.g. a big upload): nothing logged", str(logged[:1]))
    finally:
        w.Stop()
        Pump(0.3)
        FE.LogError=realLogError
        m.Destroy()


def SelectionKeptOnce() -> None:
    R.Section("A selection is kept once, not doubled with every redraw (Edie, 2026-10-19)")
    import WxDataGrid
    FreshServer()
    m=FE.FanzinesEditorWindow(None)
    g=m.wxGrid
    g.SelectBlock(1, 1, 1, 1)
    start=time.perf_counter()
    for text in ["A", "Ap", "A", "Ap", "A", "Ap", "A", "Ap", "A", "Ap", "A", "Ap", "A", "Ap"]:
        m.tSearch.SetValue(text)
    took=time.perf_counter()-start
    R.Check(len(list(g.GetSelectedBlocks())) == 0 and took < 2, "the main list: a search clears the selection (was: doubled per keystroke -- 4,096 after 12, 9 s each)",
            f"{len(list(g.GetSelectedBlocks()))} blocks, {took:.2f} s")
    m.Destroy()

    w=OpenPage("Apollo")
    g=w.wxGrid
    g.SelectBlock(2, 1, 2, 1)
    for _ in range(14):
        w._dataGrid.RefreshWxGridFromDatasource()
    blocks=[(b.TopRow, b.LeftCol, b.BottomRow, b.RightCol) for b in g.GetSelectedBlocks()]
    R.Check(blocks == [(2, 1, 2, 1)], "a page's grid: one selected cell is still one after 14 redraws (was: 16,384)", str(blocks[:3])+f" ({len(blocks)})")
    g.ClearSelection()
    g.SelectBlock(3, 0, 6, 2)
    g.SelectBlock(3, 0, 6, 2, addToSelected=True)
    sel=WxDataGrid.Selection(g)
    R.Check(sel.selectedBlocks == [(3, 0, 6, 2)], "the same block selected twice is kept once", str(sel.selectedBlocks))

    n=g.GetNumberRows()
    g.ClearSelection()
    g.SelectBlock(n-3, 0, n-1, 1)       # Partly past the end once the grid is shorter
    g.SelectBlock(n-1, 2, n-1, 2, addToSelected=True)     # Wholly past it
    sel=WxDataGrid.Selection(g)
    g.DeleteRows(n-2, 2)
    try:
        sel.Restore(g)
        blocks=[(b.TopRow, b.LeftCol, b.BottomRow, b.RightCol) for b in g.GetSelectedBlocks()]
    except Exception as e:
        blocks=f"{type(e).__name__}: {e}"
    R.Check(blocks == [(n-3, 0, n-3, 1)], "restored onto a shorter grid: cut short, or dropped (was: rows the grid no longer has)", str(blocks))
    w.Destroy()


def WindowPlacement() -> None:
    R.Section("Windows open on a connected screen")
    FreshServer()
    areas=[wx.Display(i).GetClientArea() for i in range(wx.Display.GetCount())]
    primary=next(wx.Display(i).GetClientArea() for i in range(wx.Display.GetCount()) if wx.Display(i).IsPrimary())

    def OnScreen(win) -> bool:
        r=win.GetRect()
        bar=wx.Rect(r.x, r.y, r.width, 30)
        return any(bar.Intersects(a) and bar.Intersect(a).width >= min(100, r.width) for a in areas)

    saved=Settings("FanzinesEditor positions.json").Dict       # In memory only: this dictionary has no file
    try:
        saved["Index Page Window Position"]=(40000, 40000)        # Where a now-unplugged monitor was
        saved["Index Page Window Size"]=(900, 600)
        w=OpenPage("Apollo")
        R.Check(OnScreen(w) and primary.Contains(w.GetRect().GetTopLeft()), "a fanzine page saved on a missing screen opens on the primary one",
                str(w.GetRect()))
        w.Destroy()
        here=(primary.x+40, primary.y+40)
        saved["Index Page Window Position"]=here
        w=OpenPage("Apollo")
        R.Check(tuple(w.GetPosition()) == here and tuple(w.GetSize()) == (900, 600), "one saved on a connected screen opens exactly where it was",
                f"{tuple(w.GetPosition())} {tuple(w.GetSize())}")
        w.Destroy()
        saved["Top Level Window Position"]=(-40000, 5)
        saved["Top Level Window Size"]=(50000, 50000)              # And far too big
        m=FE.FanzinesEditorWindow(None)
        r=m.GetRect()
        R.Check(OnScreen(m) and r.width <= primary.width and r.height <= primary.height, "the main window too, shrunk to fit", str(r))
        m.Destroy()
    finally:
        for k in ("Index Page Window Position", "Index Page Window Size", "Top Level Window Position", "Top Level Window Size"):
            saved.pop(k, None)


# ======================================================================================================================
for group in (PureFunctions, PdfWork, Deltas, Uploads, NamelessFiles, Regenerate, Moves, PageWindow, MainWindow, Safeguards, TidyUps, TidyUps2, Collections, NewComputer, FtpFailures, ReplaceURL, ListRedrawFailure, SearchAndWatchdog, SelectionKeptOnce, WindowPlacement):
    try:
        group()
    except Exception:
        R.Error(group.__name__)
sys.exit(R.Finish())
