from __future__ import annotations

import os
import wx
import wx.grid
import sys
import re

from FTP import FTP, Lock

from FTPLog import FTPLog
from WxDataGrid import DataGrid, GridDataSource, ColDefinitionsList, GridDataRowClass, ColDefinition, IsEditable
from WxHelpers import OnCloseHandling, ProgressMessage2, ModalDialogManager
from HelpersPackage import ExtractInvisibleTextInsideFanacComment, ConvertHTMLishCharacters
from HelpersPackage import InsertHTMLUsingFanacStartEndCommentPair, UnicodeToHtml, StripSpecificTag, Int0, TimestampFilename
from Log import LogOpen, LogClose, LogError
from Log import Log as RealLog
from Settings import Settings
from FanacFanzinesHelpers import ReadClassicFanzinesTable

from FanzineIndexPageEdit import FanzineIndexPageWindow, ClassicFanzinesDate, Tagit
from FanzineNames import FanzineNames
from GenGUIClass import FanzinesGridGen
from GenLogDialogClass import LogDialog
from ClassicFanzinesLine import ClassicFanzinesLine


def main():

    # Initialize wx
    app=wx.App(False)

    # Set up LogDialog
    # global g_LogDialog
    # g_LogDialog=LogDialog(None)
    # g_LogDialog.Show()

    # showLogWindow=Settings().Get("Show log window", False)
    # if showLogWindow:
    #     g_LogDialog.Destroy()
    #     g_LogDialog=None

    homedir=os.getcwd()
    LogOpen(os.path.join(homedir, "Log -- FanzinesEditor.txt"), os.path.join(homedir, "Log (Errors) -- FanzinesEditor.txt"))
    Log(f"Open Logfile {os.path.join(homedir, 'Log -- FanzinesEditor.txt')}")
    Log(f"{homedir=}")
    Log(f"{sys.executable=}")

    # Load the global settings dictionary
    Log(f"Settings().Load({os.path.join(homedir, 'FanzinesEditor settings.txt')})")
    Settings().Load(os.path.join(homedir, "FanzinesEditor settings.txt"), MustExist=True)
    Log(Settings().Dump())
    Settings("FanzinesEditor positions.json").Load(os.path.join(homedir, "FanzinesEditor positions.json"), MustExist=True, SuppressMessageBox=True)
    Log(Settings("FanzinesEditor positions.json").Dump())

    # Set the debug/production mode
    global g_debug
    g_debug=Settings().Get("Debug Mode", False)
    g_testServer=Settings().Get("Test Root Directory", "")

    # Allow turning off of routine FTP logging
    FTP.g_dologging=Settings().Get("FTP Logging", False)

    FTP().LoggingOff()

    id=Settings().Get("ID")
    rootDir="/fanzines"
    if Settings().IsTrue("Test mode"):
        rootDir="/"+Settings().Get("Test Root Directory", rootDir)

    # Initialize logging of activities
    FTPLog().Init(id, f"{rootDir}/FanzinesEditor Log.txt")

    if not os.path.exists("FTP Credentials.json"):
        msg=f"Unable to find file 'FTP Credentials.json' file.\nExpected to find it in {os.getcwd()}"
        Log(msg, isCritical=True)


    if not FTP().OpenConnection("FTP Credentials.json"):
        Log("Main: OpenConnection('FTP Credentials.json' failed")
        Log("Unable to open connection to FTP server fanac.org", isCritical=True)


    # Attempt to establish a lock on the Fanzines directories
    lockEstablished=False
    if id is not None:
        rslt=Lock().SetLock(rootDir, id)
        if rslt == "":
            lockEstablished=True
        else:
            dlg=wx.MessageDialog(None, f"Unable to establish a lock for id '{id}' in directory '{rootDir}' because: \n{rslt}. \n\n Do you wish to proceed, anyway? ", "Continue (and risk disaster)?", wx.YES_NO|wx.ICON_QUESTION)
            result=dlg.ShowModal()
            dlg.Destroy()
            if result == wx.ID_YES:
                lockEstablished=True

    if lockEstablished:
        # Initialize the GUI
        FanzinesEditorWindow(None)

        # Run the event loop
        app.MainLoop()

    Lock().ReleaseLock(rootDir, id)

    LogClose()
    sys.exit(1)


