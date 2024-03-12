from __future__ import annotations

from typing import Optional

import os
import wx
import wx.grid
import sys
import re

from FTP import FTP
from bs4 import BeautifulSoup
from datetime import datetime

from WxDataGrid import DataGrid, GridDataSource, ColDefinitionsList, GridDataRowClass, ColDefinition, IsEditable
from WxHelpers import OnCloseHandling, ProgressMsg
from HelpersPackage import MessageBox, SearchExtractAndRemoveBoundedAll, ExtractInvisibleTextInsideFanacComment
from HelpersPackage import InsertHTMLUsingFanacComments, UnicodeToHtml, StripSpecificTag, Int0
from Log import LogOpen, LogClose, LogError
from Log import Log as RealLog
from Settings import Settings

from FanzineIndexPageEdit import FanzineIndexPageWindow, ClassicFanzinesDate
from GenGUIClass import FanzinesGridGen
from GenLogDialogClass import LogDialog
from ClassicFanzinesLine import ClassicFanzinesLine


def main():

    # Initialize wx
    app=wx.App(False)


    if sys.gettrace() is None:
        # We are not running under the debugger
        homedir=os.path.split(sys.executable)[0]
    else:
        # We are debugging.
        homedir=os.getcwd()

    homedir=os.getcwd()     # Awful. This will break a non-debug version

    # Set up LogDialog
    # global g_LogDialog
    # g_LogDialog=LogDialog(None)
    # g_LogDialog.Show()

    # showLogWindow=Settings().Get("Show log window", False)
    # if showLogWindow:
    #     g_LogDialog.Destroy()
    #     g_LogDialog=None

    LogOpen(os.path.join(homedir, "Log -- FanzinesEditor.txt"), os.path.join(homedir, "Log (Errors) -- FanzinesEditor.txt"))
    Log(f"Open Logfile {os.path.join(homedir, 'Log -- FanzinesEditor.txt')}")
    Log(f"{homedir=}")
    Log(f"{sys.executable=}")

    # Load the global settings dictionary
    Log(f"Settings().Load({os.path.join(homedir, 'FanzinesEditor settings.txt')})")
    Settings().Load(os.path.join(homedir, "FanzinesEditor settings.txt"), MustExist=True)
    Log(Settings().Dump())
    Settings("FanzinesEditor positions.json").Load(os.path.join(homedir, "FanzinesEditor positions.json"), MustExist=True)
    Log(Settings("FanzinesEditor positions.json").Dump())

    # Set the debug/production mode
    global g_debug
    g_debug=Settings().Get("Debug Mode", False)
    g_testServer=Settings().Get("Test server Directory", "")

    # Allow turning off of routine FTP logging
    FTP.g_dologging=Settings().Get("FTP Logging", False)

    if not os.path.exists("FTP Credentials.json"):
        msg=f"Unable to find file 'FTP Credentials.json' file.  Expected to find it in {os.getcwd()}"
        MessageBox(msg, ignoredebugger=True)
        Log(msg)
        exit(0)

    if not FTP().OpenConnection("FTP Credentials.json"):
        MessageBox("Unable to open connection to FTP server fanac.org", ignoredebugger=True)
        Log("Main: OpenConnection('FTP Credentials.json' failed")
        exit(0)


    # Initialize the GUI
    FanzineEditorWindow(None)

    # Run the event loop
    app.MainLoop()

    LogClose()
    sys.exit(1)


#------------------------------------------------------------------------------
g_LogDialog: Optional[LogDialog]=None
def Log(text: str, isError: bool=False, noNewLine: bool=False, Print=True, Clear=False, Flush=False, timestamp=False) -> None:
    RealLog(text, isError=isError, noNewLine=noNewLine, Print=Print, Clear=Clear, Flush=Flush, timestamp=timestamp)
    if g_LogDialog is not None:
        if not text.endswith("\n"):
            text=text+"\n"
        g_LogDialog.textLogWindow.AppendText(text)


