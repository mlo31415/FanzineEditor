r"""
Tier 2 tests for FanzinesEditor: run before building an exe for Edie, or after changing FTP-level code. A few minutes.

    venv12\Scripts\python.exe tests\tier2.py

Runs a handful of end-to-end checks against the REAL test root (/fanzines-test), to catch what the fake server can't:
the real server's behaviour, upload size verification, connection problems. It refuses to start unless
'FanzinesEditor settings.txt' says Test mode=True and Test Root directory=fanzines-test, never writes to /fanzines, uses
small generated PDFs, and puts back everything it changed on the test root (in a finally, so an error midway still
cleans up). Results: tests/results/tier2.txt. Exit code 0 if everything passed.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness
from harness import Dialogs, MakePdf, PdfFacts, OpenPage, AddRow, EditFilename, Upload, MoveRows, Regenerate

harness.Setup(2)

import FanzinesEditor as FE
from FTP import FTP

R=harness.Results("tier2")
TMP=harness.TMP
T=harness.TEST_ROOT
SRC, TGT="Apollo", "Innuendo"


def Files(d: str) -> list[str]:
    return FTP().Nlst(f"/{T}/{d}") if FTP().PathExists(f"/{T}/{d}") else []


def Page(d: str) -> str:
    return FTP().GetFileAsString(f"/{T}/{d}", "index.html", TestLoad=True) or ""


def ServerPdf(d: str, name: str) -> dict:
    local=os.path.join(TMP, "downloaded.pdf")
    if not FTP().GetFile(f"/{T}/{d}", name, local):
        return dict(hasHeader=False, header="", links=[], metadata={"title": ""}, words=[])
    return PdfFacts(local)


def Pdf(name: str, text: str="Tier 2 test page") -> str:
    return MakePdf(os.path.join(TMP, name), text)


# ---------------------------------------------------------------- what's on the test root now, to put back afterwards
snapshot={d: (FTP().PathExists(f"/{T}/{d}"), Page(d) if FTP().PathExists(f"/{T}/{d}") else "") for d in (SRC, TGT)}
classic0=FTP().GetFileAsString(f"/{T}", "Classic_Fanzines.html", TestLoad=True)
R.Write(f"(test root before: {SRC} {'present' if snapshot[SRC][0] else 'absent'}, {TGT} {'present' if snapshot[TGT][0] else 'absent'}, "
        f"Classic list {'present' if classic0 else 'absent'})")

try:
    R.Section("Upload, with header and metadata, to the real test root")
    w=OpenPage(SRC)
    a=AddRow(w, "t2_a.pdf", Pdf("t2_a.pdf"), "Apollo 91")
    b=AddRow(w, "t2_b.pdf", Pdf("t2_b.pdf"), "Special Supplement")
    Upload(w)
    R.Check({"t2_a.pdf", "t2_b.pdf"} <= set(Files(SRC)) and "t2_a.pdf" in Page(SRC) and not Dialogs.Messages, "uploaded and published, no messages", str(Dialogs.Messages))
    f=ServerPdf(SRC, "t2_a.pdf")
    R.Check(f["hasHeader"] and f["header"].startswith("Apollo 91") and f["links"][:1] == ["https://www.fanac.org/fanzines/Apollo/"]
            and f["metadata"]["title"] == "Apollo 91", "the PDF on the server has its header, link and title", f["header"])

    R.Section("Rename and delete on the real server")
    EditFilename(w, b, "t2_b2.pdf")
    w.deltaTracker.Delete(serverDirName=SRC, row=a)
    w.Datasource.Rows.remove(a)
    Upload(w)
    files=Files(SRC)
    R.Check("t2_b2.pdf" in files and "t2_b.pdf" not in files and "t2_a.pdf" not in files and "t2_b2.pdf" in Page(SRC) and w.deltaTracker.Deltas == [],
            "renamed, deleted, page published", str([x for x in files if x.startswith("t2_")]))

    R.Section("Regenerate PDF Header on the real server")
    b[1]="Special Supplement (revised)"
    Regenerate(w, b)
    f=ServerPdf(SRC, "t2_b2.pdf")
    R.Check(f["header"].startswith("Apollo: Special Supplement (revised)") and "regenerated" in (Dialogs.Messages[-1] if Dialogs.Messages else ""),
            "the header was re-done from the page", f["header"])
    Upload(w)

    R.Section("Move to Different Fanzine on the real server")
    MoveRows(w, [b], TGT)
    f=ServerPdf(TGT, "t2_b2.pdf")
    R.Check("t2_b2.pdf" in Files(TGT) and "t2_b2.pdf" not in Files(SRC) and "t2_b2.pdf" in Page(TGT) and "t2_b2.pdf" not in Page(SRC),
            "copied to the target, original deleted, both pages updated")
    R.Check(f["links"][:1] == ["https://www.fanac.org/fanzines/Innuendo/"], "re-stamped for the new fanzine", str(f["links"]))
    w.Destroy()

    R.Section("Classic list upload on the real server")
    m=FE.FanzinesEditorWindow(None)
    c=[x for x in m._fanzinesList if x.ServerDir == SRC][0].Deepcopy()
    c.Editors="TIER 2 TEST"
    c._created=None
    m.MergeCFLIntoList(c)
    Dialogs.Clear()
    m.OnUploadPressed(None)
    back={x.ServerDir: x for x in FE.GetClassicFanzinesList()}
    R.Check(back[SRC].Editors == "TIER 2 TEST" and len(back) > 1000 and not m.NeedsSaving(), "merged into the full list and uploaded", f"{len(back)} entries")
    m.Destroy()

except Exception:
    R.Error("tier 2")

finally:
    # ---------------------------------------------------------------- put the test root back
    for d, (existed, page) in snapshot.items():
        for n in [x for x in Files(d) if x.startswith("t2_")]:
            FTP().DeleteFile(f"/{T}/{d}/{n}")
        if existed:
            FTP().PutFileAsString(f"/{T}/{d}", "index.html", page)
        elif FTP().PathExists(f"/{T}/{d}"):
            for n in Files(d):
                FTP().DeleteFile(f"/{T}/{d}/{n}")
            FTP().DeleteDir(f"/{T}/{d}")
    if classic0 is not None:
        FTP().PutFileAsString(f"/{T}", "Classic_Fanzines.html", classic0)
    restored=all((Page(d) == page) if existed else not FTP().PathExists(f"/{T}/{d}") for d, (existed, page) in snapshot.items())
    restored=restored and (classic0 is None or FTP().GetFileAsString(f"/{T}", "Classic_Fanzines.html") == classic0)
    R.Write(f"(test root put back as it was: {restored})")

sys.exit(R.Finish())