#------------------------------------------------------------------------------
g_LogDialog: LogDialog|None=None
def Log(text: str, isError: bool=False, noNewLine: bool=False, Print=True, Clear=False, Flush=False, timestamp=False, isWarning=False, isCritical=False) -> None:
    RealLog(text, isError=isError, noNewLine=noNewLine, Print=Print, Clear=Clear, Flush=Flush, timestamp=timestamp, isWarning=isWarning, isCritical=isCritical)
    if g_LogDialog is not None:
        if not text.endswith("\n"):
            text=text+"\n"
        g_LogDialog.textLogWindow.AppendText(text)


#==========================================================================================================
# Read the classic fanzine list on fanac.org and return a list of all *fanzine directory names*
def GetClassicFanzinesList() -> list[ClassicFanzinesLine]|None:
    html=None
    if Settings().Get("Test mode", "False") == "True":
        testRootDirectory=Settings().Get("Test Root directory")
        if testRootDirectory != "":
            testRootDirectory="/"+testRootDirectory
            # If there is a test directory, try loading from there, first
            html=FTP().GetFileAsString(testRootDirectory, "Classic_Fanzines.html")
    if html is None:
        # If we're not in test mode or if that failed (or there wasn't one) load from the default
        html=FTP().GetFileAsString("/fanzines", "Classic_Fanzines.html")
    if html is None:
        LogError(f"Unable to download 'Classic_Fanzines.html' because: {FTP().LastMessage}")

        return None

    # Remove the &amp;amp;amp;amp;amp;... that has crept in to some pages.
    while "&amp;amp;" in html:
        html=html.replace("amp;amp;", "amp;")
        Log(f"redundant 'amp;'s removed from Classic_Fanzines.html")

    rows=ReadClassicFanzinesTable(html)
    assert rows is not None

    rowtable: list[list[str]]=[]
    for row in rows[1:]:    # row[0] is the column headers, and for this file the columns are hard-coded, so they can be ignored.
        srow=str(row)
        if "<form action=" in srow[:30]:  # I don't know where this line is coming from (it shows up as the last row, but does not appear on the website!)>
            continue

        # Parse a row into columns
        # Drop everything before the first <td>
        loc=srow.lower().find("<td>")
        if loc >= 0:
            srow=srow[loc:]
        # Break the remainder into section bounced by <td...> and </td> plus whatever's left

        cells=[]
        while True:
            colpat=r"<td.*?>(.*?)</td>"
            m=re.search(colpat, srow, flags=re.IGNORECASE | re.DOTALL)
            if m is None:
                if len(srow) > 0:
                    cells.append(srow)
                break
            cells.append(m.groups()[0])
            srow=re.sub(colpat, "", srow, count=1, flags=re.IGNORECASE | re.DOTALL)

        #Log(str(cols))
        rowtable.append(cells)

    # Process each of the columns
    namelist: list[ClassicFanzinesLine]=[]
    for row in rowtable:
        if len(row) == 0:
            continue
        if "<form action=" in row[0]:    # I don't know where this is coming from (this shows up as the last row, but does not appear on the website)>
            continue

        # Remove class='right' and class='left' as this is just noise for our purposes
        def RemoveClassRightLeft(s: str) -> str:
            # We need to deal with either kind of quote and also should not leave double spaces behind due to the removal.
            return re.sub(r"class=[\'\"](right|left)[\'\"]", "", s)
        # Do a strip() and then if the entry is nothing but whitespace and HTML that amounts to whitespace, remove it all
        def DStrip(s: str) -> str:
            s=s.strip()
            ss=re.sub(r"\s|<br>|</br>|<br/>|<td>", "", s, flags=re.IGNORECASE)
            if len(ss) == 0:
                return ""
            return s

        row=[DStrip(RemoveClassRightLeft(x)) for x in row]

        cfl=ClassicFanzinesLine()
        # Column 0
        # This is the blue dot.  No information here, it seems.

        # Column 1
        # <td sorttable_customkey="1940S ONE SHOTS"><a href="1940s_One_Shots/"><strong>1940s One Shots</strong></a></td>
        # This cell is of one of two possible formats:
        # (1) '<a href="Zed-Nielsen_Hayden/"><strong>Zed</strong></a>'
        # This is the typical case with URL and text
        # (2) '<a href="Zed/"><strong>Zed, The </strong></a><br/> Die Zeitschrift Fur Vollstandigen Unsinn'
        # In a few cases, the fanzine has a list of alternative names following.
        if row[1] != "":
            m=re.search(r'<a href=[\'\"]?([^>]+?)/?[\'\"]?>(.+)</a>(.*)$', row[1], flags=re.DOTALL|re.IGNORECASE)
            if m is None:
                Log(f"GetFanzineList() Failure: column 1 (Name and URL), {row[1]=}")
                Log(f"                {row=}")
                continue

            url=m.group(1).strip()
            cfl.Name=FanzineNames(StripSpecificTag(m.group(2), "strong", Number=5), m.group(3))
            m=re.match(r"https://fanac.org/fanzines([a-zA-Z 0-9\-]*?)/(.*)$", url, flags=re.IGNORECASE)
            if m is not None:
                url=m.group(2)
            cfl.ServerDir=StripSpecificTag(url, "strong")

        # Column 2: Editor
        if row[2] != "":
            cfl.Editors=ConvertHTMLishCharacters(row[2].strip())
            # Strip trailing semicolon which otherwise looks like a second, blank editor
            if len(cfl.Editors) > 0 and cfl.Editors[-1] == ";":
                cfl.Editors=cfl.Editors[:-1]

        # Column 3: Dates
        if row[3] != "":
            cfl.Dates=ConvertHTMLishCharacters(row[3].strip())

        # Column 4: Type
        if row[4] != "":
            cfl.Type=row[4].strip()

        # Column 5: Issues
        if row[5] != "":
            cfl.Issues=row[5].strip()

        # Column 6: Flag
        if len(row) < 7:
            row.append("")      # This column is optional, but it's easier to process if we add it on as blank
        if row[6] != "":
            m=re.search(r'<x class="complete">Complete</x>', row[6], flags=re.IGNORECASE)
            if m is not None:
                cfl._complete=True

            cfl.Updated=ClassicFanzinesDate()
            val=ExtractInvisibleTextInsideFanacComment(row[6], "updated")
            if len(val) > 0:
                cfl.Updated=val

            cfl.DuplicateCopy=False
            val=ExtractInvisibleTextInsideFanacComment(row[6], "duplicate")
            if val == "yes":
                cfl.DuplicateCopy=True

            val=ExtractInvisibleTextInsideFanacComment(row[6], "created")
            if len(val) > 0:
                cfl.Created=val

        if cfl.Updated is None: # Look for an invisible Updated flag somewhere in the row
            cfl.Updated=ClassicFanzinesDate(ExtractInvisibleTextInsideFanacComment(str(row), "updated"))

        # When we create the classic list, we add fanzines with more than one title in multiple places and mark all but one as duplicate.
        # We only want one entry for each fanzine, so we skip appending the duplicates.
        if not cfl.DuplicateCopy:
            namelist.append(cfl)
            #Log(f"{row[1]=}    {cfl.ServerDir=}    {cfl.Name=}")
        #Log(str(row))

    return namelist