#==========================================================================================================
# Read the classic fanzine list on fanac.org and return a list of all *fanzine directory names*
def GetFanzinesList() -> list[ClassicFanzinesLine]|None:
    testServerDirectory=Settings().Get("Test server directory")
    html=None
    if testServerDirectory != "":
        # If there is a test directory, try loading from there, first
        html=FTP().GetFileAsString(testServerDirectory, "Classic_Fanzines.html")
    if html is None:
        # If that failed (or there wasn't one) load from the default
        html=FTP().GetFileAsString("fanzines", "Classic_Fanzines.html")
    if html is None:
        LogError(f"Unable to download 'Classic_Fanzines.html'")
        return None

    soup=BeautifulSoup(html, 'html.parser')
    table=soup.find_all("table", class_="sortable")[0]
    rows=table.find_all_next("tr")
    rowtable: list[list[str]]=[]
    for i, row in enumerate(rows[1:]):    # row[0] is the column headers, and for this file the columns are hard-coded, so they can be ignored.
        srow=str(row)
        if "<form action=" in srow[:30]:  # I don't know where this line is coming from (it shows up as the last row, but does not appear on the website!)>
            continue

        # Parse a row into columns by breaking on <td>...</td>
        row, srow=SearchExtractAndRemoveBoundedAll(srow, r"(<td)(.*?)<\/td>")

        #Log(str(cols))
        rowtable.append(row)

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
            ss=re.sub(r"\s|<br>|</br>|<br/>|<td>", "", s)
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
        # In aa few cases, the fanzine has a list of alternative names following.
        if row[1] != "":
            m=re.search(r'<td\s*sorttable_customkey=[\'\"](.*?)[\'\"]><a href=[\'\"]?([^>]+?)/?[\'\"]?>(.+)</a>(.*)$', row[1], flags=re.IGNORECASE)
            if m is None:
                Log(f"GetFanzineList() Failure: column 1 (Name and URL), {row[1]=}")
                Log(f"                {row=}")
                continue

            cfl.ServerDir=m.groups()[1]
            cfl.DisplayName=StripSpecificTag(m.groups()[2], "strong", CaseSensitive=False)
            cfl.OtherNames=m.groups()[3]

        # Column 2: Editor
        # '<td sorttable_customkey="SPEER, JACK">Jack Speer'
        if row[2] != "":
            m=re.search(r'<td\s*sorttable_customkey=[\'\"](.*?)[\'\"]>(.*)$', row[2], flags=re.IGNORECASE)
            if m is None:
                Log(f"GetFanzineList() Failure: column 2 (Editors), {row[2]=}")
                Log(f"                {row=}")
                continue
            cfl.Editors=m.groups()[1]

        # Column 3: Dates
        # '<td sorttable_customkey="19390000">1939-1943'
        if row[3] != "":
            m=re.search(r'<td\s*sorttable_customkey=[\'\"](.*?)[\'\"]>(.*)$', row[3], flags=re.IGNORECASE)
            if m is None:
                Log(f"GetFanzineList() Failure: column 3 (Dates), {row[3]=}")
                Log(f"                {row=}")
                continue
            cfl.Dates=m.groups()[1]

        # Column 4: Type
        # '<td>Fanzine'
        if row[4] != "":
            m=re.search(r'<td>(.*)$', row[4], flags=re.IGNORECASE)
            if m is None:
                Log(f"GetFanzineList() Failure: column 4 (Type), {row[4]=}")
                Log(f"                {row=}")
                continue
            cfl.Type=m.groups()[0]

        # Column 5: Issues
        # '<td class="right" sorttable_customkey="00001">1 '
        if row[5] != "":
            m=re.search(r'<td\s*sorttable_customkey=[\'\"](.*?)[\'\"]>(.*)$', row[5], flags=re.IGNORECASE)
            if m is None:
                Log(f"GetFanzineList() Failure: column 5 (Dates), {row[5]=}")
                Log(f"                {row=}")
                continue
            cfl.Issues=m.groups()[1]

        # Column 6: Flag
        # '<td sorttable_customkey="zzzz"><br/>'
        if len(row) < 7:
            row.append("")
        if row[6] != "":
            m=re.search(r'<td\s*sorttable_customkey=[\'\"](.*?)[\'\"]>(.*)$', row[6], flags=re.IGNORECASE)
            if m is not None:
                flag=m.groups()[1].lower()
                if flag == "<br>" or flag == "<br/>":
                    cfl.Flag=""
                else:
                    cfl.Flag=m.groups()[1]

            m=re.search(r'<x class="complete">Complete</x>', row[6], flags=re.IGNORECASE)
            if m is not None:
                cfl._complete=True

            cfl.Updated=""
            val=ExtractInvisibleTextInsideFanacComment(html, "updated")
            if len(val) > 0:
                cfl.Updated=val


            val=ExtractInvisibleTextInsideFanacComment(html, "created")
            if len(val) > 0:
                cfl.Created=val

        # Look for an invisible Updated flag somewhere in the row
        cfl.Updated=ClassicFanzinesDate(ExtractInvisibleTextInsideFanacComment(str(row), "updated"))


        namelist.append(cfl)
        #Log(str(row))

    return namelist


