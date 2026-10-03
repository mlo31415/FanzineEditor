"""
Shared setup for FanzinesEditor's tests (tests/tier1.py and tests/tier2.py). Call Setup() before importing any FE module.

The rules it enforces, learnt the hard way:
  * No window is ever shown, and no dialog ever appears: every kind of dialog is answered from a script (Dialogs).
  * Settings are pinned in memory (Test mode on, the test root, no local-directory root path) and can never be saved to
    the real settings files; the server-to-local table is a temporary copy.
  * Logs go to a temporary folder.
  * Tier 1 runs against a fake FTP server in memory (fakeftp.py) and cannot touch the network.
    Tier 2 runs against the real test root, and refuses to start unless the settings file says Test mode=True and
    Test Root directory=fanzines-test.
  * Results are written to tests/results/<name>.txt line by line, so an interrupted run still leaves them.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time

FE_DIR=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS_DIR=os.path.join(FE_DIR, "tests")
FIXTURES_DIR=os.path.join(TESTS_DIR, "fixtures")
TEST_ROOT="fanzines-test"
REAL_ROOT="fanzines"

TMP=""          # A temporary folder for this run (removed by Results.Finish)
App=None        # The wx.App
Server=None     # Tier 1: the FakeServer
_console=sys.stdout     # Results are printed here; FE's own chatter (its Log prints everything) goes to the log file only


# ======================================================================================================================
# Dialogs: nothing is ever shown. Messages are recorded; questions are answered from these.
class Dialogs:
    Messages: list[str]=[]          # Every wx.MessageBox text
    Questions: list[str]=[]         # Every wx.MessageDialog text
    Answer: int=0                   # What wx.MessageDialog answers (set to wx.ID_YES by Setup)
    TextAnswers: list[str|None]=[]  # Queue of wx.TextEntryDialog answers: a string is OK with that value; None (or empty queue) is Cancel
    FilePaths: list[list[str]]=[]   # Queue of wx.FileDialog answers: a list of paths is OK; an empty queue is Cancel

    @staticmethod
    def Clear() -> None:
        Dialogs.Messages.clear()
        Dialogs.Questions.clear()
        Dialogs.TextAnswers.clear()
        Dialogs.FilePaths.clear()


def _StubDialogs(wx) -> None:
    wx.MessageBox=lambda *a, **k: Dialogs.Messages.append(a[0] if a else k.get("message", ""))

    class MessageDialog:
        def __init__(self, parent=None, message="", *a, **k):
            Dialogs.Questions.append(message)
        def ShowModal(self): return Dialogs.Answer
        def Destroy(self): pass
        def __enter__(self): return self
        def __exit__(self, *a): pass
    wx.MessageDialog=MessageDialog

    answers: dict[int, str]={}
    def TextShowModal(self):
        a=Dialogs.TextAnswers.pop(0) if Dialogs.TextAnswers else None
        if a is None:
            return wx.ID_CANCEL
        answers[id(self)]=a
        return wx.ID_OK
    wx.TextEntryDialog.ShowModal=TextShowModal
    wx.TextEntryDialog.GetValue=lambda self: answers.get(id(self), "")

    paths: dict[int, list[str]]={}
    def FileShowModal(self):
        if not Dialogs.FilePaths:
            return wx.ID_CANCEL
        paths[id(self)]=Dialogs.FilePaths.pop(0)
        return wx.ID_OK
    wx.FileDialog.ShowModal=FileShowModal
    wx.FileDialog.GetPaths=lambda self: paths.get(id(self), [])
    wx.FileDialog.Paths=property(lambda self: paths.get(id(self), []))
    wx.FileDialog.GetFilenames=lambda self: paths.get(id(self), [])


class _QuietProgress:        # Stands in for ProgressMessage2: no window
    def __init__(self, *a, **k): pass
    def Update(self, *a, **k): pass
    def Destroy(self): pass
    def Show(self, *a, **k): pass
    def Close(self, *a, **k): pass


# ======================================================================================================================
def RemoveKey(d, name: str) -> None:
    """Remove a key, whatever its case, from a settings dictionary (a dict, or HelpersPackage's ParmDict)."""
    d=d._parms if hasattr(d, "_parms") else d
    for k in [k for k in list(d.keys()) if k.casefold() == name.casefold()]:
        del d[k]


def _SetSetting(Settings, name: str, value) -> None:
    """Set a setting in memory only, replacing the existing key whatever its case (lookups are case-insensitive)."""
    RemoveKey(Settings().Dict, name)
    Settings().Dict[name]=value


def Setup(tier: int) -> None:
    """Prepare a test run. Tier 1: fake FTP server, no network. Tier 2: the real test root."""
    global TMP, App, Server
    os.chdir(FE_DIR)
    if FE_DIR not in sys.path:
        sys.path.insert(0, FE_DIR)
    if TESTS_DIR not in sys.path:
        sys.path.insert(0, TESTS_DIR)
    TMP=tempfile.mkdtemp(prefix="FE-tests-")
    sys.stdout=open(os.devnull, "w", encoding="utf-8")      # (Python's own errors still appear: they go to stderr)

    import wx
    App=wx.App(False)
    Dialogs.Answer=wx.ID_YES
    _StubDialogs(wx)

    from Log import LogOpen
    LogOpen(os.path.join(TMP, "Log.txt"), os.path.join(TMP, "Log Errors.txt"))

    from Settings import Settings
    Settings().Load("FanzinesEditor settings.txt", MustExist=True)
    if tier == 2 and not (Settings().IsTrue("Test mode") and (Settings().Get("Test Root directory") or "").strip() == TEST_ROOT):
        raise SystemExit(f"Tier 2 refuses to run: 'FanzinesEditor settings.txt' must say Test mode=True and Test Root directory={TEST_ROOT}")
    _SetSetting(Settings, "Test mode", "True")
    _SetSetting(Settings, "Test Root directory", TEST_ROOT)
    _SetSetting(Settings, "Root directory", REAL_ROOT)
    _SetSetting(Settings, "Local Directory Root Path", "")

    # The server-to-local table: a temporary copy
    real=Settings().Get("Server To Local Table Name")
    table=os.path.join(TMP, "ServerToLocal.txt")
    shutil.copyfile(real, table)
    _SetSetting(Settings, "Server To Local Table Name", table)
    Settings("ServerToLocal").Load(table)

    # No test may ever save a settings file outside this run's temporary folder
    realSave=Settings.Save
    def GuardedSave(self) -> None:
        if self.Dictpath and not os.path.abspath(self.Dictpath).startswith(os.path.abspath(TMP)):
            raise RuntimeError(f"A test tried to save settings to {self.Dictpath}")
        realSave(self)
    Settings.Save=GuardedSave

    from FTP import FTP
    from FTPLog import FTPLog
    if tier == 1:
        import fakeftp
        Server=fakeftp.Install()
    else:
        FTP().OpenConnection("FTP Credentials.json")
    FTPLog().Init("tests", f"/{TEST_ROOT}/FanzinesEditor Log.txt")

    # FE's windows: never shown
    import FanzineIndexPageEdit as FIP
    import FanzinesEditor as FE
    FIP.ProgressMessage2=_QuietProgress
    FE.ProgressMessage2=_QuietProgress
    FIP.FanzineIndexPageWindow.ShowModal=lambda self: wx.ID_OK
    FE.FanzinesEditorWindow.Show=lambda self, *a, **k: True
    FE.FanzinesEditorWindow.Raise=lambda self, *a, **k: None
    with open(os.path.join(FE_DIR, "Fanac logo for pdf headers.jpg"), "rb") as f:
        FIP.SetHeaderLogo(f.read())


# ======================================================================================================================
# Driving a fanzine page window the way a user would
def OpenPage(serverDir: str):
    import FanzineIndexPageEdit as FIP
    w=FIP.FanzineIndexPageWindow(None, serverDir=serverDir)
    if w.failure:
        raise RuntimeError(f"Could not load {serverDir}")
    return w


def AddRow(w, name: str, local: str, text: str):
    """Add an issue as Add New Issue(s) does: a row pointing at a local file, and a pending add."""
    w.Datasource.AppendEmptyRows(1)
    r=w.Datasource.Rows[-1]
    r.FileSourcePath=local
    r[0]=name
    r[1]=text
    w.deltaTracker.Add(local, row=r)
    return r


def EditFilename(w, row, newname: str) -> None:
    """Change a filename the way typing in the grid does, through the real cell-change handler."""
    import wx
    import wx.grid
    w._dataGrid.RefreshWxGridFromDatasource()
    irow=w.Datasource.Rows.index(row)
    w.wxGrid.SetCellValue(irow, 0, newname)
    w.OnGridCellChanged(wx.grid.GridEvent(w.wxGrid.GetId(), wx.grid.wxEVT_GRID_CELL_CHANGED, w.wxGrid, irow, 0))


def Upload(w) -> None:
    Dialogs.Clear()
    w.OnUpload(None)


def MoveRows(w, rows: list, targetDir: str) -> None:
    """Move to Different Fanzine, through the real handler (the rows must be next to each other)."""
    idx=[w.Datasource.Rows.index(r) for r in rows]
    w._dataGrid.clickedRow=idx[0]
    w.wxGrid.ClearSelection()
    if len(idx) > 1:
        w.wxGrid.SelectBlock(min(idx), 0, max(idx), 0)
    Dialogs.Clear()
    Dialogs.TextAnswers.append(targetDir)
    w.OnPopupMoveToFanzine(None)


def Regenerate(w, row) -> None:
    w._dataGrid.clickedRow=w.Datasource.Rows.index(row)
    w.wxGrid.ClearSelection()
    Dialogs.Clear()
    w.OnPopupRegeneratePDFHeader(None)


# ======================================================================================================================
def MakePdf(path: str, text: str="Test page", pages: int=1, rotation: int=0, xmpTitle: str="") -> str:
    """A small PDF for the tests (much faster to upload than a real scan). Optionally rotated, or carrying XMP metadata."""
    import fitz
    doc=fitz.open()
    for i in range(pages):
        page=doc.new_page(width=420, height=600)
        page.insert_text((60, 120), f"{text} -- page {i+1}", fontsize=14)
    if rotation:
        doc[0].set_rotation(rotation)
    if xmpTitle:
        doc.set_xml_metadata(f'<?xpacket begin=""?><x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
                             f'<rdf:Description xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title><rdf:Alt><rdf:li xml:lang="x-default">{xmpTitle}'
                             f'</rdf:li></rdf:Alt></dc:title></rdf:Description></rdf:RDF></x:xmpmeta><?xpacket end="w"?>')
    doc.save(path)
    doc.close()
    return path.replace("\\", "/")


def PdfFacts(path: str) -> dict:
    """What a test wants to know about a PDF: its metadata, page-1 header text and links, rotation, XMP."""
    import fitz
    doc=fitz.open(path)
    page=doc[0]
    facts=dict(metadata=doc.metadata, rotation=page.rotation, xmp=doc.get_xml_metadata(),
               links=[l.get("uri") for l in page.get_links() if l.get("uri")],
               words=[w[4] for w in page.get_text("words")],
               header=page.get_text("text", clip=(0, 0, page.rect.width, 40)).replace("\n", " ").strip() if page.rotation == 0 else "")
    doc.close()
    facts["hasHeader"]="fanac.org/fanzines" in facts["words"]
    return facts


# ======================================================================================================================
class Results:
    """Collects PASS/FAIL lines, writing each to tests/results/<name>.txt as it happens."""
    def __init__(self, name: str) -> None:
        os.makedirs(os.path.join(TESTS_DIR, "results"), exist_ok=True)
        self.path=os.path.join(TESTS_DIR, "results", f"{name}.txt")
        self.passed=0
        self.failed: list[str]=[]
        self.start=time.time()
        open(self.path, "w", encoding="utf-8").close()
        self.Write(f"{name}: started {time.strftime('%Y-%m-%d %H:%M:%S')}")

    def Write(self, line: str) -> None:
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(line+"\n")
        try:
            print(line, file=_console, flush=True)
        except UnicodeEncodeError:
            print(line.encode("ascii", "replace").decode("ascii"), file=_console, flush=True)

    def Section(self, title: str) -> None:
        self.Write(f"=== {title} ===")

    def Check(self, ok: bool, text: str, detail: str="") -> bool:
        if ok:
            self.passed+=1
        else:
            self.failed.append(text)
        self.Write(f"  [{'PASS' if ok else 'FAIL'}] {text}"+(f"   ({detail})" if detail and not ok else ""))
        return ok

    def Error(self, where: str) -> None:
        """Record an unexpected exception in a group of tests as a failure, and carry on with the next group."""
        import traceback
        self.failed.append(f"{where}: exception")
        self.Write(f"  [FAIL] {where}: unexpected exception\n"+"".join("        "+l for l in traceback.format_exc().splitlines(True)))

    def Finish(self) -> int:
        total=self.passed+len(self.failed)
        self.Write(f"--- {self.passed} of {total} passed, {len(self.failed)} failed, in {time.time()-self.start:.0f} s")
        for f in self.failed:
            self.Write(f"    FAILED: {f}")
        shutil.rmtree(TMP, ignore_errors=True)
        return 1 if self.failed else 0