def PutClassicFanzineList(fanzinesList: list[ClassicFanzinesLine], rootDir: str) -> bool:
    if not os.path.exists("Template - Classic_Fanzines.html"):
        LogError(f"PutFanzineIndexPage() can't find 'Template - Classic_Fanzines.html' at {os.path.curdir}")
        return False
    with open("Template - Classic_Fanzines.html") as f:
        output=f.read()

    # There is a single entry for each fanzine, including ones with multiple titles. We want to create an entry for each title.
    # The strategy will be to duplicate any ClassicFanzinesLine with multiple names, marking the extras as duplicate so they are ignored when doing the GetFanzinesList
    duplicatelist=[]
    for fanzine in fanzinesList:
        duplicatelist.append(fanzine)
        if len(fanzine.Name.Othernames) > 0:
            # Duplicate the fanzine's entry, swapping each of the other names in turn as the main name
            for i in range(len(fanzine.Name.Othernames)):
                fz=fanzine.Deepcopy()
                if fz.Name.SwapMainNameAndOtherName(i):
                    fz.DuplicateCopy=True
                    duplicatelist.append(fz)

    duplicatelist.sort(key=lambda x:x.DisplayNameSort)

    insert=""
    for fanzine in duplicatelist:
        # <!-- fanac.table start -->
        # <TR VALIGN="top">
        # <TD><IMG SRC="blue.gif" HEIGHT="14" WIDTH="21" ALT="[BB]"></TD>
        # <!-- LINK="Aberration/ Aberration" -->
        # <!-- TYPE="Genzine" -->
        # <TD sorttable_customkey="ABERRATION"><A HREF="Aberration/"><STRONG>Aberration</STRONG></A></TD>
        # <TD sorttable_customkey="MOOMAW, KENT">Kent Moomaw</TD>
        # <TD sorttable_customkey="19570000">1957-1957</TD>
        # <TD>Genzine</TD>
        # <TD CLASS="right" sorttable_customkey="00003">3 </TD>
        # <TD><X CLASS="complete">Complete</X></TD>
        # </TR>
        # <!-- fanac.table end -->
        row='<TR VALIGN="top">\n'
        row+='<TD><IMG SRC="blue.gif" HEIGHT="14" WIDTH="21" ALT="[BB]"></TD>\n'
        row+=f'<TD sorttable_customkey="{fanzine.DisplayNameSort}"><A HREF="{fanzine.ServerDir}/"><STRONG>{UnicodeToHtml(fanzine.Name.MainName)}</STRONG></A>'
        if len(fanzine.Name.Othernames) > 0:
            row+="<br>"+fanzine.Name.OthernamesAsHTML
        row+=f'</TD>'
        row+=f'<TD sorttable_customkey="{fanzine.EditorsSort}">{UnicodeToHtml(fanzine.Editors)}</TD>\n'
        row+=f'<TD sorttable_customkey="{fanzine.DatesSort}">{fanzine.Dates}</TD>\n'
        row+=f'<TD>{fanzine.Type}</TD>\n'
        row+=f'<TD CLASS="right" sorttable_customkey="{fanzine.IssuesSort}">{fanzine.Issues}</TD>\n'

        updatedFlag=fanzine.Updated.DaysAgo() < Int0(Settings().Get("How old is updated", 90))
        newFlag=fanzine.Created.DaysAgo() < Int0(Settings().Get("How old is new", 90))

        flags=("n" if newFlag else "")+("u" if updatedFlag else "")+("c" if fanzine.Complete else "")

        match flags:
            case "":
                row+=f'<TD sorttable_customkey="zzzz"><BR>&nbsp;<br>\n'
            case "c":
                row+=f'<TD sorttable_customkey="complete"><br><X CLASS="complete">Complete</X><br>\n'
            case "u":
                row+=f'<TD sorttable_customkey="updated"><br><X CLASS="updated">Updated</X><br>\n'
            case "n":
                row+=f'<TD sorttable_customkey="new"><br><X CLASS="new">New</X><br>\n'
            case "uc":
                row+=f'<TD sorttable_customkey="complete+updated"><br><X CLASS="complete">Complete</X><X CLASS="updated">Updated</X><br>\n'
            case "nc":
                row+=f'<TD sorttable_customkey="complete+new"><br><X CLASS="complete">New+Complete</X><X CLASS="new">New</X><X CLASS="complete">Complete</X><br>\n'
            case "nu":
                row+=f'<TD sorttable_customkey="new+updated"><br><X CLASS="updated">Updated</X><X CLASS="new">New</X><br>\n'
            case "ncu":
                row+=f'<TD sorttable_customkey="complete+updated+new"><br><X CLASS="complete">Complete</X><X CLASS="updated">Updated</X><X CLASS="new">New</X><br>\n'

        flu=""
        if fanzine.Updated is not None:
            flu=str(fanzine.Updated)
        row+=f'<!-- fanac-updated {flu} -->\n'

        flu=""
        if fanzine.Created is not None:
            flu=str(fanzine.Created)
        row+=f'<!-- fanac-created {flu} -->\n'

        # When a fanzine is entered more than once (e.g., due to multiple names) al but one must be ignored
        row+=f'<!-- fanac-duplicate {"yes" if fanzine.DuplicateCopy else "no"} -->\n'

        row+=f'</TD></TR>\n'
        insert+=row

    temp=InsertHTMLUsingFanacStartEndCommentPair(output, "table", insert)
    if temp == "":
        LogError(f"Could not InsertUsingFanacComments('table')")
        return False
    output=temp

    insert=f"Updated {ClassicFanzinesDate().Now()}"
    temp=InsertHTMLUsingFanacStartEndCommentPair(output, "updated", insert)
    if temp == "":
        LogError(f"Could not InsertUsingFanacComments('updated')")
        return False
    output=temp

    with ModalDialogManager(ProgressMessage2, f"Uploading 'Classic_Fanzines.html'", parent=None):
        ret=FTP().BackupServerFile(f"/{rootDir}/Classic_Fanzines.html")

        if not ret:
            Log(f"Could not make a backup copy: {rootDir}/{TimestampFilename('Classic_Fanzines.html')}because {FTP().LastMessage}")
            return False

        ret=FTP().PutFileAsString(f"/{rootDir}", "Classic_Fanzines.html", output, create=True)
        if not ret:
            Log(f"Could not FTP().PutFileAsString: /{rootDir}/Classic_Fanzines.html because {FTP().LastMessage}")
            return False
    FTPLog().AppendItemVerb("upload Classic_Fanzines succeeded", f"{Tagit("RootDir", rootDir)}", Flush=True)
    return True