def PutClassicFanzineList(fanzinesList: list[ClassicFanzinesLine], rootDir: str) -> bool:
    if not os.path.exists("Template - Classic_Fanzines.html"):
        LogError(f"PutFanzineIndexPage() can't find 'Template - Classic_Fanzines.html' at {os.path.curdir}")
        return False
    with open("Template - Classic_Fanzines.html") as f:
        output=f.read()

    insert=""
    for fanzine in fanzinesList:
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
        row+=f'<TD sorttable_customkey="{fanzine.DisplayNameSort}"><A HREF="{fanzine.ServerDir}/"><STRONG>{UnicodeToHtml(fanzine.DisplayName)}</STRONG></A></TD>'
        row+=f'<TD sorttable_customkey="{fanzine.EditorsSort}">{UnicodeToHtml(fanzine.Editors)}</TD>\n'
        row+=f'<TD sorttable_customkey="{fanzine.DatesSort}">{fanzine.Dates}</TD>\n'
        row+=f'<TD>{fanzine.Type}</TD>\n'
        row+=f'<TD CLASS="right" sorttable_customkey="{fanzine.IssuesSort}">{fanzine.Issues}</TD>\n'

        updatedFlag=fanzine.Updated.DaysAgo() < Int0(Settings().Get("How old is updated", 90))
        newFlag=fanzine.Created.DaysAgo() < Int0(Settings().Get("How old is new", 90))

        flags=("n" if newFlag else "")+("u" if updatedFlag else "")+("c" if fanzine.Complete else "")

        match flags:
            case "":
                row+=f'<TD sorttable_customkey="zzzz"><BR>&nbsp;</TD>\n'
            case "c":
                row+=f'<TD sorttable_customkey="complete"><X CLASS="complete">Complete</X></TD>\n'
            case "u":
                row+=f'<TD sorttable_customkey="updated"><X CLASS="updated">Updated</X></TD>\n'
            case "n":
                row+=f'<TD sorttable_customkey="new"><X CLASS="new">New</X></TD>\n'
            case "uc":
                row+=f'<TD sorttable_customkey="complete+updated"><X CLASS="complete">Complete</X><X CLASS="updated">Updated</X></TD>\n'
            case "nc":
                row+=f'<TD sorttable_customkey="complete+new"><X CLASS="complete">New+Complete</X><X CLASS="new">New</X><X CLASS="complete">Complete</X></TD>\n'
            case "nu":
                row+=f'<TD sorttable_customkey="new+updated"><X CLASS="updated">Updated</X><X CLASS="new">New</X></TD>\n'
            case "ncu":
                row+=f'<TD sorttable_customkey="complete+updated+new"><X CLASS="complete">Complete</X><X CLASS="updated">Updated</X><X CLASS="new">New</X></TD>\n'

        flu=""
        if fanzine.Updated is not None:
            flu=str(fanzine.Updated)
        row+=f'<!-- fanac-updated {flu} -->\n'

        flu=""
        if fanzine.Created is not None:
            flu=str(fanzine.Created)
        row+=f'<!-- fanac-created {flu} -->\n'

        row+=f'</TR>\n'
        insert+=row

    temp=InsertHTMLUsingFanacComments(output, "table", insert)
    if temp == "":
        LogError(f"Could not InsertUsingFanacComments('table')")
        return False
    output=temp

    insert=f"Updated {ClassicFanzinesDate().Now()}"
    temp=InsertHTMLUsingFanacComments(output, "updated", insert)
    if temp == "":
        LogError(f"Could not InsertUsingFanacComments('updated')")
        return False
    output=temp

    with ProgressMsg(None, f"Uploading 'Classic_Fanzines.html'"):
        ret=FTP().CopyAndRenameFile(f"/{rootDir}/", "Classic_Fanzines.html",
                                    f"/{rootDir}/", f"Classic_Fanzines - {datetime.now():%Y-%m-%d %H-%M-%S}.html")
        if not ret:
            Log(f"Could not make a backup copy: {rootDir}/Classic_Fanzines - {datetime.now():%Y-%m-%d %H-%M-%S}.html")
            return False

        ret=FTP().PutFileAsString(f"/{rootDir}", "Classic_Fanzines.html", output, create=True)
        if not ret:
            Log(f"Could not FTP().PutFileAsString: /{rootDir}/Classic_Fanzines.html")
            return False
    return True