#==========================================================================================================
class FanzinesEditorWindow(FanzinesGridGen):
    def __init__(self, parent):
        FanzinesGridGen.__init__(self, parent)

        self._dataGrid: DataGrid=DataGrid(self.wxGrid)
        self.Datasource=FanzinesPage()      # Note that this is an empty instance
        self._fanzinesList: list[ClassicFanzinesLine]=[]        # This holds the linear list of fanzines that gets folded into the rectangular grid

        # Position the window on the screen it was on before at the size it was before
        tlwp=Settings("FanzinesEditor positions.json").Get("Top Level Window Position")
        if tlwp:
            self.SetPosition(tlwp)
        tlws=Settings("FanzinesEditor positions.json").Get("Top Level Window Size")
        if tlws:
            self.SetSize(tlws)

        # Load the server->local directory table
        s2LDir=Settings().Get("Server To Local Table Name")
        if s2LDir is None:
            s2LDir="ServerToLocalTable.txt"
            Settings().Put("Server To Local Table Name", s2LDir)

        if not Settings("ServerToLocal").Load(s2LDir):
            LogError(f"Can't open/read {os.getcwd()}/{s2LDir}")
            exit(999)

        # Figure out the server directory
        self.RootDir="fanzines"
        if Settings().IsTrue("Test mode"):
            self.RootDir=Settings().Get("Test Root Directory", self.RootDir)

        with ModalDialogManager(ProgressMessage2, "Downloading main fanzine page", parent=self):
                cfllist=GetClassicFanzinesList()
                if cfllist is None or len(cfllist) == 0:
                    return
                cfllist.sort(key=lambda cfl: cfl.ServerDir.casefold())
                self._fanzinesList=cfllist      # Update the linear list of fanzines
                self.Datasource.FanzineList=self._fanzinesList      # Update the rectangular grid of fanzine server directories

        self._dataGrid.HideRowLabels()
        self._dataGrid.HideColLabels()

        self._signature=0   # We need this member. ClearMainWindow() will initialize it
        self._fanzinesCount=0   # Also used to prevent exist with loss of data

        self.MarkAsSaved()
        self.tSearch.SetFocus()     # Start up with the entry cursor in the search box
        self.RefreshWindow()

        self.Show(True)
        self.Raise()    # Bring the window to the top
        self.tSearch.SetFocus()     # And put the focus/cursor in the search box


    @property
    def Datasource(self) -> FanzinesPage:       
        return self._Datasource
    @Datasource.setter
    def Datasource(self, val: FanzinesPage):
        self._Datasource=val
        self._dataGrid.Datasource=val


    def OnClosePressed( self, event ):
        self.OnClose(event)

    def OnExitPressed( self, event ):
        self.OnClose(event)

    def OnClose(self, event):

        if self._fanzinesCount != len(self._fanzinesList):
            resp=wx.MessageBox("You have added or deleted a fanzine from this list and have not saved the list. If you exist without saving, "
                               "those changes will be lost. \n\nDo you want to exist without saving?", 'Warning', wx.OK|wx.CANCEL|wx.ICON_WARNING)
            if resp == wx.CANCEL:
                return
        else:
            if OnCloseHandling(event, self.NeedsSaving(), "The list of fanzines has been updated and not yet saved. Exit anyway?"):
                return

        self.MarkAsSaved()  # The contents have been declared doomed

        # Save the window's position
        pos=self.GetPosition()
        Settings("FanzinesEditor positions.json").Put("Top Level Window Position", (pos.x, pos.y))
        size=self.GetSize()
        Settings("FanzinesEditor positions.json").Put("Top Level Window Size", (size.width, size.height))

        self.Destroy()
        LogClose()
        # sys.exit(1)


    def UpdateNeedsSavingFlag(self):       
        s="Editing Fanzines "
        if self.NeedsSaving():
            s=s+" *"        # Add on a change marker if needed
        self.SetTitle(s)


    def RefreshWindow(self, DontRefreshGrid: bool=False)-> None:       
        self.UpdateNeedsSavingFlag()
        if not DontRefreshGrid:
            self._dataGrid.RefreshWxGridFromDatasource()


    # ----------------------------------------------
    # Used to determine if anything has been updated
    def Signature(self) -> int:       
        return self.Datasource.Signature()


    def MarkAsSaved(self):       
        self._signature=self.Signature()
        self._fanzinesCount=len(self._fanzinesList)
        self.UpdateNeedsSavingFlag()


    def NeedsSaving(self):       
        return self._signature != self.Signature() or self._fanzinesCount != len(self._fanzinesList)


    def OnSearchText(self, event):       
        self.SearchFanzineList()


    def OnSearchTextChar(self, event: wx.KeyEvent):
        if event.GetKeyCode() != 13:
            event.Skip()
            return
        # A Return was pressed.  If the list of fanzines is down to 1, treat this as a request to open it.  (Otherwise, just process normally.)
        if len(self.Datasource._fanzineList) != 1:
            event.Skip()
            return

        self.clickedColumn=0
        self.clickedRow=0
        self.clickType="auto"
        self.OpenClickedCell(0, 0)


    def SearchFanzineList(self):       
        searchtext=self.tSearch.GetValue()
        if searchtext != "":
            fanzinelist=[x for x in self._fanzinesList if searchtext.casefold().replace("_", " ") in x.ServerDir.casefold().replace("_", " ") or searchtext.casefold() in x.Name.MainName.casefold()]
            self.Datasource.FanzineList=fanzinelist
            self.RefreshWindow()


    def OnClearSearch( self, event ):       
        self.Datasource.FanzineList=self._fanzinesList
        self.tSearch.SetValue("")
        self.RefreshWindow()


    def OnAddNewFanzine(self, event):

        with FanzineIndexPageWindow(None, ExistingFanzinesServerDirs=self.Datasource.FanzineList) as fsw:
            fsw.ShowModal()
        FTPLog().AppendItemVerb("New Fanzine", f"{Tagit("FanzineName", fsw.CFL.Name.MainName)}", Flush=True)

        if not fsw._uploaded:
            return

        # A new fanzine has been added.
        self._fanzinesList.append(fsw.CFL)
        self._fanzinesList.sort(key=lambda cfl: cfl.ServerDir.casefold())
        self.Datasource.FanzineList=self._fanzinesList
        self.SearchFanzineList()
        self.RefreshWindow()


    def OnGridCellLeftClick( self, event ):
        row=event.GetRow()
        if row > self.Datasource.NumRows-1:
            return
        col=event.GetCol()
        if col > self.Datasource.NumCols-1:
            return
        loc=row*self.Datasource.NumCols+col
        if loc > len(self.Datasource._fanzineList):
            return
        cfl=self.Datasource._fanzineList[loc]
        self.CFLText.Label=f"{cfl}"
        self._dataGrid.OnGridCellLeftClick(event)


    #-------------------
    def OnGridCellDoubleClick(self, event):       
        self._dataGrid.SaveClickLocation(event, "double")
        self.OpenClickedCell(event.Col, event.Row)


    def OpenClickedCell(self, icol: int, irow: int):

        serverDir=self._Datasource.Rows[irow][icol]
        with FanzineIndexPageWindow(None, serverDir=serverDir) as fipw:
            if fipw.failure:
                wx.MessageBox(f"Unable to load {serverDir}", caption="Loading Fanzine Index page", parent=self)
                Log(f"FanzineIndexPageWindow('{serverDir}') failed")
                return
            fipw.ShowModal()

        # The edit may have updated some of the parameters.
        if fipw.CFL is not None:
            # First, we have to figure out where to store the result. The icol and irow can be used only if the entire list of fanzines was being displayed.
            # If they were the result of a search, they are meaningless
            # We make use of the fact that the derver directories are unique.
            index=[i for i, x in enumerate(self._fanzinesList) if x.ServerDir == fipw.CFL.ServerDir][0]    # There should be exactly one hit

            self._fanzinesList[index]=fipw.CFL

            #existingCFL: ClassicFanzinesLine=self._fanzinesList[self.Datasource.NumCols*event.Row+event.Col]
            # Display the updated fanzines list
            self._fanzinesList.sort(key=lambda cfl: cfl.ServerDir.casefold())
            self.Datasource.FanzineList=self._fanzinesList
            self.SearchFanzineList()
            self.RefreshWindow()

    #-------------------
    # Upload the fanzines list to the classic fanzine page
    def OnUploadPressed( self, event ):
        success=PutClassicFanzineList(self._fanzinesList, self.RootDir)
        self.Raise()    # Bring the window to the top
        self.tSearch.SetFocus()     # And put the focus/cursor in the search box
        if success:
            self.MarkAsSaved()

    # ------------------
    def OnDeleteFanzineClicked( self, event):
        row=self._dataGrid.clickedRow
        col=self._dataGrid.clickedColumn
        type=self._dataGrid.clickType
        if row is None or col is None or type is None:
            wx.MessageBox("No fanzine selected for deletion.", parent=self)
            return
        if type == "left":
            selectedFanzine=self._dataGrid.Datasource.Rows[row][col]

            dlg=wx.MessageDialog(None, f"Really delete {selectedFanzine}?", "Delete fanzine?", wx.YES_NO|wx.ICON_QUESTION)
            result=dlg.ShowModal()
            dlg.Destroy()
            if result == wx.ID_YES:
                self._fanzinesList=[x for x in self._fanzinesList if x.ServerDir != selectedFanzine]
                self._fanzinesList.sort(key=lambda cfl: cfl.ServerDir.casefold())
                searchtext=self.tSearch.GetValue()
                fanzinelist=self._fanzinesList
                if searchtext != "":
                    fanzinelist=[x for x in self._fanzinesList if searchtext.casefold().replace("_", " ") in x.ServerDir.casefold().replace("_", " ") or searchtext.casefold() in x.Name.MainName.casefold()]
                self.Datasource.FanzineList=fanzinelist
                self.RefreshWindow()


    # ------------------
    # Initialize the main window to empty
    # This also initiazes the datasource
    def ClearMainWindow(self):       

        # Re-initialize the form

        # Create an empty datasource
        self.Datasource._fanzineList=[]

        # Update the dialog's grid from the data
        self._dataGrid.RefreshWxGridFromDatasource(RetainSelection=False)

        # Set the signature to the current (empty) state so any change will trigger a request to save on exit
        self.MarkAsSaved()


#=============================================================
# An individual file to be listed under a convention
# This is a single row
class FanzinesPageRow(GridDataRowClass):

    def __init__(self, cells: list[str]):
        GridDataRowClass.__init__(self)
        self._cells: list[str]=cells

    def __str__(self):
        return str(self._cells)

    def __len__(self):
        return len(self._cells)

    def __hash__(self):
        return sum([(i+1)*hash(x) for i, x in enumerate(self._cells)])

    def Extend(self, s: list[str]) -> None:
        self._cells.extend(s)

    # Make a deep copy of a FanzineTableRow
    def Copy(self) -> FanzinesPageRow:
        ftr=FanzinesPageRow([])
        ftr._cells=self._cells
        return ftr

    # We multiply the cell has by the cell index (+1) so that moves right and left also change the signature
    def Signature(self) -> int:
        return self.__hash__()

    @property
    def Cells(self) -> list[str]:
        return self._cells
    @Cells.setter
    def Cells(self, newcells: list[str]):
        self._cells=newcells

    @property
    def CanDeleteColumns(self) -> bool:
        return False

    # This deletes a single column from the datasource.
    # It must be implemented here because WxDataGrid doesn't understand the details of the DataSource
    def DelCol(self, icol: int) -> None:
        del self._cells[icol]


    def __getitem__(self, index: int | slice) -> str | list[str]:
        if isinstance(index, int):
            return self._cells[index]
        if isinstance(index, slice):
            return self._cells[index]
            #return self._cells(self.List[index])
        raise KeyError

    def __setitem__(self, index: str | int | slice, value: str | int | bool) -> None:
        if isinstance(index, int):
            self._cells[index]=value
            return
        raise KeyError

    @property
    def IsEmptyRow(self) -> bool:
        return all([cell.strip() == "" for cell in self._cells])