#==========================================================================================================
class FanzineEditorWindow(FanzinesGridGen):
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
            Settings().Put("Server To Local Table Name", "s2LDir")

        if not Settings("ServerToLocal").Load(s2LDir):
            Log(f"Can't open/read {os.getcwd()}/{s2LDir}")
            exit(999)


        # Figure out the server directory
        self.RootDir="Fanzines"
        if Settings().IsTrue("Test mode"):
            self.RootDir=Settings().Get("Test Server Directory", self.RootDir)


        with ProgressMsg(self, "Downloading main fanzine page"):
            cfllist=GetFanzinesList()
            if cfllist is None or len(cfllist) == 0:
                return
            cfllist.sort(key=lambda cfl: cfl.ServerDir.casefold())
            self._fanzinesList=cfllist      # Update the linear list oif fanzines
            self.Datasource.FanzineList=self._fanzinesList      # Update the rectangular grid of fanzine server directories

        self._dataGrid.HideRowLabels()
        self._dataGrid.HideColLabels()

        self._signature=0   # We need this member. ClearMainWindow() will initialize it

        self.MarkAsSaved()
        self.RefreshWindow()

        self.Show(True)


    @property
    def Datasource(self) -> FanzinesPage:       # FanzineEditor(FanzineGrid)
        return self._Datasource
    @Datasource.setter
    def Datasource(self, val: FanzinesPage):
        self._Datasource=val
        self._dataGrid.Datasource=val


    def OnClosePressed( self, event ):
        self.OnClose(event)

    def OnExitPressed( self, event ):
        self.OnClose(event)

    def OnClose(self, event):       # FanzineEditor(FanzineGrid)
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
        sys.exit(1)


    def UpdateNeedsSavingFlag(self):       # FanzineEditor(FanzineGrid)
        s="Editing Fanzines "
        if self.NeedsSaving():
            s=s+" *"        # Add on a change marker if needed
        self.SetTitle(s)


    def RefreshWindow(self, DontRefreshGrid: bool=False)-> None:       # FanzineEditor(FanzineGrid)
        self.UpdateNeedsSavingFlag()
        if not DontRefreshGrid:
            self._dataGrid.RefreshWxGridFromDatasource()


    # ----------------------------------------------
    # Used to determine if anything has been updated
    def Signature(self) -> int:       # FanzineEditor(FanzineGrid)
        return self.Datasource.Signature()


    def MarkAsSaved(self):       # FanzineEditor(FanzineGrid)
        self._signature=self.Signature()


    def NeedsSaving(self):       # FanzineEditor(FanzineGrid)
        return self._signature != self.Signature()


    def OnSearchText(self, event):       # FanzineEditor(FanzineGrid)
        self.SearchFanzineList()


    def SearchFanzineList(self):       # FanzineEditor(FanzineGrid)
        searchtext=self.tSearch.GetValue()
        if searchtext != "":
            fanzinelist=[x for x in self._fanzinesList if searchtext.casefold().replace("_", " ") in x.ServerDir.casefold().replace("_", " ") or searchtext.casefold() in x.DisplayName.casefold()]
            self.Datasource.FanzineList=fanzinelist
            self.RefreshWindow()


    def OnClearSearch( self, event ):       # FanzineEditor(FanzineGrid)
        self.Datasource.FanzineList=self._fanzinesList
        self.tSearch.SetValue("")
        self.RefreshWindow()


    def OnAddNewFanzine(self, event):       # FanzineEditor(FanzineGrid)
        fsw=FanzineIndexPageWindow(None)
        if fsw.failure:
            MessageBox(f"Unable to load new fanzine window", Title="Loading Fanzine Index page", ignoredebugger=True)
            Log(f"FanzineIndexPageWindow('') failed")
            return

        with FanzineIndexPageWindow(None) as fsw:
            fsw.ShowModal()

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
        col=event.GetCol()
        cfl=self.Datasource._fanzineList[row*self.Datasource.NumCols+col]
        self.CFLText.Label=f"{cfl}"
        self._dataGrid.OnGridCellLeftClick(event)


    #-------------------
    def OnGridCellDoubleClick(self, event):       # FanzineEditor(FanzineGrid)
        self._dataGrid.SaveClickLocation(event, "double")
        serverDir=self._Datasource.Rows[event.Row][event.Col]
        with FanzineIndexPageWindow(None, serverDir) as fsw:
            if fsw.failure:
                wx.MessageBox(f"Unable to load {serverDir}", caption="Loading Fanzine Index page", parent=self)
                Log(f"FanzineIndexPageWindow('{serverDir}') failed")
                return
            fsw.ShowModal()

        # The edit may have updated some of the parameters.
        if fsw.CFL is not None:
            self._fanzinesList[self.Datasource.NumCols*event.Row+event.Col]=fsw.CFL
            #existingCFL: ClassicFanzinesLine=self._fanzinesList[self.Datasource.NumCols*event.Row+event.Col]
            # Display the updated fanzines list
            self._fanzinesList.sort(key=lambda cfl: cfl.ServerDir.casefold())
            self.Datasource.FanzineList=self._fanzinesList
            self.SearchFanzineList()
            self.RefreshWindow()

    #-------------------
    # Upload the fanzines list to the classic fanzine page
    def OnUploadPressed( self, event ):       # FanzineEditor(FanzineGrid)
        PutClassicFanzineList(self._fanzinesList, self.RootDir)
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
            fanzine=self._dataGrid.Datasource.Rows[row][col]

            dlg=wx.MessageDialog(None, f"Really delete {fanzine}?", "Delete fanzine?", wx.YES_NO|wx.ICON_QUESTION)
            result=dlg.ShowModal()
            dlg.Destroy()
            if result == wx.ID_YES:
                self._fanzinesList=[x for x in self._fanzinesList if x.ServerDir != fanzine]
                self._fanzinesList.sort(key=lambda cfl: cfl.ServerDir.casefold())
                searchtext=self.tSearch.GetValue()
                fanzinelist=self._fanzinesList
                if searchtext != "":
                    fanzinelist=[x for x in self._fanzinesList if searchtext.casefold().replace("_", " ") in x.ServerDir.casefold().replace("_", " ") or searchtext.casefold() in x.DisplayName.casefold()]
                self.Datasource.FanzineList=fanzinelist
                self.RefreshWindow()


    # ------------------
    # Initialize the main window to empty
    # This also initiazes the datasource
    def ClearMainWindow(self):       # FanzineEditor(FanzineGrid)

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

    def __str__(self):      # FanzineTableRow(GridDataRowClass)
        return str(self._cells)

    def __len__(self):     # FanzineTableRow(GridDataRowClass)
        return len(self._cells)

    def Extend(self, s: list[str]) -> None:    # FanzineTableRow(GridDataRowClass)
        self._cells.extend(s)

    # Make a deep copy of a FanzineTableRow
    def Copy(self) -> FanzinesPageRow:      # FanzineTableRow(GridDataRowClass)
        ftr=FanzinesPageRow([])
        ftr._cells=self._cells
        return ftr

    # We multiply the cell has by the cell index (+1) so that moves right and left also change the signature
    def Signature(self) -> int:      # FanzineTableRow(GridDataRowClass)
        return sum([(i+1)*hash(x) for i, x in enumerate(self._cells)])

    @property
    def Cells(self) -> list[str]:      # FanzineTableRow(GridDataRowClass)
        return self._cells
    @Cells.setter
    def Cells(self, newcells: list[str]):
        self._cells=newcells

    @property
    def CanDeleteColumns(self) -> bool:      # FanzineTableRow(GridDataRowClass)
        return False

    # This deletes a single column from the datasource.
    # It must be implemented here because WxDataGrid doesn't understand the details of the DataSource
    def DelCol(self, icol: int) -> None:      # FanzineTableRow(GridDataRowClass)
        del self._cells[icol]


    def __getitem__(self, index: int | slice) -> str | list[str]:      # FanzineTableRow(GridDataRowClass)
        if isinstance(index, int):
            return self._cells[index]
        if isinstance(index, slice):
            return self._cells[index]
            #return self._cells(self.List[index])
        raise KeyError

    def __setitem__(self, index: str | int | slice, value: str | int | bool) -> None:      # FanzineTableRow(GridDataRowClass)
        if isinstance(index, int):
            self._cells[index]=value
            return
        raise KeyError

    &property
    def IsEmptyRow(self) -> bool:      # FanzineTableRow(GridDataRowClass)
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


    def Signature(self) -> int:        # FanzinesPage(GridDataSource)
        return sum([x.__hash__() *(i+1) for i, x in enumerate(self._fanzineList)])


    # Inherited from GridDataSource
    @property
    def Rows(self) -> list[FanzinesPageRow]:        # FanzinesPage(GridDataSource)
        return self._rows
    @Rows.setter
    def Rows(self, rows: list) -> None:        # FanzinesPage(GridDataSource)
        self._rows=rows

    @property
    def NumRows(self) -> int:        # FanzinesPage(GridDataSource)
        numcells=len(self._fanzineList)
        if numcells%self._numCols == 0:
            return numcells//self._numCols
        return numcells//self._numCols+1

    @property
    def FanzineList(self):
        assert False    # We don't actually ever expect to use this
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



    def __getitem__(self, index: int) -> FanzinesPageRow:        # FanzinesPage(GridDataSource)
        return self.Rows[index]

    def __setitem__(self, index: int, val: FanzinesPageRow) -> None:        # FanzinesPage(GridDataSource)
        self._fanzineList[index]=val

    def CanAddColumns(self) -> bool:        # FanzinesPage(GridDataSource)
        return False

    def CanMoveColumns(self) -> bool:     # FanzinesPage(GridDataSource)
        return False             # Override if columns can't be moved


    def InsertEmptyRows(self, insertat: int, num: int=1) -> None:        # FanzinesPage(GridDataSource)
        for i in range(num):
            ftr=FanzinesPageRow([""]*self.NumCols)
            self._fanzineList.insert(insertat+i, ftr)


if __name__ == "__main__":
    main()