#####################################################################################################
#####################################################################################################

class FanzinesPage(GridDataSource):
    def __init__(self):
        GridDataSource.__init__(self)
        self._numCols=5
        self._colDefs: ColDefinitionsList=ColDefinitionsList([])
        for i in range(self._numCols):
            self._colDefs.append(ColDefinition("", IsEditable=IsEditable.Yes))
        self._rows: list[FanzinesPageRow]=[]
        self._gridDataRowClass=FanzinesPageRow
        #self._daysForUpdatedFlag=Settings().Get("How old is old", 90)

        self._fanzineList:list[FanzinesPageRow]=[]

    def __hash__(self):
        return sum([hash(x)*(i+1) for i, x in enumerate(self._fanzineList)])


    def Signature(self) -> int:        
        return self.__hash__()

    # Inherited from GridDataSource
    @property
    def Rows(self) -> list[FanzinesPageRow]:        
        return self._rows
    @Rows.setter
    def Rows(self, rows: list) -> None:        
        self._rows=rows

    @property
    def NumRows(self) -> int:        
        numcells=len(self._fanzineList)
        if numcells%self._numCols == 0:
            return numcells//self._numCols
        return numcells//self._numCols+1

    @property
    def FanzineList(self):
        serverdirs=[]
        for row in self._rows:
            for cell in row:
                if len(cell) > 0:
                    serverdirs.append(cell)
        return serverdirs
    @FanzineList.setter
    def FanzineList(self, val: list[ClassicFanzinesLine]):
        self._fanzineList=val

        # Update the number of rows and columns
        numrows=len(val)/self._numCols
        if len(val)%self._numCols != 0:
            numrows+=1

        # Now distribute the 1-D fanzine list into the 2-D grid
        self._rows=[]
        for i in range(len(val)):
            row=i//self._numCols
            col=i%self._numCols
            if col == 0:
                self._rows.append(self._gridDataRowClass(self._numCols*[""]))
            self._rows[row][col]=val[i].ServerDir



    def __getitem__(self, index: int) -> FanzinesPageRow:        
        return self.Rows[index]

    def __setitem__(self, index: int, val: FanzinesPageRow) -> None:        
        self._fanzineList[index]=val
    def CanAddColumns(self) -> bool:        
        return False

    def CanMoveColumns(self) -> bool:     
        return False             # Override if columns can't be moved


    def InsertEmptyRows(self, insertat: int, num: int=1) -> None:        
        for i in range(num):
            ftr=FanzinesPageRow([""]*self.NumCols)
            self._fanzineList.insert(insertat+i, ftr)


if __name__ == "__main__":
    main()